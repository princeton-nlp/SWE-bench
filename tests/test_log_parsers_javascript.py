import json
from types import SimpleNamespace

import pytest

from swebench.harness.log_parsers.javascript import (
    parse_log_jest,
    parse_log_lighthouse,
    parse_log_prismjs,
)
from swebench.harness.constants import TestStatus


class TestParseLogJest:
    """Tests for parse_log_jest used by Jest-based JS/TS repos."""

    def test_parse_pass_and_fail(self):
        """Test parsing normal verbose Jest output."""
        log = """✓ adds two numbers (2 ms)
✕ subtracts two numbers
○ skipped test
"""
        result = parse_log_jest(log, test_spec=None)

        assert len(result) == 3
        assert result["adds two numbers"] == TestStatus.PASSED.value
        assert result["subtracts two numbers"] == TestStatus.FAILED.value
        assert result["skipped test"] == TestStatus.SKIPPED.value

    def test_same_test_name_stable_with_and_without_duration(self):
        """Jest only prints a "(N ms)" duration suffix above a small timing threshold,
        so the same test can appear with or without it across runs. The captured test
        name must be identical either way, otherwise it silently maps to two different
        dict keys and a real fail->pass transition can be missed."""
        with_duration = "✓ builds the correct query (105 ms)"
        without_duration = "✓ builds the correct query"

        result_with = parse_log_jest(with_duration, test_spec=None)
        result_without = parse_log_jest(without_duration, test_spec=None)

        assert list(result_with.keys()) == ["builds the correct query"]
        assert list(result_with.keys()) == list(result_without.keys())

    def test_strips_leading_and_trailing_whitespace(self):
        """Indentation from nested describe blocks shouldn't leak into the test name."""
        log = "    ✓ works when nested (3 ms)"
        result = parse_log_jest(log, test_spec=None)

        assert result == {"works when nested": TestStatus.PASSED.value}


@pytest.mark.parametrize(
    "parser,spec",
    [
        (parse_log_prismjs, None),
        (parse_log_lighthouse, SimpleNamespace(version="2.5")),
    ],
)
def test_mocha_json_parsers_find_every_report_amid_reordered_streams(parser, spec):
    def report(passes=(), failures=()):
        def test(name):
            return {"title": name, "fullTitle": name, "duration": 1, "err": {}}

        passed = [test(name) for name in passes]
        failed = [test(name) for name in failures]
        return json.dumps(
            {
                "stats": {"tests": len(passed) + len(failed)},
                "tests": passed + failed,
                "pending": [],
                "failures": failed,
                "passes": passed,
            },
            indent=2,
        )

    log = (
        'unrelated diff with braces: {"stats": definitely-not-json}\n'
        + report(passes=["first passes"])
        + "+ shell trace moved between streams\n"
        + report(passes=["second passes"], failures=["second fails"])
        + ">>>>> Test Exit Code: 1\n"
    )

    assert parser(log, spec) == {
        "first passes": TestStatus.PASSED.value,
        "second passes": TestStatus.PASSED.value,
        "second fails": TestStatus.FAILED.value,
    }
