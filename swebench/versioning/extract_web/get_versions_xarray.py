import json
import os
import re
import requests
import sys

from datetime import datetime

sys.path.append("../../harness")


def get_instances(instance_path: str) -> list:
    """
    Get task instances from given path

    Args:
        instance_path (str): Path to task instances
    Returns:
        task_instances (list): List of task instances
    """
    if any([instance_path.endswith(x) for x in [".jsonl", ".jsonl.all"]]):
        task_instances = list()
        with open(instance_path) as f:
            for line in f.readlines():
                task_instances.append(json.loads(line))
        return task_instances

    with open(instance_path) as f:
        task_instances = json.load(f)
    return task_instances


PATH_TASKS_XARRAY = "../../collect/Q3/xarray-task-instances.jsonl"
PATH_TASKS_XARRAY_VERSIONED = "../../collect/Q3_versioned"

# Get raw xarray dataset
data_tasks = get_instances(PATH_TASKS_XARRAY)

# Get version to date from xarray home page
resp = requests.get("https://docs.xarray.dev/en/stable/whats-new.html")
pattern = (
    r'<a class="reference internal nav-link( active)?" href="#v(.*)">v(.*) \((.*)\)</a>'
)
matches = re.findall(pattern, resp.text)
matches = list(set(matches))
matches = [x[1:] for x in matches]

# Get (date, version) pairs
date_formats = ["%B %d %Y", "%d %B %Y"]
keep_major_minor = lambda x, sep: ".".join(x.strip().split(sep)[:2])

times = []
for match in matches:
    parts = match[0].split("-")
    version = keep_major_minor(".".join(parts[0:3]), ".")
    date_str = " ".join(parts[3:])

    for f_ in date_formats:
        try:
            date_obj = datetime.strptime(date_str, f_)
            times.append((date_obj.strftime("%Y-%m-%d"), version))
        except:
            continue
        break

times = sorted(times, key=lambda x: x[0])[::-1]

for task in data_tasks:
    created_at = task["created_at"].split("T")[0]
    found = False
    for t in times:
        if t[0] < created_at:
            task["version"] = t[1]
            found = True
            break
    if not found:
        task["version"] = None

# Save xarray versioned data to repository
with open(
    os.path.join(PATH_TASKS_XARRAY_VERSIONED, "xarray-task-instances_versions.jsonl"),
    "w",
) as f:
    for task in data_tasks:
        json.dump(task, f)
        f.write('\n')
