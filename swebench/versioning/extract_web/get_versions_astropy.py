import json
import os
import re
import requests
import sys

from datetime import datetime

sys.path.append(os.path.abspath("../../harness"))


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


PATH_TASKS_ASTROPY = "../../collect/Q3/astropy-task-instances.jsonl"
PATH_TASKS_ASTROPY_VERSIONED = "../../collect/Q3_versioned"

# Get raw astropy dataset
data_tasks = get_instances(PATH_TASKS_ASTROPY)

# Get version to date from astropy homepage
resp = requests.get("https://docs.astropy.org/en/latest/changelog.html")
pattern = (
    r'<a class="reference internal nav-link" href="#version-(.*)">Version (.*)</a>'
)
matches = re.findall(pattern, resp.text)
matches = list(set(matches))

# Get (date, version) pairs
date_format = "%Y-%m-%d"
keep_major_minor = lambda x, sep: ".".join(x.strip().split(sep)[:2])

# Iterate through matches, construct (version, date) pairs
times = []
for match in matches:
    match_parts = match[1].split(" ")
    version, date = match_parts[0], match_parts[1].strip(")").strip("(")
    version = keep_major_minor(version, ".")
    date_obj = datetime.strptime(date, date_format)
    times.append((date_obj.strftime("%Y-%m-%d"), version))

# Group times by major/minor version
map_version_to_times = {}
for time in times:
    if time[1] not in map_version_to_times:
        map_version_to_times[time[1]] = []
    map_version_to_times[time[1]].append(time[0])

# Pick the most recent time as the version cut off date
version_to_time = [(k, max(v)) for k, v in map_version_to_times.items()]
version_to_time = sorted(version_to_time, key=lambda x: x[0])[::-1]

# Assign version to each task instance
for task in data_tasks:
    created_at = task["created_at"].split("T")[0]
    for t in version_to_time:
        found = False
        if t[1] < created_at:
            task["version"] = t[0]
            found = True
            break
    if not found:
        task["version"] = version_to_time[-1][0]

# Construct map of versions to task instances
map_v_to_t = {}
for task in data_tasks:
    if task["version"] not in map_v_to_t:
        map_v_to_t[task["version"]] = []
    map_v_to_t[task["version"]].append(t)

# Save astropy versioned data to repository
with open(
    os.path.join(
        PATH_TASKS_ASTROPY_VERSIONED,
        "astropy-task-instances_versions.jsonl",
    ),
    "w",
) as f:
    for task in data_tasks:
        json.dump(task, f)
        f.write("\n")
