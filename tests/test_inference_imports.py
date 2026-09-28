"""Optional legacy SDK exports must not prevent importing current API routes."""

import subprocess
import sys

import pytest

pytest.importorskip("anthropic")
pytest.importorskip("openai")
pytest.importorskip("tiktoken")


def test_run_api_imports_without_legacy_anthropic_prompt_constants():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import anthropic; "
            "[delattr(anthropic, name) for name in ('HUMAN_PROMPT', 'AI_PROMPT') "
            "if hasattr(anthropic, name)]; "
            "from swebench.inference import run_api; "
            "assert callable(run_api.call_chat); "
            "assert callable(run_api.call_litellm)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
