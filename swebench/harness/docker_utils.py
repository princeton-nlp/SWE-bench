from __future__ import annotations

import io
import os
import tarfile
import threading
import time
import traceback
import subprocess
from pathlib import Path

from docker.models.containers import Container

from swebench.utils import generate_heredoc_delimiter, _get_log_objects


def copy_to_container(container: Container, src: Path, dst: Path):
    """
    Copy a file from local to a docker container

    Args:
        container (Container): Docker container to copy to
        src (Path): Source file path
        dst (Path): Destination file path in the container
    """
    if os.path.dirname(dst) == "":
        raise ValueError(
            f"Destination path parent directory cannot be empty!, dst: {dst}"
        )
    # A sibling .tar path can be an existing file, or even src itself.
    with io.BytesIO() as buffer:
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            tar.add(src, arcname=dst.name)
        data = buffer.getvalue()
    container.exec_run(f"mkdir -p {dst.parent}")
    container.put_archive(os.path.dirname(dst), data)


def write_to_container(container: Container, data: str, dst: Path):
    """
    Write a string to a file in a docker container
    """
    delimiter = generate_heredoc_delimiter(data)
    command = f"cat <<'{delimiter}' > {dst}\n{data}\n{delimiter}"
    container.exec_run(command)


def cleanup_container(client, container, logger):
    """
    Stop and remove a Docker container using subprocess commands.
    Performs this forcefully if the container cannot be stopped with the standard docker stop.

    Args:
        client (docker.DockerClient): Docker client (unused, kept for compatibility).
        container (docker.models.containers.Container): Container to remove.
        logger (logging.Logger): Logger to use for output. If None, print to stdout
    """
    if not container:
        return

    container_id = container.id
    container_name = container.name

    log_info, log_error, raise_error = _get_log_objects(logger)

    try:
        log_info(f"Attempting to stop container {container_name}...")
        cmd = ["docker", "stop", "--time=15", container_id]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
        log_info(f"Container {container_name} stopped successfully.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log_error(
            f"Failed to stop container {container_name}: {e}. Trying to forcefully kill..."
        )
        try:
            log_info(f"Forcefully killing container {container_name}...")
            cmd = ["docker", "kill", container_id]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                log_info(f"Container {container_name} killed successfully.")
            else:
                log_error(f"Failed to kill container {container_name}: {result.stderr}")
        except Exception as e2:
            if raise_error:
                raise e2
            log_error(
                f"Failed to forcefully kill container {container_name}: {e2}\n"
                f"{traceback.format_exc()}"
            )
    try:
        log_info(f"Attempting to remove container {container_name}...")
        cmd = ["docker", "rm", "--force", container_id]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            log_info(f"Container {container_name} removed successfully.")
        else:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        if raise_error:
            raise e
        log_error(
            f"Failed to remove container {container_name}: {e}\n"
            f"Command output: {getattr(e, 'stderr', 'N/A')}"
        )


def _close_exec_stream(stream) -> None:
    """Close a docker exec stream and the HTTP response underneath it.

    Left to the garbage collector, the response's finalizer reports
    "I/O operation on closed file" from inside __del__ and the socket leaks until then.
    Both closes are guarded: either may already be closed.
    """
    if stream is None:
        return
    for owner in (stream, getattr(stream, "_response", None)):
        close = getattr(owner, "close", None)
        if close is None:
            continue
        try:
            close()
        except Exception:
            pass


def exec_run_with_timeout(container, cmd, timeout: int | None = 60):
    """
    Run a command in a container with a timeout.

    Args:
        container (docker.Container): Container to run the command in.
        cmd (str): Command to run.
        timeout (int): Timeout in seconds.
    """
    exec_result = b""
    exec_id = None
    exec_stream = None
    exception = None
    timed_out = False

    def run_command():
        nonlocal exec_result, exec_id, exec_stream, exception
        try:
            exec_id = container.client.api.exec_create(container.id, cmd)["Id"]
            exec_stream = container.client.api.exec_start(exec_id, stream=True)
            for chunk in exec_stream:
                exec_result += chunk
        except Exception as e:
            exception = e
        finally:
            _close_exec_stream(exec_stream)

    thread = threading.Thread(target=run_command)
    start_time = time.time()
    thread.start()
    thread.join(timeout)
    if exception:
        raise exception
    if thread.is_alive():
        if exec_id is not None:
            exec_pid = container.client.api.exec_inspect(exec_id)["Pid"]
            container.exec_run(f"kill -TERM {exec_pid}", detach=True)
        # the reader is still blocked on the stream; closing it lets that thread end
        _close_exec_stream(exec_stream)
        timed_out = True
    end_time = time.time()
    # test output is arbitrary bytes; a stray non-UTF-8 byte must not kill the run
    return exec_result.decode(errors="replace"), timed_out, end_time - start_time
