#!/usr/bin/env python3

"""Given the `<owner/name>` of a GitHub repo, this script writes the raw information for all the repo's PRs to a single `.jsonl` file."""

from __future__ import annotations

import argparse
import json
import logging
import os

from datetime import datetime
from fastcore.xtras import obj2dict
from swebench.collect.utils import Repo
from typing import Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def log_all_pulls(
        repo: Repo,
        output: str,
        max_pulls: int = None,
        cutoff_date: str = None,
    ) -> None:
    """
    Iterate over all pull requests in a repository and log them to a file

    Args:
        repo (Repo): repository object
        output (str): output file name
    """
    cutoff_date = datetime.strptime(cutoff_date, "%Y%m%d") \
        .strftime("%Y-%m-%dT%H:%M:%SZ") \
        if cutoff_date is not None else None

    with open(output, "w") as file:
        for i_pull, pull in enumerate(repo.get_all_pulls()):
            setattr(pull, "resolved_issues", repo.extract_resolved_issues(pull))
            print(json.dumps(obj2dict(pull)), end="\n", flush=True, file=file)
            if max_pulls is not None and i_pull >= max_pulls:
                break
            if cutoff_date is not None and pull.created_at < cutoff_date:
                break

def main(
        repo_name: str,
        output: str,
        token: Optional[str] = None,
        max_pulls: int = None,
        cutoff_date: str = None,
    ):
    """
    Logic for logging all pull requests in a repository

    Args:
        repo_name (str): name of the repository
        output (str): output file name
        token (str, optional): GitHub token
    """
    if token is None:
        token = os.environ.get("GITHUB_TOKEN")
    owner, repo = repo_name.split("/")
    repo = Repo(owner, repo, token=token)
    log_all_pulls(repo, output, max_pulls=max_pulls, cutoff_date=cutoff_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_name", type=str, help="Name of the repository")
    parser.add_argument("output", type=str, help="Output file name")
    parser.add_argument("--token", type=str, help="GitHub token")
    parser.add_argument("--max_pulls", type=int, help="Maximum number of pulls to log", default=None)
    parser.add_argument("--cutoff_date", type=str, help="Cutoff date for PRs to consider in format YYYYMMDD", default=None)
    args = parser.parse_args()
    main(**vars(args))
