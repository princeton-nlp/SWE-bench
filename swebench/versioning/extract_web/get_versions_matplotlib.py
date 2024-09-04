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


PATH_TASKS_MATPLOTLIB = "../../collect/Q3/matplotlib-task-instances.jsonl"
PATH_TASKS_MATPLOTLIB_VERSIONED = "../../collect/Q3_versioned"

# Get raw matplotlib dataset
data_tasks = get_instances(PATH_TASKS_MATPLOTLIB)

# Get version to date from matplotlib home page
resp = requests.get("https://matplotlib.org/stable/users/release_notes#past-versions")
pattern = r'<a class="reference internal" href="prev_whats_new/whats_new_(.*).html">What\'s new in Matplotlib (.*)</a>'
matches = re.findall(pattern, resp.text)
matches = list(set(matches))

# Get (date, version) pairs
date_format = "%b %d, %Y"
keep_major_minor = lambda x, sep: ".".join(x.strip().split(sep)[:2])

times = []
for match in matches:
    version, s = match[0], match[1]
    if "(" not in s:
        continue
    version = keep_major_minor(version, ".")
    date_string = s[s.find("(") + 1 : s.find(")")]
    date_obj = datetime.strptime(date_string.replace("Sept", "Sep"), date_format)
    times.append((date_obj.strftime("%Y-%m-%d"), version))
times = sorted(times, key=lambda x: x[0])[::-1]

for task in data_tasks:
    created_at = task["created_at"].split("T")[0]
    for t in times:
        if t[0] < created_at:
            task["version"] = t[1]
            break

# Construct map of versions to task instances
map_v_to_t = {}
for t in data_tasks:
    if t["version"] not in map_v_to_t:
        map_v_to_t[t["version"]] = []
    map_v_to_t[t["version"]].append(t)

# Save matplotlib versioned data to repository
with open(
    os.path.join(PATH_TASKS_MATPLOTLIB_VERSIONED, "matplotlib-task-instances_versions.jsonl"),
    "w",
) as f:
    for t in data_tasks:
        json.dump(t, f)
        f.write("\n")