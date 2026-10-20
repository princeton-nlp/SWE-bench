"""Post-hoc classification of infrastructure failures (#586).

Separates "the environment broke" from "the model's patch was wrong" using
signatures in logs the harness already writes, so a broken image is not silently
counted as a model failure.

Two properties are deliberate:

1. Classification is post-hoc and read-only. It never runs commands in a
   container and never decides whether an instance gets evaluated, so it cannot
   drop an instance from a run.
2. It is advisory. A flagged instance stays in `unresolved_ids` / `error_ids`
   exactly as before, so the scoring denominator is unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

# Cannot plausibly be caused by patching repository source.
TIER_ENVIRONMENT = "environment"
# Can come from either a broken environment or a bad patch; reported separately
# so it is never mistaken for a confirmed environment fault.
TIER_AMBIGUOUS = "ambiguous"

# (reason, tier, pattern), matched in order; the first hit wins.
INFRA_FAILURE_SIGNATURES: tuple[tuple[str, str, str], ...] = (
    (
        "browser_launch_failed",
        TIER_ENVIRONMENT,
        r"Failed to launch|Failed to connect to the bus",
    ),
    (
        "display_unavailable",
        TIER_ENVIRONMENT,
        r"cannot open display|Missing X server|unable to open X display",
    ),
    (
        "out_of_memory",
        TIER_ENVIRONMENT,
        r"Cannot allocate memory|OutOfMemoryError|^Killed$",
    ),
    (
        "container_unavailable",
        TIER_ENVIRONMENT,
        r"Error response from daemon|Cannot connect to the Docker daemon",
    ),
    (
        "network_unreachable",
        TIER_ENVIRONMENT,
        r"Could not resolve host|Temporary failure in name resolution",
    ),
    (
        "missing_module",
        TIER_AMBIGUOUS,
        r"Cannot find module|MODULE_NOT_FOUND|ModuleNotFoundError",
    ),
    ("no_tests_collected", TIER_AMBIGUOUS, r"no tests ran|collected 0 items"),
    ("tests_timed_out", TIER_AMBIGUOUS, r"Timeout error: \d+ seconds exceeded"),
)

_COMPILED = tuple(
    (reason, tier, re.compile(pattern, re.MULTILINE))
    for reason, tier, pattern in INFRA_FAILURE_SIGNATURES
)

# Pytest's own tests can print an empty inner run before the outer summary (#683).
# Only a later final summary with nonzero test outcomes overrides that advisory.
_PYTEST_SUMMARY = re.compile(
    r"^=+ (?P<result>[^\r\n]+) in \d+(?:\.\d+)?s(?: \([^\r\n]*\))? =+[ \t\r]*$",
    re.MULTILINE,
)
_PYTEST_OUTCOMES = re.compile(r"\b[1-9]\d* (?:passed|failed|skipped|xfailed|xpassed)\b")


def _pytest_ran_after(text: str, offset: int) -> bool:
    last_summary = None
    for summary in _PYTEST_SUMMARY.finditer(text, offset):
        last_summary = summary
    return bool(last_summary and _PYTEST_OUTCOMES.search(last_summary["result"]))


def classify_text(text: str) -> tuple[str, str] | None:
    """Return (reason, tier) for the first matching signature, else None."""
    if not text:
        return None
    for reason, tier, pattern in _COMPILED:
        if pattern.search(text):
            if reason == "no_tests_collected":
                last_empty_end = max(match.end() for match in pattern.finditer(text))
                if _pytest_ran_after(text, last_empty_end):
                    continue
            return reason, tier
    return None


def classify_logs(*log_paths: str | Path) -> tuple[str, str] | None:
    """Classify the concatenated contents of whichever log paths exist."""
    chunks = []
    for log_path in log_paths:
        path = Path(log_path)
        if path.exists():
            chunks.append(path.read_text(errors="replace"))
    return classify_text("\n".join(chunks))
