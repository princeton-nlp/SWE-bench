import tarfile
from pathlib import Path, PurePosixPath

import pytest

from swebench import VettoContainer, VettoTaskRunner
from swebench.harness import docker_utils
from swebench.harness.run_evaluation import (
    get_parser,
    main as run_evaluation,
    run_instances,
)
from swebench.harness.vetto_adapter import (
    ExecResult,
    create_vetto_container,
)
from swebench.types import TestSpec

TestSpec.__test__ = False


def _make_dummy_test_spec(instance_id="sympy__sympy-20590"):
    return TestSpec(
        instance_id=instance_id,
        image="sweb.eval.x86_64.sympy__sympy-20590:latest",
        eval_script_list=["echo 1"],
        repo="sympy/sympy",
        version="1.7",
        FAIL_TO_PASS=[],
        PASS_TO_PASS=[],
    )


def test_vetto_container_lifecycle(tmp_path):
    workdir = tmp_path / "testbed"
    runner = VettoTaskRunner(workspace=workdir)
    test_spec = _make_dummy_test_spec()
    container = VettoContainer(runner=runner, test_spec=test_spec, workdir=workdir)

    assert container.id.startswith("vetto-sympy__sympy-20590-")
    assert "sweb.eval.sympy__sympy-20590" in container.name

    container.start()
    assert workdir.exists()
    assert (workdir / ".git").exists()

    # Lifecycle methods should not throw
    container.stop()
    container.remove()
    container.cleanup()


def test_vetto_container_custom_workspace_preservation(tmp_path):
    custom_ws = tmp_path / "my_project"
    custom_ws.mkdir()
    marker = custom_ws / "keep_me.txt"
    marker.write_text("important")

    runner = VettoTaskRunner(workspace=custom_ws)
    container = VettoContainer(runner=runner, workdir=custom_ws)
    container.start()

    # Artifacts exist in temp root dir, not in custom workspace
    assert container.root_dir != container.workdir
    assert container.patch_file.parent.exists()

    # Cleanup should remove temp root dir but preserve custom workspace
    container.cleanup()
    assert not container.root_dir.exists()
    assert custom_ws.exists()
    assert marker.read_text() == "important"


def test_vetto_container_copy_to_and_archive(tmp_path):
    workdir = tmp_path / "testbed"
    runner = VettoTaskRunner(workspace=workdir)
    container = VettoContainer(runner=runner, workdir=workdir)
    container.start()

    # 1. Test patch copying
    patch_file = tmp_path / "sample.diff"
    patch_file.write_text("--- a/f\n+++ b/f\n@@ -1 +1 @@\n-1\n+2\n")
    container.copy_to(patch_file, PurePosixPath("/tmp/patch.diff"))
    assert container.patch_file.exists()
    assert container.patch_file.read_text() == patch_file.read_text()

    # 2. Test eval.sh copying and path rewriting
    eval_src = tmp_path / "eval.sh"
    eval_src.write_text(
        "source /opt/miniconda3/bin/activate\ncd /testbed\ngit apply /tmp/patch.diff\ncp /image_assets/test.png .\n"
    )
    container.copy_to(eval_src, PurePosixPath("/eval.sh"))
    assert container.eval_script_path.exists()
    rewritten = container.eval_script_path.read_text()
    assert f"cd {container.workdir}" in rewritten
    assert f"git apply {container.patch_file}" in rewritten
    assert str(container.assets_dir) in rewritten
    # Ensure miniconda activation is guarded when absent
    if not Path("/opt/miniconda3/bin/activate").exists():
        assert "test -f /opt/miniconda3/bin/activate" in rewritten

    # 3. Test image asset copying
    asset_file = tmp_path / "baseline.png"
    asset_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    container.copy_to(asset_file, PurePosixPath("/image_assets/baseline.png"))
    assert (container.assets_dir / "baseline.png").exists()

    # 4. Test put_archive
    tar_archive = tmp_path / "archive.tar"
    dummy_data = tmp_path / "hello.txt"
    dummy_data.write_text("world")
    with tarfile.open(tar_archive, "w") as tar:
        tar.add(dummy_data, arcname="hello.txt")
    container.put_archive("/data", tar_archive.read_bytes())
    assert (container.root_dir / "data" / "hello.txt").exists()

    container.cleanup()


def test_vetto_container_exec_run(tmp_path):
    workdir = tmp_path / "testbed"
    workdir.mkdir(parents=True, exist_ok=True)
    runner = VettoTaskRunner(workspace=workdir)
    container = VettoContainer(runner=runner, workdir=workdir)
    container.start()

    # Run command and test ExecResult namedtuple properties
    res = container.exec_run(["echo", "hello_vetto"])
    assert isinstance(res, ExecResult)
    assert res.exit_code == 0
    assert b"hello_vetto" in res.output

    # Test tuple unpacking compatibility
    code, output = res
    assert code == 0
    assert b"hello_vetto" in output

    container.cleanup()


def test_vetto_container_exec_run_path_translation(tmp_path):
    workdir = tmp_path / "testbed"
    workdir.mkdir(parents=True, exist_ok=True)
    runner = VettoTaskRunner(workspace=workdir)
    container = VettoContainer(runner=runner, workdir=workdir)
    container.start()

    # Test that /testbed in command string is translated
    res_str = container.exec_run("echo /testbed")
    assert str(workdir).encode() in res_str.output

    # Test that /testbed in command list is translated
    res_list = container.exec_run(["echo", "/testbed"])
    assert str(workdir).encode() in res_list.output

    container.cleanup()


def test_vetto_container_exec_run_with_timeout(tmp_path):
    workdir = tmp_path / "testbed"
    workdir.mkdir(parents=True, exist_ok=True)
    runner = VettoTaskRunner(workspace=workdir)
    container = VettoContainer(runner=runner, workdir=workdir)
    container.start()

    out, timed_out, duration = container.exec_run_with_timeout(
        ["echo", "timeout_test"], timeout=10
    )
    assert "timeout_test" in out
    assert not timed_out
    assert duration >= 0.0

    container.cleanup()


def test_docker_utils_hooks_with_vetto_container(tmp_path):
    workdir = tmp_path / "testbed"
    workdir.mkdir(parents=True, exist_ok=True)
    runner = VettoTaskRunner(workspace=workdir)
    container = VettoContainer(runner=runner, workdir=workdir)
    container.start()

    # Verify copy_to_container dispatches to container.copy_to
    src = tmp_path / "test_file.diff"
    src.write_text("test diff content")
    docker_utils.copy_to_container(container, src, PurePosixPath("/tmp/patch.diff"))
    assert container.patch_file.exists()

    # Verify exec_run_with_timeout dispatches to container.exec_run_with_timeout
    out, timed_out, _ = docker_utils.exec_run_with_timeout(
        container, ["echo", "dispatched_run"], timeout=5
    )
    assert "dispatched_run" in out
    assert not timed_out

    # Verify cleanup_container dispatches to container.cleanup
    cleaned = False
    original_cleanup = container.cleanup

    def mock_cleanup():
        nonlocal cleaned
        cleaned = True
        original_cleanup()

    container.cleanup = mock_cleanup
    docker_utils.cleanup_container(None, container, None)
    assert cleaned


def test_vetto_task_runner_find_binary(monkeypatch, tmp_path):
    custom_bin = tmp_path / "fake_vetto"
    custom_bin.write_text("#!/bin/sh\nexit 0\n")
    custom_bin.chmod(0o755)

    # 1. Custom bin argument
    found = VettoTaskRunner._find_vetto_binary(custom_bin=str(custom_bin))
    assert found == str(custom_bin)

    # 2. VETTO_BIN env var
    monkeypatch.setenv("VETTO_BIN", str(custom_bin))
    found_env = VettoTaskRunner._find_vetto_binary()
    assert found_env == str(custom_bin)

    # 3. None when missing
    monkeypatch.delenv("VETTO_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    found_none = VettoTaskRunner._find_vetto_binary()
    assert found_none is None


def test_create_vetto_container_factory(tmp_path, monkeypatch):
    test_spec = _make_dummy_test_spec()
    workdir = tmp_path / "factory_ws"
    container = create_vetto_container(
        test_spec=test_spec,
        run_id="factory-run",
        workspace=workdir,
    )
    assert isinstance(container, VettoContainer)
    assert container.test_spec == test_spec
    assert container.run_id == "factory-run"
    assert container.workdir == workdir
    container.cleanup()

    # Check env var fallback
    monkeypatch.setenv("VETTO_WORKSPACE", str(workdir))
    container_env = create_vetto_container(
        test_spec=test_spec,
        run_id="factory-run-env",
    )
    assert container_env.workdir == workdir
    container_env.cleanup()


def test_cli_parser_runtime_and_workspace_options():
    parser = get_parser()

    args_default = parser.parse_args(["-p", "gold", "-id", "default-run"])
    assert args_default.runtime == "docker"
    assert args_default.workspace is None

    args_vetto = parser.parse_args(
        [
            "-p",
            "gold",
            "-id",
            "vetto-run",
            "--runtime",
            "vetto",
            "--workspace",
            "/tmp/ws",
        ]
    )
    assert args_vetto.runtime == "vetto"
    assert args_vetto.workspace == "/tmp/ws"


def test_guard_modal_and_vetto():
    with pytest.raises(ValueError, match="Cannot combine --modal with --runtime vetto"):
        run_evaluation(
            dataset_name="SWE-bench/SWE-bench_Lite",
            split="test",
            instance_ids=["test__1"],
            predictions_path="gold",
            max_workers=1,
            open_file_limit=4096,
            run_id="guard-test",
            timeout=60,
            rewrite_reports=False,
            modal=True,
            runtime="vetto",
        )


def test_public_api_exports():
    import swebench

    assert hasattr(swebench, "VettoContainer")
    assert hasattr(swebench, "VettoTaskRunner")
    assert "VettoContainer" in swebench.__all__
    assert "VettoTaskRunner" in swebench.__all__


def test_run_instances_signature_backward_compatibility():
    import inspect

    sig = inspect.signature(run_instances)
    params = list(sig.parameters.keys())

    # Verify original positional order
    expected_prefix = [
        "predictions",
        "instances",
        "max_workers",
        "run_id",
        "timeout",
        "rewrite_reports",
        "skip_patch",
        "task_repo",
        "runtime",
        "workspace",
        "client",
    ]
    assert params == expected_prefix
