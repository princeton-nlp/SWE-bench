# We are going to be testing the jedi library over here

import asyncio
import json
import subprocess
import jedi
import aiohttp
import os
from aiohttp import web
from typing import List

# This is set to tmp to start with, just to provide it a value for now
DIR_NAME = "/tmp"

# All functions here take input as 0 indexed, its YOUR job to make sure that
# the library takes the input in the correct way
# example: jedi takes input as 1 indexed line while pyright takes 0 indexed line

def go_to_references(dir_name: str, fs_file_path: str, line: int, column: int) -> List:
    """
    This function is going to return the references of the variable at the given line and column
    """
    # Open the file
    with open(fs_file_path, 'r') as fs_file:
        fs_file_content = fs_file.read()
    
    # Get the references
    project = jedi.Project(dir_name)
    # Line number is 1 indexed in jedi
    line = line + 1
    script = jedi.Script(fs_file_content, path=fs_file_path, project=project)
    references = script.get_references(line, column)
    formatted_references = []
    for reference in references:
        fs_file_path = reference.module_path
        start_position = reference.get_definition_start_position()
        end_position = reference.get_definition_end_position()
        formatted_references.append({
            'fs_file_path': fs_file_path,
            'range': {
                'startPosition': {
                    'line': start_position[0] - 1,
                    'column': start_position[1],
                    'byteOffset': 0,
                },
                'endPosition': {
                    'line': end_position[0] - 1,
                    'column': end_position[1],
                    'byteOffset': 0,
                }
            }
        })
    return formatted_references

async def go_to_references_handler(request):
    data = await request.json()
    fs_file_path = data['fs_file_path']
    position = data['position']
    line = int(position['line'])
    column = int(position['character'])
    results = go_to_references(DIR_NAME, fs_file_path, line, column)
    return web.json_response({
        'reference_locations': results,
    })

def go_to_definition(dir_name: str, fs_file_path: str, line: int, column: int):
    """
    This function is going to return the definition of the variable at the given line and column
    """
    # Open the file
    with open(fs_file_path, 'r') as fs_file:
        fs_file_content = fs_file.read()
    
    # Get the definition
    project = jedi.Project(dir_name)
    script = jedi.Script(fs_file_content, path=fs_file_path, project=project)
    definitions = script.goto(line + 1, column, follow_imports=True)
    formatted_definitions = []
    for definition in definitions:
        fs_file_path = str(definition.module_path)
        # print("definitions over here:::::::::", definition, dir_name, fs_file_path, line, column)
        start_position = definition.get_definition_start_position()
        end_position = definition.get_definition_end_position()
        # print("definitions position over here", start_position, end_position)
        formatted_definitions.append({
            'fs_file_path': fs_file_path.removeprefix(dir_name + '/'),
            'range': {
                'startPosition': {
                    'line': start_position[0] - 1,
                    'character': start_position[1],
                    'byteOffset': 0,
                },
                'endPosition': {
                    'line': end_position[0] - 1,
                    'character': end_position[1],
                    'byteOffset': 0,
                }
            }
        })
    return formatted_definitions

def get_diagnostics(dir_name: str, fs_file_path: str, line: int, column: int):
    """
    This function is going to return the diagnostics of the file at the given line and column
    We are going to use pyright over here instead of jedi since pyright also gives us back
    the compile type errors and is not too slow to be honest to be useful
    """
    # Open the file
    with open(fs_file_path, 'r') as fs_file:
        fs_file_content = fs_file.read()
    
    # Get the diagnostics
    project = jedi.Project(dir_name)
    script = jedi.Script(fs_file_content, path=fs_file_path, project=project)
    syntax_errors = script.get_syntax_errors()
    return syntax_errors

async def get_diagnostics_pyright(dir_name: str, fs_file_path: str, range):
    # Set the command to invoke pyright
    start_line = range['startPosition']['line']
    end_line = range['endPosition']['line']
    start_column = range['startPosition']['character']
    end_column = range['endPosition']['character']
    python_path = os.environ['VIRTUAL_ENV'] + '/bin/python'
    command = f"{python_path} -m pyright --project {dir_name} --outputjson"
    # print(f"diagnostics_commnad:command: {command}")

    try:
        # Run the command asynchronously
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=dir_name,
            shell=True,
        )

        # Wait for the command to complete
        stdout, stderr = await process.communicate()

        # print(stdout)

        # Check if there was an error
        # if process.returncode != 0:
        #     raise Exception(f"pyright command failed with error code {process.returncode}")

        # Parse the JSON output
        output = json.loads(stdout)

        # Grab the diagnostics over here
        diagnostics = output['generalDiagnostics']
        # print("get_diagnostics_pyright::diagnostics", len(diagnostics))
        # print("get_diagnostics_pyright::fs_file_path", fs_file_path)
        # Sample output of what diagnostics looks like
        # {
        #   "file": "/Users/skcd/scratch/swe_bench/harness.py",
        #   "severity": "error",
        #   "message": "Expression of type \"int\" is incompatible with return type \"str\"\n  \"int\" is incompatible with \"str\"",
        #   "range": {
        #     "start": {
        #       "line": 31,
        #       "character": 11
        #     },
        #     "end": {
        #       "line": 31,
        #       "character": 12
        #     }
        #   },
        #   "rule": "reportReturnType"
        # },
        # Now filter for all the diagnostics which are in the range we are looking at
        filtered_diagnostics = []
        for diagnostic in diagnostics:
            # For some reason pyright gives the file path back as /private/{file_path}
            # the check we can do here is for the suffix instead
            # print("dignostic_file", diagnostic['file'])
            if not diagnostic['file'].endswith(fs_file_path):
                continue
            # print("diagnostic found in file")
            diagnostic_range = diagnostic['range']
            diagnostic_start_line = diagnostic_range['start']['line']
            diagnostic_end_line = diagnostic_range['end']['line']
            # Only do line leve filtering for now
            # we want to make sure that our ranges overlap something
            if start_line <= diagnostic_start_line and diagnostic_end_line <= end_line:
                filtered_diagnostics.append({
                    'diagnostic': diagnostic['message'],
                    'range': {
                        'startPosition': {
                            'line': diagnostic_start_line,
                            'character': diagnostic_range['start']['character'],
                            'byteOffset': 0,
                        },
                        'endPosition': {
                            'line': diagnostic_end_line,
                            'character': diagnostic_range['end']['character'],
                            'byteOffset': 0,
                        },
                    },
                })

        return filtered_diagnostics

    except Exception as e:
        # Handle any exceptions that occur during the process
        print(f"Error: {e}")
        return []

def apply_edits(fs_file_path: str, edited_content: str, edit_range: dict):
    # Read the original file content
    with open(fs_file_path, 'r') as file:
        lines = file.readlines()

    # Extract the positions from the range dictionary
    start_line = edit_range['startPosition']['line']
    end_line = edit_range['endPosition']['line']

    # Split the edited content into lines, adding a newline to each
    edited_lines = [line + '\n' for line in edited_content.split('\n')]

    # Remove specified range of lines
    del lines[start_line:end_line + 1]

    # Insert new lines at the start of the removed range
    for index, new_line in enumerate(edited_lines):
        lines.insert(start_line + index, new_line)

    # Handle edge case for the last line if it's empty or only contains a newline
    if lines and not lines[-1].strip():
        lines[-1] = lines[-1].rstrip('\n')

    # Write the updated content back to the file
    with open(fs_file_path, 'w') as file:
        file.writelines(lines)

    # Calculate the new end line index after edits
    new_end_line = start_line + len(edited_lines) - 1

    # Prepare and return the new range
    new_range = {
        'startPosition': {'line': start_line, 'character': 0, 'byteOffset': 0},
        'endPosition': {'line': new_end_line, 'character': len(edited_lines[-1].strip()), 'byteOffset': 0}
    }

    return new_range

def create_file_open_handler(dir_name: str):
    async def file_open_handler(request):
        # print("file-open-handler")
        data = await request.json()
        fs_file_path = dir_name + "/" + data['fs_file_path']
        # print(f"fs_file_path: {fs_file_path}")
        with open(fs_file_path, 'r') as file:
            content = file.read()
        return web.json_response({
            'fs_file_path': data['fs_file_path'],
            'file_contents': content,
            'language': 'python',
            'exists': True,
        })
    return file_open_handler

def create_apply_edits_handler(dir_name: str):
    async def apply_edits_handler(request):
        print('apply-edits-handler')
        data = await request.json()
        fs_file_path = dir_name + '/' + data['fs_file_path']
        edited_content = data['edited_content']
        # Range here is made up of the following struct
        # {
        #   "startPosition": {
        #     "line": 31,
        #     "column": 11,
        #     "byteOffset": 0
        #   },
        #   "endPosition": {
        #     "line": 31,
        #     "column": 12,
        #     "byteOffset": 0
        #   }
        # }
        range = data['selected_range']
        print('===================================')
        print('edit-metadata', fs_file_path, range)
        print('===================================')
        new_range = apply_edits(fs_file_path, edited_content, range)
        return web.json_response({
            'fs_file_path': fs_file_path,
            'success': True,
            'new_range': new_range, 
        })
    return apply_edits_handler


def invoke_quick_fix(dir_name: str, fs_file_path: str, line: int, column: int):
    """
    This function is going to invoke the quick fix on the file
    """
    pass

async def invoke_quick_fix_handler(request):
    data = await request.json()
    request_id = data['request_id']
    return web.json_response({
        'request_id': request_id,
        'invocation_success': False,
    })

def get_quick_fix(dir_name: str, fs_file_path: str, line: int, column: int):
    """
    This function is going to return the quick fix on the file
    """
    pass

async def get_quick_fix_handler(request):
    data = await request.json()
    request_id = data['request_id']
    return web.json_response({
        'options': [],
    })

def create_go_to_definition_handler(dir_name):
    async def go_to_definition_handler(request):
        # print("go-to-definition-handler")
        data = await request.json()
        fs_file_path = dir_name + '/' + data['fs_file_path']
        position = data['position']
        line = int(position['line'])
        column = int(position['character'])
        results = go_to_definition(dir_name, fs_file_path, line, column)
        # print(fs_file_path, line, column, results)
        return web.json_response({'definitions': results})
    return go_to_definition_handler

def create_go_to_implementation_handler(dir_name):
    async def go_to_implementation_handler(request):
        # print('go_to_implementation_handler')
        data = await request.json()
        fs_file_path = dir_name + '/' + data['fs_file_path']
        position = data['position']
        line = int(position['line'])
        column = int(position['character'])
        results = go_to_definition(dir_name, fs_file_path, line, column)
        return web.json_response({'implementation_locations': results})
    return go_to_implementation_handler

def create_get_diagnostics_handler(dir_name):
    async def get_diagnostics_handler(request):
        # print('get_diagnotics_handler')
        data = await request.json()
        fs_file_path = dir_name + '/' + data['fs_file_path']
        range = data['range']
        # position = data['position']
        # line = int(position['line'])
        # column = int(position['character'])
        results = await get_diagnostics_pyright(dir_name, fs_file_path, range)
        return web.json_response({'diagnostics': results})
    return get_diagnostics_handler

def create_test_endpoint(test_cmd):
    async def get_test_endpoint(request):
        # print("test-endpoint")
        data = await request.json()
        # print(data)
        # test_cmd is an async method, idk how to pass it as that type tho :(
        passed, output = await test_cmd()
        # print("test_output::output", output)
        # print("test_output::passed", passed)
        return web.json_response({'test_output': output, 'passed': passed})
    return get_test_endpoint

# TODO(skcd): Expose an endpoint for running the test cmd
async def setup_webserver(dir_name: str, port: int, test_cmd) -> str:
    """
    This function is going to setup the webserver for the jedi library
    """
    DIR_NAME = dir_name
    app = web.Application()
    app.router.add_post('/go_to_references', go_to_references_handler)
    app.router.add_post('/go_to_definition', create_go_to_definition_handler(dir_name=dir_name))
    app.router.add_post('/go_to_implementation', create_go_to_implementation_handler(dir_name=dir_name))
    app.router.add_post('/diagnostics', create_get_diagnostics_handler(dir_name=dir_name))
    app.router.add_post('/apply_edits', create_apply_edits_handler(dir_name=dir_name))
    app.router.add_post('/invoke_quick_fix', invoke_quick_fix_handler)
    app.router.add_post('/select_quick_fix', get_quick_fix_handler)
    app.router.add_post('/run_tests', create_test_endpoint(test_cmd))
    app.router.add_post('/file_open', create_file_open_handler(dir_name=dir_name))
    app.router.add_get("/", lambda _: web.Response(text="Hello, world"))
    runner = web.AppRunner(app)
    print("Setting up the bare-bones editor here")
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    print(f"Staring bare-bones editor at http://localshot:{port}")
    await site.start()
    print(f"Editor started at http://localhost:{port}")
    return f"http://localhost:{port}"