"""Network isolation and private dependency-cache wiring for local graders."""

import io
import hashlib
import json
import tarfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import docker
import pytest
from typer.testing import CliRunner

from swebench.cli.cli import app
from swebench.harness import run_evaluation
from swebench.harness.constants import END_TEST_OUTPUT, START_TEST_OUTPUT
from swebench.harness.docker_utils import copy_to_container
from swebench.harness.grading import get_eval_report
from swebench.image_builder import docker_build
from swebench.image_builder.image_spec import (
    ImageSpec,
    canonical_image_ref,
    image_namespace_and_tag,
)
from swebench.task.repo import asset_path
from swebench.types import TestSpec as EvaluationSpec


def _test_spec(instance_id: str = "owner__repo-1") -> EvaluationSpec:
    return EvaluationSpec(
        instance_id=instance_id,
        image="example.invalid/swebench/test:latest",
        eval_script_list=["true"],
        repo="owner/repo",
        version="1",
        FAIL_TO_PASS=[],
        PASS_TO_PASS=[],
    )


def _docker_client():
    client = MagicMock()
    image = MagicMock()
    image.id = "sha256:" + "a" * 64
    client.images.get.return_value = image
    client.containers.get.side_effect = docker.errors.NotFound("not found")
    container = MagicMock()
    container.id = "container-id"
    client.containers.create.return_value = container
    return client, container


def _write_bundle(root, instance_id="owner__repo-1", manager="npm"):
    bundle = root / instance_id
    (bundle / manager).mkdir(parents=True)
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "instance_id": instance_id,
                "image_digest": "sha256:" + "a" * 64,
                "manager": manager,
            }
        )
    )
    return bundle


def test_copy_to_container_normalizes_host_ownership(tmp_path):
    source = tmp_path / "eval.sh"
    source.write_text("true\n")
    container = MagicMock()

    copy_to_container(container, source, tmp_path / "inside" / "eval.sh")

    archive = container.put_archive.call_args.args[1]
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        member = tar.getmember("eval.sh")
    assert member.uid == member.gid == 0
    assert member.uname == member.gname == "root"


def test_create_container_has_no_network_by_default():
    client, container = _docker_client()

    result = run_evaluation.create_container(_test_spec(), client, "run", MagicMock())

    assert result is container
    kwargs = client.containers.create.call_args.kwargs
    assert kwargs["image"] == "sha256:" + "a" * 64
    assert kwargs["network_mode"] == "none"
    assert "volumes" not in kwargs


def test_create_container_network_requires_explicit_opt_in():
    client, _ = _docker_client()

    run_evaluation.create_container(
        _test_spec(), client, "run", MagicMock(), allow_network=True
    )

    assert "network_mode" not in client.containers.create.call_args.kwargs


def test_task_repo_container_never_pulls_a_missing_image():
    client, _ = _docker_client()
    client.images.get.side_effect = docker.errors.ImageNotFound("missing")

    with pytest.raises(run_evaluation.EvaluationError, match="local image is missing"):
        run_evaluation.create_container(
            _test_spec(), client, "run", MagicMock(), pull_missing=False
        )

    client.images.pull.assert_not_called()


def test_instance_bundle_is_mounted_read_only_at_expected_paths(tmp_path):
    spec = _test_spec()
    bundle = _write_bundle(tmp_path, spec.instance_id)
    client, _ = _docker_client()

    run_evaluation.create_container(
        spec, client, "run", MagicMock(), offline_deps_dir=tmp_path
    )

    kwargs = client.containers.create.call_args.kwargs
    assert kwargs["network_mode"] == "none"
    assert kwargs["volumes"] == {
        str(bundle.resolve()): {
            "bind": "/run/swebench-offline-seed",
            "mode": "ro,z",
        }
    }


def test_read_only_seed_is_copied_to_a_writable_per_container_cache():
    container = MagicMock()
    container.exec_run.return_value.exit_code = 0
    logger = MagicMock()

    run_evaluation._prepare_offline_deps(container, "owner__repo-1", logger)

    command = container.exec_run.call_args.args[0]
    assert command[:2] == ["/bin/bash", "-c"]
    assert "cp -a /run/swebench-offline-seed/. /run/swebench-offline/" in command[2]
    assert "chmod -R a+rwX /run/swebench-offline" in command[2]
    assert container.exec_run.call_args.kwargs["user"] == "root"


def test_failure_to_stage_offline_cache_is_an_infrastructure_error():
    container = MagicMock()
    container.exec_run.return_value.exit_code = 1
    container.exec_run.return_value.output = b"no space left"

    with pytest.raises(run_evaluation.EvaluationError, match="no space left"):
        run_evaluation._prepare_offline_deps(
            container, "owner__repo-1", MagicMock(log_file="run.log")
        )


def test_solver_visible_image_rejects_baked_grading_material():
    container = MagicMock()
    container.exec_run.return_value.exit_code = 0
    container.exec_run.return_value.output = b"/swebench/image_assets\n/gold.patch\n"

    with pytest.raises(
        run_evaluation.EvaluationError, match="forbidden grading material"
    ):
        run_evaluation._assert_no_baked_grading_material(
            container, "owner__repo-1", MagicMock(log_file="run.log")
        )


def test_solver_visible_image_preflight_accepts_clean_image():
    container = MagicMock()
    container.exec_run.return_value.exit_code = 0
    container.exec_run.return_value.output = b""

    run_evaluation._assert_no_baked_grading_material(
        container, "owner__repo-1", MagicMock(log_file="run.log")
    )


def test_offline_asset_resolution_never_falls_back_to_url(monkeypatch, tmp_path):
    (tmp_path / "tasks").mkdir()
    asset = {
        "instance_id": "owner__repo-1",
        "path": "expected.png",
        "url": "https://example.invalid/expected.png",
    }
    urlopen = MagicMock(side_effect=AssertionError("network fallback used"))
    monkeypatch.setattr(run_evaluation.urllib.request, "urlopen", urlopen)

    result = run_evaluation._resolve_asset_bytes(
        asset, str(tmp_path), MagicMock(), allow_network=False
    )

    assert result is None
    urlopen.assert_not_called()


def test_asset_resolution_rejects_non_http_url(monkeypatch):
    urlopen = MagicMock(side_effect=AssertionError("unsafe URL was opened"))
    monkeypatch.setattr(run_evaluation.urllib.request, "urlopen", urlopen)

    result = run_evaluation._resolve_asset_bytes(
        {
            "instance_id": "owner__repo-1",
            "path": "expected.png",
            "url": "file:///etc/passwd",
        },
        None,
        MagicMock(),
    )

    assert result is None
    urlopen.assert_not_called()


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "bad\npath"])
def test_asset_path_is_validated_without_a_task_repo(path):
    with pytest.raises(ValueError, match="asset path"):
        run_evaluation._resolve_asset_bytes(
            {"instance_id": "owner__repo-1", "path": path, "url": "https://x"},
            None,
            MagicMock(),
        )


def test_missing_local_asset_is_an_offline_infrastructure_error(tmp_path):
    (tmp_path / "tasks").mkdir()
    spec = _test_spec()
    spec.image_assets = {
        "test_patch": [
            {"path": "expected.png", "url": "https://example.invalid/expected.png"}
        ]
    }

    with pytest.raises(
        run_evaluation.EvaluationError, match="Missing local binary grading asset"
    ):
        run_evaluation._stage_image_assets(
            MagicMock(),
            spec,
            tmp_path / "logs",
            MagicMock(log_file="run.log"),
            task_repo=str(tmp_path),
            allow_network=False,
        )


def test_failed_remote_asset_is_always_an_infrastructure_error(monkeypatch, tmp_path):
    spec = _test_spec()
    spec.image_assets = {
        "test_patch": [
            {"path": "expected.png", "url": "https://example.invalid/expected.png"}
        ]
    }
    monkeypatch.setattr(run_evaluation, "_resolve_asset_bytes", lambda *a, **k: None)

    with pytest.raises(
        run_evaluation.EvaluationError, match="Missing local or remote binary"
    ):
        run_evaluation._stage_image_assets(
            MagicMock(),
            spec,
            tmp_path / "logs",
            MagicMock(log_file="run.log"),
            allow_network=True,
        )


def test_asset_path_rejects_escape_from_private_task_directory(tmp_path):
    (tmp_path / "tasks").mkdir()
    with pytest.raises(ValueError, match="escapes its test_assets directory"):
        asset_path(tmp_path, "owner__repo-1", "../../secret")


def test_asset_path_rejects_instance_id_traversal(tmp_path):
    (tmp_path / "tasks").mkdir()
    with pytest.raises(ValueError, match="Unsafe instance ID"):
        asset_path(tmp_path, "../outside", "secret")


def test_asset_restore_shell_quotes_repository_path(monkeypatch, tmp_path):
    spec = _test_spec()
    spec.image_assets = {
        "test_patch": [
            {"path": "fixtures/file name.png", "url": "https://example.invalid/x"}
        ]
    }
    monkeypatch.setattr(run_evaluation, "_resolve_asset_bytes", lambda *a, **k: b"png")
    monkeypatch.setattr(run_evaluation, "copy_to_container", MagicMock())

    restore = run_evaluation._stage_image_assets(
        MagicMock(), spec, tmp_path / "logs", MagicMock(), allow_network=False
    )

    assert restore == [
        '{ mkdir -p -- "$(dirname -- \'fixtures/file name.png\')" && '
        "cp -- /image_assets/'fixtures__file name.png' 'fixtures/file name.png'; } || "
        "{ echo 'failed to restore binary grading asset' >&2; exit 1; }"
    ]


def test_candidate_and_no_patch_runs_do_not_stage_gold_patch_assets(
    monkeypatch, tmp_path
):
    spec = _test_spec()
    spec.image_assets = {
        "test_patch": [{"path": "expected.png", "url": "https://example/x"}],
        "patch": [{"path": "gold-only.png", "url": "https://example/y"}],
    }
    monkeypatch.setattr(run_evaluation, "_resolve_asset_bytes", lambda *a, **k: b"png")
    monkeypatch.setattr(run_evaluation, "copy_to_container", MagicMock())

    candidate = run_evaluation._stage_image_assets(
        MagicMock(), spec, tmp_path / "candidate", MagicMock()
    )
    gold = run_evaluation._stage_image_assets(
        MagicMock(),
        spec,
        tmp_path / "gold",
        MagicMock(),
        include_patch_assets=True,
    )

    assert len(candidate) == 1
    assert "gold-only.png" not in candidate[0]
    assert len(gold) == 2
    assert any("gold-only.png" in command for command in gold)


def test_prepared_eval_merges_output_streams_before_any_shell_trace():
    script = "#!/bin/bash\nset -ux\n: '>>>>> Start Test Output'\ntrue\n"

    prepared = run_evaluation._inject_asset_restore(script, ["cp fixture expected"])

    assert prepared.splitlines()[:3] == ["#!/bin/bash", "exec 2>&1", "set -ux"]
    assert prepared.index("cp fixture expected") < prepared.index(">>>>> Start Test Output")
    assert run_evaluation._inject_asset_restore(prepared, []) == prepared


def test_sparse_store_allows_an_instance_without_a_bundle(tmp_path):
    assert run_evaluation._offline_deps_bundle_path(tmp_path, "owner__repo-1") is None

    client, _ = _docker_client()
    run_evaluation.create_container(
        _test_spec(), client, "run", MagicMock(), offline_deps_dir=tmp_path
    )
    assert "volumes" not in client.containers.create.call_args.kwargs


def test_task_repo_declares_only_required_private_bundles(tmp_path):
    metadata = {
        "schema_version": 1,
        "instances": {"owner__repo-1": {"manager": "npm", "mode": "install"}},
    }
    (tmp_path / "offline_dependencies.json").write_text(json.dumps(metadata))

    assert run_evaluation._required_offline_deps(tmp_path) == {"owner__repo-1"}
    assert run_evaluation._required_offline_deps(None) == set()


def test_only_root_package_manifest_diff_needs_dependency_bundle():
    assert run_evaluation._patch_changes_root_package_json(
        "diff --git a/package.json b/package.json\n--- a/package.json\n"
    )
    assert not run_evaluation._patch_changes_root_package_json(
        "diff --git a/packages/demo/package.json b/packages/demo/package.json\n"
    )
    assert not run_evaluation._patch_changes_root_package_json(
        "diff --git a/src/index.js b/src/index.js\n"
    )


def test_non_directory_bundle_entry_is_rejected(tmp_path):
    (tmp_path / "owner__repo-1").write_text("not a bundle")

    with pytest.raises(ValueError, match="is not a directory"):
        run_evaluation._offline_deps_bundle_path(tmp_path, "owner__repo-1")


def test_bundle_lookup_rejects_instance_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="Unsafe instance ID"):
        run_evaluation._offline_deps_bundle_path(tmp_path, "../secret")


def test_bundle_lookup_rejects_symlink_outside_private_root(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    outside = tmp_path / "secret"
    outside.mkdir()
    (root / "owner__repo-1").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes its root"):
        run_evaluation._offline_deps_bundle_path(root, "owner__repo-1")


def test_conflict_retry_keeps_network_and_mount_restrictions(tmp_path):
    spec = _test_spec()
    bundle = _write_bundle(tmp_path, spec.instance_id)
    client, container = _docker_client()
    client.containers.create.side_effect = [
        docker.errors.APIError("409 Conflict"),
        container,
    ]

    run_evaluation.create_container(
        spec, client, "run", MagicMock(), offline_deps_dir=tmp_path
    )

    assert client.containers.create.call_count == 2
    first, second = [call.kwargs for call in client.containers.create.call_args_list]
    assert first["network_mode"] == second["network_mode"] == "none"
    assert first["volumes"] == second["volumes"]


def test_bundle_digest_must_match_container_image(tmp_path):
    spec = _test_spec()
    bundle = _write_bundle(tmp_path, spec.instance_id)
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["image_digest"] = "sha256:" + "b" * 64
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    client, _ = _docker_client()

    with pytest.raises(run_evaluation.EvaluationError, match="does not match"):
        run_evaluation.create_container(
            spec, client, "run", MagicMock(), offline_deps_dir=tmp_path
        )


def test_bundle_provenance_binds_gold_patch_and_dependency_config(tmp_path):
    instance_id = "owner__repo-1"
    repo = tmp_path / "repo"
    task_dir = repo / "tasks" / instance_id
    task_dir.mkdir(parents=True)
    gold_patch = b"diff --git a/package.json b/package.json\n"
    (task_dir / "gold.patch").write_bytes(gold_patch)
    dependency_config = {"manager": "npm", "mode": "install"}
    (repo / "offline_dependencies.json").write_text(
        json.dumps(
            {"schema_version": 1, "instances": {instance_id: dependency_config}}
        )
    )
    store = tmp_path / "store"
    bundle = _write_bundle(store, instance_id)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["gold_patch_sha256"] = hashlib.sha256(gold_patch).hexdigest()
    manifest["dependency_config_sha256"] = hashlib.sha256(
        json.dumps(
            dependency_config, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    spec = _test_spec(instance_id)

    run_evaluation._validate_offline_deps_bundle(
        bundle, spec, "sha256:" + "a" * 64, task_repo=repo
    )

    (task_dir / "gold.patch").write_text("changed")
    with pytest.raises(ValueError, match="gold patch is stale"):
        run_evaluation._validate_offline_deps_bundle(
            bundle, spec, "sha256:" + "a" * 64, task_repo=repo
        )

    (task_dir / "gold.patch").write_bytes(gold_patch)
    dependency_config["mode"] = "ci"
    (repo / "offline_dependencies.json").write_text(
        json.dumps(
            {"schema_version": 1, "instances": {instance_id: dependency_config}}
        )
    )
    with pytest.raises(ValueError, match="configuration is stale"):
        run_evaluation._validate_offline_deps_bundle(
            bundle, spec, "sha256:" + "a" * 64, task_repo=repo
        )


def test_reuse_images_rejects_a_missing_local_image(monkeypatch, tmp_path):
    client = MagicMock()
    client.images.get.side_effect = docker.errors.ImageNotFound("missing")
    monkeypatch.setattr(run_evaluation, "make_test_spec", lambda _: _test_spec())
    task_dir = tmp_path / "tasks" / "owner__repo-1"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("instance_id: owner__repo-1\n")
    (task_dir / "Dockerfile").write_text("FROM scratch\n")

    with pytest.raises(RuntimeError, match="requires every task image"):
        run_evaluation._require_local_images(
            [{"instance_id": "owner__repo-1"}], client, tmp_path
        )


def test_reuse_images_rejects_stale_build_inputs(monkeypatch, tmp_path):
    spec = _test_spec()
    monkeypatch.setattr(run_evaluation, "make_test_spec", lambda _: spec)
    task_dir = tmp_path / "tasks" / spec.instance_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(f"instance_id: {spec.instance_id}\n")
    (task_dir / "Dockerfile").write_text("FROM scratch\n")
    client, _ = _docker_client()
    client.images.get.return_value.attrs = {
        "Config": {"Labels": {"org.swebench.build-input-sha256": "stale"}}
    }

    with pytest.raises(RuntimeError, match="not built from the current task"):
        run_evaluation._require_local_images(
            [{"instance_id": spec.instance_id}], client, tmp_path
        )


def test_run_instances_threads_offline_options_to_each_worker(monkeypatch, tmp_path):
    captured = {}
    spec = _test_spec()
    monkeypatch.setattr(run_evaluation, "_docker_client", MagicMock())
    monkeypatch.setattr(run_evaluation, "make_test_spec", lambda _: spec)

    def fake_threadpool(func, payloads, workers):
        captured["func"] = func
        captured["payloads"] = payloads
        captured["workers"] = workers

    monkeypatch.setattr(run_evaluation, "run_threadpool", fake_threadpool)

    run_evaluation.run_instances(
        {spec.instance_id: {"instance_id": spec.instance_id}},
        [{"instance_id": spec.instance_id}],
        2,
        "run",
        30,
        allow_network=True,
        offline_deps_dir=tmp_path,
    )

    assert captured["func"] is run_evaluation.run_instance
    assert captured["workers"] == 2
    assert captured["payloads"][0][-3:] == (True, tmp_path, True)


def test_main_threads_offline_options_and_preflights_bundle(monkeypatch, tmp_path):
    instance_id = "owner__repo-1"
    (tmp_path / "store" / instance_id).mkdir(parents=True)
    instance = {"instance_id": instance_id}
    prediction = {
        "instance_id": instance_id,
        "model_name_or_path": "gold",
        "model_patch": "patch",
    }
    run_instances = MagicMock()
    monkeypatch.setattr(run_evaluation, "RUN_EVALUATION_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        run_evaluation, "get_predictions_from_file", lambda *a, **k: [prediction]
    )
    monkeypatch.setattr(
        run_evaluation, "get_dataset_from_preds", lambda *a, **k: [instance]
    )
    monkeypatch.setattr(run_evaluation, "load_instances", lambda *a, **k: [instance])
    monkeypatch.setattr(run_evaluation.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(run_evaluation, "_docker_client", MagicMock())
    monkeypatch.setattr(run_evaluation, "_require_local_images", MagicMock())
    monkeypatch.setattr(run_evaluation, "run_instances", run_instances)
    monkeypatch.setattr(run_evaluation, "make_run_report", MagicMock())

    run_evaluation.main(
        dataset_name="org/dataset",
        split="test",
        instance_ids=[instance_id],
        predictions_path="gold",
        max_workers=1,
        open_file_limit=4096,
        run_id="offline",
        timeout=30,
        rewrite_reports=False,
        modal=False,
        task_repo=str(tmp_path),
        reuse_images=True,
        allow_network=True,
        offline_deps_dir=tmp_path / "store",
    )

    kwargs = run_instances.call_args.kwargs
    assert kwargs["allow_network"] is True
    assert kwargs["offline_deps_dir"] == str((tmp_path / "store").resolve())


def test_required_task_repo_bundle_cannot_be_bypassed_with_network(monkeypatch, tmp_path):
    instance_id = "owner__repo-1"
    (tmp_path / "offline_dependencies.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "instances": {
                    instance_id: {"manager": "npm", "mode": "install"}
                },
            }
        )
    )
    instance = {"instance_id": instance_id}
    prediction = {
        "instance_id": instance_id,
        "model_name_or_path": "gold",
        "model_patch": "diff --git a/package.json b/package.json\n",
    }
    monkeypatch.setattr(run_evaluation, "RUN_EVALUATION_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        run_evaluation, "get_predictions_from_file", lambda *a, **k: [prediction]
    )
    monkeypatch.setattr(
        run_evaluation, "get_dataset_from_preds", lambda *a, **k: [instance]
    )
    monkeypatch.setattr(run_evaluation, "load_instances", lambda *a, **k: [instance])
    monkeypatch.setattr(run_evaluation.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(run_evaluation, "_docker_client", MagicMock())

    with pytest.raises(ValueError, match="Dependency bundles are required"):
        run_evaluation.main(
            dataset_name="org/dataset",
            split="test",
            instance_ids=[instance_id],
            predictions_path="gold",
            max_workers=1,
            open_file_limit=4096,
            run_id="connected-but-cache-required",
            timeout=30,
            rewrite_reports=False,
            modal=False,
            task_repo=str(tmp_path),
            allow_network=True,
        )


def test_source_only_prediction_does_not_require_gold_dependency_bundle(
    monkeypatch, tmp_path
):
    instance_id = "owner__repo-1"
    (tmp_path / "offline_dependencies.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "instances": {
                    instance_id: {"manager": "npm", "mode": "install"}
                },
            }
        )
    )
    instance = {"instance_id": instance_id}
    prediction = {
        "instance_id": instance_id,
        "model_name_or_path": "candidate",
        "model_patch": "diff --git a/src/a.js b/src/a.js\n",
        # Both are reserved internal fields; a prediction file must not control them.
        "reference_patch": True,
        "skip_patch": True,
    }
    run_instances = MagicMock()
    monkeypatch.setattr(run_evaluation, "RUN_EVALUATION_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        run_evaluation, "get_predictions_from_file", lambda *a, **k: [prediction]
    )
    monkeypatch.setattr(
        run_evaluation, "get_dataset_from_preds", lambda *a, **k: [instance]
    )
    monkeypatch.setattr(run_evaluation, "load_instances", lambda *a, **k: [instance])
    monkeypatch.setattr(run_evaluation.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(run_evaluation, "_docker_client", MagicMock())
    monkeypatch.setattr(run_evaluation, "_build_before_eval", MagicMock())
    monkeypatch.setattr(run_evaluation, "run_instances", run_instances)
    monkeypatch.setattr(run_evaluation, "make_run_report", MagicMock())

    run_evaluation.main(
        dataset_name="org/dataset",
        split="test",
        instance_ids=[instance_id],
        predictions_path="predictions.jsonl",
        max_workers=1,
        open_file_limit=4096,
        run_id="source-only",
        timeout=30,
        rewrite_reports=False,
        modal=False,
        task_repo=str(tmp_path),
        allow_network=False,
    )

    run_instances.assert_called_once()
    trusted_prediction = run_instances.call_args.args[0][instance_id]
    assert trusted_prediction["reference_patch"] is False
    assert trusted_prediction["skip_patch"] is False


def test_modal_no_patch_is_rejected(monkeypatch):
    monkeypatch.setattr(run_evaluation.platform, "system", lambda: "Darwin")
    with pytest.raises(ValueError, match="supported only by local evaluation"):
        run_evaluation.main(
            dataset_name="org/dataset",
            split="test",
            instance_ids=[],
            predictions_path="no-patch",
            max_workers=1,
            open_file_limit=4096,
            run_id="modal-baseline",
            timeout=30,
            rewrite_reports=False,
            modal=True,
        )


def test_task_repo_bundles_require_reusing_prebuilt_images(tmp_path):
    with pytest.raises(ValueError, match="requires --reuse-images"):
        run_evaluation.main(
            dataset_name="org/dataset",
            split="test",
            instance_ids=[],
            predictions_path="gold",
            max_workers=1,
            open_file_limit=4096,
            run_id="unsafe-order",
            timeout=30,
            rewrite_reports=False,
            modal=False,
            task_repo=str(tmp_path),
            offline_deps_dir=str(tmp_path),
        )


def test_images_build_cli_forwards_split(monkeypatch):
    called = {}

    def fake_prepare_images(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "swebench.image_builder.prepare_images.main", fake_prepare_images
    )
    result = CliRunner().invoke(
        app, ["images", "build", "/tasks", "--split", "test", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert called["split"] == "test"
    assert called["open_file_limit"] == 65536


@pytest.mark.parametrize(
    "image,expected",
    [
        (
            "swebench/sweb.eval.x86_64.owner_1776_repo-1:latest",
            ("docker.io/swebench", "latest"),
        ),
        ("ghcr.io/org/sub/image:v2", ("ghcr.io/org/sub", "v2")),
        ("registry.example:5000/org/image", ("registry.example:5000/org", "latest")),
    ],
)
def test_image_namespace_keeps_the_complete_prefix(image, expected):
    assert image_namespace_and_tag(image) == expected


def test_docker_hub_short_names_are_canonicalized():
    assert canonical_image_ref("ubuntu:jammy") == "docker.io/library/ubuntu:jammy"
    assert canonical_image_ref("swebench/image:latest") == "docker.io/swebench/image:latest"
    assert canonical_image_ref("localhost/image:latest") == "localhost/image:latest"


def test_build_attestation_hashes_only_public_context_inputs(tmp_path):
    (tmp_path / ".dockerignore").write_text(
        "*\n!Dockerfile\n!problem_assets\n!problem_assets/**\n"
    )
    spec = ImageSpec("owner__repo-1", "FROM scratch\n", "example", context_dir=tmp_path)
    initial = spec.build_input_digest

    (tmp_path / "test_assets").mkdir()
    (tmp_path / "test_assets" / "secret.png").write_bytes(b"secret")
    assert spec.build_input_digest == initial

    (tmp_path / "problem_assets").mkdir()
    (tmp_path / "problem_assets" / "public.png").write_bytes(b"public")
    assert spec.build_input_digest != initial


def test_force_rebuild_dry_run_is_forwarded_without_deleting_images(monkeypatch):
    captured = {}

    def fake_threadpool(_func, payloads, _workers):
        captured["payloads"] = payloads
        return ["planned"], []

    monkeypatch.setattr(docker_build, "run_threadpool", fake_threadpool)

    docker_build.build_instance_images(
        client=MagicMock(),
        image_specs=[SimpleNamespace(name="example/image:latest")],
        force_rebuild=True,
        max_workers=1,
        dry_run=True,
    )

    assert captured["payloads"][0][-2:] == (True, True)


def test_eval_cli_exposes_and_forwards_offline_options(monkeypatch, tmp_path):
    called = {}

    def fake_run_evaluation(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(run_evaluation, "main", fake_run_evaluation)

    result = CliRunner().invoke(
        app,
        [
            "eval",
            "org/dataset",
            "--gold",
            "--allow-network",
            "--offline-deps-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert called["allow_network"] is True
    assert called["offline_deps_dir"] == str(tmp_path)


def test_eval_cli_defaults_to_an_isolated_container(monkeypatch):
    called = {}

    def fake_run_evaluation(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(run_evaluation, "main", fake_run_evaluation)

    result = CliRunner().invoke(app, ["eval", "org/dataset", "--gold"])

    assert result.exit_code == 0, result.output
    assert called["allow_network"] is False
    assert called["offline_deps_dir"] is None


def test_eval_cli_supports_no_patch_negative_control(monkeypatch):
    called = {}

    def fake_run_evaluation(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(run_evaluation, "main", fake_run_evaluation)
    result = CliRunner().invoke(app, ["eval", "org/dataset", "--no-patch"])

    assert result.exit_code == 0, result.output
    assert called["predictions_path"] == "no-patch"


def test_no_patch_report_has_truthful_patch_flags(tmp_path):
    spec = _test_spec()
    spec.log_parser = "parse_log_jest"
    spec.eval_type = "fail_only"
    spec.FAIL_TO_PASS = ["still fails"]
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\n✕ still fails\n{END_TEST_OUTPUT}\n"
        ">>>>> Test Exit Code: 1\n"
    )
    prediction = {
        "instance_id": spec.instance_id,
        "model_name_or_path": "no_patch",
        "model_patch": "__SWEBENCH_NO_PATCH__",
        "skip_patch": True,
    }

    report = get_eval_report(spec, prediction, log, include_tests_status=True)[
        spec.instance_id
    ]

    assert report["patch_is_None"] is True
    assert report["patch_exists"] is False
    assert report["patch_successfully_applied"] is False
    assert report["resolved"] is False


def test_report_cli_regrades_no_patch_directory(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(run_evaluation, "RUN_EVALUATION_LOG_DIR", tmp_path)
    run_evaluation.write_run_metadata(
        "baseline",
        "org/dataset",
        "test",
        None,
        prediction_mode="no-patch",
    )

    def fake_run_evaluation(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(run_evaluation, "main", fake_run_evaluation)
    result = CliRunner().invoke(app, ["report", "baseline"])

    assert result.exit_code == 0, result.output
    assert called["predictions_path"] == "no-patch"
