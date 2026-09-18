from __future__ import annotations

import docker
import hashlib
import json
from datetime import datetime, timezone
import os
import platform
import re
import shlex
import urllib.parse
import urllib.request
import traceback

if platform.system() == "Linux":
    import resource

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path, PurePosixPath

from swebench.image_builder.constants import CONTAINER_USER, CONTAINER_WORKDIR
from swebench.image_builder.image_spec import canonical_image_ref
from swebench.harness.constants import (
    APPLY_PATCH_FAIL,
    APPLY_PATCH_PASS,
    CONTAINER_PATCH_FILE,
    LOG_REPORT,
    LOG_RUN_METADATA,
    LOG_INSTANCE,
    LOG_TEST_OUTPUT,
    RUN_EVALUATION_LOG_DIR,
    START_TEST_OUTPUT,
)
from swebench.harness.docker_utils import (
    cleanup_container,
    copy_to_container,
    exec_run_with_timeout,
)
import logging
from swebench.harness.grading import get_eval_report
from swebench.harness.reporting import make_run_report
from swebench.harness.modal_eval import (
    run_instances_modal,
    validate_modal_credentials,
)
from swebench.types import TestSpec
from swebench.harness.utils import make_test_spec
from swebench.task.repo import asset_path, load_task_repo
from swebench.harness.utils import (
    EvaluationError,
    load_swebench_dataset,
    get_predictions_from_file,
    run_threadpool,
    str2bool,
)

from swebench.logger import setup_logger, close_logger

GIT_APPLY_CMDS = [
    "git apply --verbose",
    "git apply --verbose --3way",
    "git apply --verbose --reject",
    "patch --batch --forward --fuzz=5 -p1 -i",
]

DOCKER_CLIENT_TIMEOUT = int(os.environ.get("SWEBENCH_DOCKER_TIMEOUT", "1800"))
DOCKER_CLIENT_POOL_SIZE = int(os.environ.get("SWEBENCH_DOCKER_POOL_SIZE", "128"))


def _docker_client() -> docker.DockerClient:
    return docker.from_env(
        timeout=DOCKER_CLIENT_TIMEOUT,
        max_pool_size=DOCKER_CLIENT_POOL_SIZE,
    )


def create_container(
    test_spec: TestSpec,
    client: docker.DockerClient,
    run_id: str,
    logger: logging.Logger,
    allow_network: bool = False,
    offline_deps_dir: str | Path | None = None,
    pull_missing: bool = True,
    task_repo: str | Path | None = None,
):
    """
    Creates a container from an instance image for running evaluation.

    Args:
        test_spec (TestSpec): Test spec with evaluation details
        client (docker.DockerClient): Docker client for creating the container
        run_id (str): Run ID identifying process, used for the container name
        logger (logging.Logger): Logger to use for logging the creation process
        allow_network (bool): Give the container Docker's default network instead
            of the network-isolated default
        offline_deps_dir (str | Path | None): Root containing one read-only
            dependency-cache directory per instance
        pull_missing (bool): Pull a missing image from its registry. Task-repo runs
            disable this so a stale published image cannot replace a missing build.
        task_repo (str | Path | None): Source of dependency-bundle provenance metadata.
    """
    container = None
    try:
        # Check if the image exists
        try:
            image_name = canonical_image_ref(test_spec.image)
            image = client.images.get(image_name)
        except docker.errors.ImageNotFound:
            if not pull_missing:
                raise EvaluationError(
                    test_spec.instance_id,
                    f"Required local image is missing: {test_spec.image}",
                    logger,
                )
            try:
                logger.info("Image not found locally, attempting to pull...")
                image = client.images.pull(image_name)
            except docker.errors.ImageNotFound:
                raise EvaluationError(
                    test_spec.instance_id,
                    f"Image {image_name} not found for {test_spec.instance_id}",
                    logger,
                )

        logger.info(f"Creating container for {test_spec.instance_id}...")

        container_name = f"sweb.eval.{test_spec.instance_id.lower()}.{run_id}"
        create_kwargs = {
            # Pin this container to the image object already validated above. A mutable
            # tag could otherwise be retargeted between validation and creation.
            "image": image.id,
            "user": CONTAINER_USER,
            "detach": True,
            "command": "tail -f /dev/null",
            # Docker's default seccomp profile only permits CLONE_NEWUSER with
            # CAP_SYS_ADMIN, which browser sandboxes need (e.g. openlayers karma)
            "cap_add": ["SYS_ADMIN"],
        }
        if not allow_network:
            create_kwargs["network_mode"] = "none"
        else:
            # Docker's default bridge is normally appropriate. A rootless engine can
            # explicitly select another connected mode (for example ``host``) without
            # weakening the isolated default used by normal grading.
            network_override = os.environ.get("SWEBENCH_NETWORK_MODE")
            if network_override:
                create_kwargs["network_mode"] = network_override
            proxy_env = {
                name: os.environ[name]
                for name in (
                    "HTTP_PROXY",
                    "HTTPS_PROXY",
                    "NO_PROXY",
                    "http_proxy",
                    "https_proxy",
                    "no_proxy",
                )
                if os.environ.get(name)
            }
            if proxy_env:
                create_kwargs["environment"] = proxy_env
        if offline_deps_dir is not None:
            bundle = _offline_deps_bundle_path(offline_deps_dir, test_spec.instance_id)
            if bundle is not None:
                _validate_offline_deps_bundle(
                    bundle, test_spec, image.id, task_repo=task_repo
                )
                create_kwargs["volumes"] = {
                    str(bundle): {
                        "bind": "/run/swebench-offline-seed",
                        "mode": "ro,z",
                    }
                }
                logger.info(
                    f"Mounting offline dependency bundle for {test_spec.instance_id} "
                    "as a read-only seed"
                )
        # Remove any existing container with this name (handles ghost containers)
        try:
            old = client.containers.get(container_name)
            old.remove(force=True)
            logger.info(f"Removed existing container {container_name}")
        except docker.errors.NotFound:
            pass
        except Exception:
            pass
        try:
            container = client.containers.create(
                name=container_name,
                **create_kwargs,
            )
        except docker.errors.APIError as e:
            if "409" in str(e) or "Conflict" in str(e):
                # Ghost container — use a unique suffix
                import time

                container_name = f"{container_name}.{int(time.time())}"
                logger.info(f"Retrying with unique name: {container_name}")
                container = client.containers.create(
                    name=container_name,
                    **create_kwargs,
                )
            else:
                raise
        logger.info(f"Container for {test_spec.instance_id} created: {container.id}")
        return container
    except Exception as e:
        logger.error(f"Error creating container for {test_spec.instance_id}: {e}")
        logger.info(traceback.format_exc())
        cleanup_container(client, container, logger)
        raise EvaluationError(test_spec.instance_id, str(e), logger) from e


def _offline_deps_bundle_path(
    offline_deps_dir: str | Path, instance_id: str
) -> Path | None:
    """Return the private cache directory for one instance.

    The evaluator accepts a store whose immediate children are instance IDs.  It
    mounts only the selected child, never the task repo or the whole private store.
    That child may contain ``npm`` and/or ``yarn`` directories; they are copied to
    ``/run/swebench-offline/npm`` and ``/run/swebench-offline/yarn`` in the grader.
    """
    if Path(instance_id).name != instance_id or instance_id in {"", ".", ".."}:
        raise ValueError(
            f"Unsafe instance ID for offline dependency lookup: {instance_id!r}"
        )

    root = Path(offline_deps_dir).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Offline dependency root is not a directory: {root}")
    bundle = root / instance_id
    if not bundle.exists():
        return None
    if not bundle.is_dir():
        raise ValueError(
            f"Offline dependency bundle for {instance_id} is not a directory: {bundle}"
        )
    resolved_bundle = bundle.resolve()
    try:
        resolved_bundle.relative_to(root)
    except ValueError as e:
        raise ValueError(
            f"Offline dependency bundle for {instance_id} escapes its root: "
            f"{resolved_bundle}"
        ) from e
    return resolved_bundle


def _required_offline_deps(task_repo: str | Path | None) -> set[str]:
    """Load instance IDs whose manifest changes require a private offline cache."""
    if task_repo is None:
        return set()
    path = Path(task_repo).expanduser().resolve() / "offline_dependencies.json"
    if not path.is_file():
        return set()
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("instances"), dict):
        raise ValueError(f"Invalid offline dependency metadata: {path}")
    return set(data["instances"])


def _patch_changes_root_package_json(patch: str | None) -> bool:
    """Whether a unified diff changes the repository-root package manifest."""
    if not patch:
        return False
    return bool(
        re.search(
            r"^diff --git (?:a/)?package\.json (?:b/)?package\.json\s*$",
            patch,
            re.MULTILINE,
        )
    )


def _validate_offline_deps_bundle(
    bundle: Path,
    test_spec: TestSpec,
    image_digest: str,
    task_repo: str | Path | None = None,
) -> dict:
    """Reject a cache built for another task or mutable image revision."""
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Offline dependency manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError(f"Unsupported offline dependency manifest: {manifest_path}")
    if manifest.get("instance_id") != test_spec.instance_id:
        raise ValueError(
            f"Offline dependency bundle names {manifest.get('instance_id')!r}, "
            f"expected {test_spec.instance_id!r}"
        )
    expected_digest = str(manifest.get("image_digest", "")).removeprefix("sha256:")
    actual_digest = str(image_digest).removeprefix("sha256:")
    if not expected_digest or expected_digest != actual_digest:
        raise ValueError(
            f"Offline dependency bundle image digest {expected_digest!r} does not "
            f"match {test_spec.image} digest {actual_digest!r}"
        )
    manager = manifest.get("manager")
    if manager not in {"npm", "yarn"} or not (bundle / manager).is_dir():
        raise ValueError(
            f"Offline dependency bundle has no valid npm/yarn cache: {bundle}"
        )
    if task_repo is not None:
        task_root = Path(task_repo).expanduser().resolve()
        gold_patch = task_root / "tasks" / test_spec.instance_id / "gold.patch"
        config_path = task_root / "offline_dependencies.json"
        if not gold_patch.is_file() or not config_path.is_file():
            raise FileNotFoundError(
                f"Cannot validate dependency bundle provenance for {test_spec.instance_id}"
            )
        config = json.loads(config_path.read_text())
        dependency_config = config.get("instances", {}).get(test_spec.instance_id)
        if not isinstance(dependency_config, dict):
            raise ValueError(
                f"No dependency metadata for {test_spec.instance_id} in {config_path}"
            )
        expected_patch = hashlib.sha256(gold_patch.read_bytes()).hexdigest()
        expected_config = hashlib.sha256(
            json.dumps(
                dependency_config, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        if manifest.get("gold_patch_sha256") != expected_patch:
            raise ValueError(
                f"Offline dependency bundle gold patch is stale for {test_spec.instance_id}"
            )
        if manifest.get("dependency_config_sha256") != expected_config:
            raise ValueError(
                f"Offline dependency bundle configuration is stale for {test_spec.instance_id}"
            )
    return manifest


def _prepare_offline_deps(container, instance_id: str, logger) -> None:
    """Copy an immutable cache seed to the writable paths package managers use.

    npm and Yarn both update cache bookkeeping during an offline install. Mounting
    the host cache directly at ``/run/swebench-offline`` read-only therefore fails
    with EROFS. The source remains immutable and shared, while every disposable
    grader gets its own writable copy.
    """
    result = container.exec_run(
        [
            "/bin/bash",
            "-c",
            "rm -rf /run/swebench-offline && "
            "mkdir -p /run/swebench-offline && "
            "cp -a /run/swebench-offline-seed/. /run/swebench-offline/ && "
            "chmod -R a+rwX /run/swebench-offline",
        ],
        user="root",
    )
    if result.exit_code != 0:
        output = result.output.decode("utf-8", errors="replace")
        raise EvaluationError(
            instance_id,
            f"Could not stage the offline dependency bundle: {output}",
            logger,
        )
    logger.info(
        "Copied the read-only dependency seed to writable "
        "/run/swebench-offline for this container"
    )


def _assert_no_baked_grading_material(
    container, instance_id: str, logger, allow_offline_seed: bool = False
) -> None:
    """Reject solver-visible images containing known private grader paths."""
    forbidden = (
        "/swebench/image_assets",
        "/image_assets",
        "/run/swebench-offline",
        "/gold.patch",
        "/test.patch",
        "/tests.json",
        "/eval.sh",
        CONTAINER_PATCH_FILE,
    )
    if not allow_offline_seed:
        forbidden += ("/run/swebench-offline-seed",)
    command = "for path in " + " ".join(map(shlex.quote, forbidden)) + "; do "
    command += 'if [ -e "$path" ]; then printf "%s\\n" "$path"; fi; done'
    result = container.exec_run(["/bin/bash", "-c", command], user="root")
    output = result.output.decode("utf-8", errors="replace").strip()
    if result.exit_code != 0:
        raise EvaluationError(
            instance_id,
            f"Could not inspect image for grading material: {output}",
            logger,
        )
    if output:
        raise EvaluationError(
            instance_id,
            "Solver-visible image contains forbidden grading material: "
            + ", ".join(output.splitlines()),
            logger,
        )


def _resolve_asset_bytes(
    asset: dict,
    task_repo: str | None,
    logger,
    allow_network: bool = True,
) -> bytes | None:
    """Read an asset from the task repo if there is one, else fetch its url."""
    _validate_asset_path(asset["path"])
    if task_repo is not None:
        local = asset_path(task_repo, asset["instance_id"], asset["path"])
        if local.is_file():
            return local.read_bytes()
    if not allow_network:
        logger.warning(
            f"Offline grading requires a local copy of {asset['instance_id']} "
            f"asset {asset['path']}"
        )
        return None
    url = asset.get("url")
    if not url:
        logger.warning(f"No asset for {asset['instance_id']} at {asset['path']}")
        return None
    if urllib.parse.urlparse(url).scheme not in {"http", "https"}:
        logger.warning(f"Refusing non-HTTP asset URL: {url}")
        return None
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return resp.read()
    except Exception as e:
        logger.warning(f"Could not fetch image asset {url}: {e}")
        return None


def _validate_asset_path(path: str) -> None:
    """Reject absolute, escaping, or control-character asset paths."""
    if not isinstance(path, str) or not path:
        raise ValueError(f"asset path is not a non-empty string: {path!r}")
    parsed = PurePosixPath(path)
    if parsed.is_absolute():
        raise ValueError(f"asset path is absolute: {path!r}")
    if any(part in {"", ".", ".."} for part in parsed.parts):
        raise ValueError(f"asset path contains an unsafe component: {path!r}")
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError(f"asset path contains a control character: {path!r}")


def _stage_image_assets(
    container,
    test_spec,
    log_dir: Path,
    logger,
    task_repo: str | None = None,
    allow_network: bool = True,
    include_patch_assets: bool = False,
) -> list[str]:
    """Stage a patch's binary assets in the container; return restore commands.

    A text patch cannot carry binary files (e.g. expected.png rendering baselines),
    so the dataset lists them in image_assets. They must land in the working tree
    *after* the eval script's `rm -f` + `git apply`, so they arrive with the patch
    rather than being baked into the image -- test data in the image would be
    visible to anything with a shell in it.
    """
    declared = test_spec.image_assets or {}
    assets = []
    kinds = ["test_patch"]
    if include_patch_assets:
        kinds.append("patch")
    for key in kinds:
        for entry in declared.get(key) or []:
            if entry.get("path"):
                assets.append({**entry, "instance_id": test_spec.instance_id})
    if not assets:
        return []
    staging = Path(log_dir) / "image_assets"
    staging.mkdir(parents=True, exist_ok=True)
    container.exec_run("mkdir -p /image_assets", user="root")
    restore, from_mirror = [], 0
    for asset in assets:
        _validate_asset_path(asset["path"])
        data = _resolve_asset_bytes(
            asset, task_repo, logger, allow_network=allow_network
        )
        if data is None:
            source = "local" if not allow_network else "local or remote"
            raise EvaluationError(
                test_spec.instance_id,
                f"Missing {source} binary grading asset: {asset['path']}",
                logger,
            )
        if (
            task_repo is not None
            and asset_path(task_repo, asset["instance_id"], asset["path"]).is_file()
        ):
            from_mirror += 1
        flat = asset["path"].replace("/", "__")
        local = staging / flat
        local.write_bytes(data)
        copy_to_container(container, local, PurePosixPath("/image_assets") / flat)
        quoted_path = shlex.quote(asset["path"])
        quoted_flat = shlex.quote(flat)
        restore.append(
            f'{{ mkdir -p -- "$(dirname -- {quoted_path})" && '
            f"cp -- /image_assets/{quoted_flat} {quoted_path}; }} || "
            f"{{ echo 'failed to restore binary grading asset' >&2; exit 1; }}"
        )
    if restore:
        logger.info(
            f"Staged {len(restore)} patch asset(s) for restore after git apply "
            f"({from_mirror} from the local mirror, {len(restore) - from_mirror} fetched)"
        )
    return restore


def _inject_asset_restore(eval_script: str, restore_cmds: list[str]) -> str:
    """Prepare an eval script for deterministic logging and grader-only assets.

    Merging stderr into stdout inside the shell is necessary for Docker-compatible
    runtimes that otherwise batch their two exec streams. Without it, test results can
    move outside the start/end markers and be mistaken for missing tests.
    """
    lines = eval_script.split("\n")
    if "exec 2>&1" not in lines:
        insert_at = 1 if lines and lines[0].startswith("#!") else 0
        lines.insert(insert_at, "exec 2>&1")
    if not restore_cmds:
        return "\n".join(lines)
    for idx, line in enumerate(lines):
        if START_TEST_OUTPUT in line:
            return "\n".join(lines[:idx] + restore_cmds + lines[idx:])
    return "\n".join(lines + restore_cmds)


def run_instance(
    test_spec: TestSpec,
    pred: dict,
    client: docker.DockerClient,
    run_id: str,
    timeout: int | None = None,
    rewrite_reports: bool = False,
    skip_patch: bool = False,
    task_repo: str | None = None,
    allow_network: bool = False,
    offline_deps_dir: str | Path | None = None,
    pull_missing: bool = True,
):
    """
    Run a single instance with the given prediction.

    Args:
        test_spec (TestSpec): TestSpec instance with pre-built image
        pred (dict): Prediction w/ model_name_or_path, model_patch, instance_id
        client (docker.DockerClient): Docker client
        run_id (str): Run ID
        timeout (int): Timeout for running tests
        rewrite_reports (bool): True if eval run is just to reformat existing report
        skip_patch (bool): True to skip applying model patch (negative test mode)
        task_repo (str | None): Optional local task repository
        allow_network (bool): Opt in to Docker's default network for this grader
        offline_deps_dir (str | Path | None): Per-instance dependency bundle root
        pull_missing (bool): Whether a missing local image may be pulled
    """
    # Set up logging directory
    instance_id = test_spec.instance_id
    model_name_or_path = pred.get("model_name_or_path", "None").replace("/", "__")
    log_dir = RUN_EVALUATION_LOG_DIR / run_id / model_name_or_path / instance_id

    # Set up report file
    report_path = log_dir / LOG_REPORT
    if rewrite_reports:
        test_output_path = log_dir / LOG_TEST_OUTPUT
        if not test_output_path.exists():
            raise ValueError(f"Test output file {test_output_path} does not exist")
        report = get_eval_report(
            test_spec=test_spec,
            prediction=pred,
            test_log_path=test_output_path,
            include_tests_status=True,
        )
        # Write report to report.json
        with open(report_path, "w") as f:
            f.write(json.dumps(report, indent=4))
        return instance_id, report
    if report_path.exists():
        return instance_id, json.loads(report_path.read_text())

    # Set up logger
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_INSTANCE
    logger = setup_logger(instance_id, log_file)

    # Run the instance
    container = None
    try:
        # Create container from image
        container = create_container(
            test_spec,
            client,
            run_id,
            logger,
            allow_network=allow_network,
            offline_deps_dir=offline_deps_dir,
            pull_missing=pull_missing,
            task_repo=task_repo,
        )
        container.start()
        logger.info(f"Container for {instance_id} started: {container.id}")
        if task_repo is not None:
            # Registry images may predate this contract; task-repo validation must
            # prove that the image produced by the candidate checkout is clean.
            has_offline_seed = (
                offline_deps_dir is not None
                and _offline_deps_bundle_path(offline_deps_dir, instance_id) is not None
            )
            _assert_no_baked_grading_material(
                container,
                instance_id,
                logger,
                allow_offline_seed=has_offline_seed,
            )

        if not skip_patch:
            # Copy model prediction as patch file to container
            patch_file = Path(log_dir / "patch.diff")
            patch_file.write_text(pred["model_patch"] or "")
            logger.info(
                f"Intermediate patch for {instance_id} written to {patch_file}, now applying to container..."
            )
            copy_to_container(
                container, patch_file, PurePosixPath(CONTAINER_PATCH_FILE)
            )

            # Attempt to apply patch to container
            applied_patch = False
            for attempt, git_apply_cmd in enumerate(GIT_APPLY_CMDS):
                if attempt:
                    # a failed attempt (notably --reject) leaves partial state behind,
                    # which makes every later command fail; restart from a pristine tree
                    container.exec_run(
                        ["/bin/bash", "-c", "git checkout -- . ; git clean -fd"],
                        workdir=CONTAINER_WORKDIR,
                        user=CONTAINER_USER,
                    )
                val = container.exec_run(
                    f"{git_apply_cmd} {CONTAINER_PATCH_FILE}",
                    workdir=CONTAINER_WORKDIR,
                    user=CONTAINER_USER,
                )
                if val.exit_code == 0:
                    logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
                    applied_patch = True
                    break
                else:
                    logger.info(f"Failed to apply patch to container: {git_apply_cmd}")
            if not applied_patch:
                # the chain can leave the patch fully applied while each command still exited non-zero
                reverse_check = container.exec_run(
                    f"git apply --check --reverse {CONTAINER_PATCH_FILE}",
                    workdir=CONTAINER_WORKDIR,
                    user=CONTAINER_USER,
                )
                if reverse_check.exit_code == 0:
                    logger.info(f"{APPLY_PATCH_PASS}: verified already applied")
                    applied_patch = True
            if not applied_patch:
                logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}")
                raise EvaluationError(
                    instance_id,
                    f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}",
                    logger,
                )
        else:
            logger.info(f"Skipping model patch for {instance_id} (--no-patch mode)")

        if (
            offline_deps_dir is not None
            and _offline_deps_bundle_path(offline_deps_dir, instance_id) is not None
        ):
            _prepare_offline_deps(container, instance_id, logger)

        # Get git diff before running eval script
        git_diff_output_before = (
            container.exec_run(
                "git -c core.fileMode=false diff", workdir=CONTAINER_WORKDIR
            )
            .output.decode("utf-8", errors="replace")
            .strip()
        )
        logger.info(f"Git diff before:\n{git_diff_output_before}")

        # Materialize multimodal binary assets (e.g. expected.png rendering
        # baselines). A text test_patch cannot carry them, so the dataset ships
        # them as urls in image_assets; without this the tests run against a
        # missing baseline and error out.
        restore_cmds = _stage_image_assets(
            container,
            test_spec,
            log_dir,
            logger,
            task_repo,
            allow_network=allow_network,
            include_patch_assets=bool(pred.get("reference_patch")),
        )

        eval_file = Path(log_dir / "eval.sh")
        eval_file.write_text(_inject_asset_restore(test_spec.eval_script, restore_cmds))
        logger.info(
            f"Eval script for {instance_id} written to {eval_file}; copying to container..."
        )
        copy_to_container(container, eval_file, PurePosixPath("/eval.sh"))

        # Run eval script, write output to logs
        test_output, timed_out, total_runtime = exec_run_with_timeout(
            container, "/bin/bash /eval.sh", timeout
        )
        test_output_path = log_dir / LOG_TEST_OUTPUT
        logger.info(f"Test runtime: {total_runtime:_.2f} seconds")
        with open(test_output_path, "w") as f:
            f.write(test_output)
            logger.info(f"Test output for {instance_id} written to {test_output_path}")
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    instance_id,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )

        # Get git diff after running eval script (ignore permission changes)
        git_diff_output_after = (
            container.exec_run(
                "git -c core.fileMode=false diff", workdir=CONTAINER_WORKDIR
            )
            .output.decode("utf-8", errors="replace")
            .strip()
        )

        # Check if git diff changed after running eval script
        logger.info(f"Git diff after:\n{git_diff_output_after}")
        if git_diff_output_after != git_diff_output_before:
            logger.info("Git diff changed after running eval script")

        # Get report from test output
        logger.info(f"Grading answer for {instance_id}...")
        report = get_eval_report(
            test_spec=test_spec,
            prediction=pred,
            test_log_path=test_output_path,
            include_tests_status=True,
        )
        logger.info(
            f"report: {report}\n"
            f"Result for {instance_id}: resolved: {report[instance_id]['resolved']}"
        )

        # Write report to report.json
        with open(report_path, "w") as f:
            f.write(json.dumps(report, indent=4))
        return instance_id, report
    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        error_msg = (
            f"Error in evaluating model for {instance_id}: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({logger.log_file}) for more information."
        )
        logger.error(error_msg)
    finally:
        # Remove instance container + image, close logger
        cleanup_container(client, container, logger)
        close_logger(logger)
    return


def run_instances(
    predictions: dict,
    instances: list,
    max_workers: int,
    run_id: str,
    timeout: int,
    rewrite_reports: bool = False,
    skip_patch: bool = False,
    task_repo: str | None = None,
    allow_network: bool = False,
    offline_deps_dir: str | Path | None = None,
    pull_missing: bool = True,
):
    """
    Run all instances for the given predictions in parallel.
    Expects instances to have pre-built images.

    Args:
        predictions (dict): Predictions dict generated by the model
        instances (list): List of instances with 'image' field
        max_workers (int): Maximum number of workers
        run_id (str): Run ID
        timeout (int): Timeout for running tests
        rewrite_reports (bool): True if eval run is just to reformat existing report
        allow_network (bool): Opt in to Docker's default network for graders
        offline_deps_dir (str | Path | None): Per-instance dependency bundle root
        pull_missing (bool): Whether workers may pull missing local images
    """
    client = _docker_client()
    test_specs = [make_test_spec(instance) for instance in instances]

    # run instances in parallel
    payloads = []
    for test_spec in test_specs:
        payloads.append(
            (
                test_spec,
                predictions[test_spec.instance_id],
                client,
                run_id,
                timeout,
                rewrite_reports,
                skip_patch,
                task_repo,
                allow_network,
                offline_deps_dir,
                pull_missing,
            )
        )

    # run instances in parallel
    print(f"Running {len(instances)} instances...")
    run_threadpool(run_instance, payloads, max_workers)
    print("All instances run.")


def write_run_metadata(
    run_id: str,
    dataset_name: str,
    split: str,
    task_repo: str | None,
    allow_network: bool = False,
    offline_deps_dir: str | Path | None = None,
    reuse_images: bool = False,
    prediction_mode: str = "gold",
) -> Path:
    """Record what this run graded against.

    Re-grading needs the expected tests and the log parser, which live in the
    dataset, not in the run's logs. Without this a later `swebench report` has to
    be told the dataset again, and gets it wrong silently if told the wrong one.
    """
    path = RUN_EVALUATION_LOG_DIR / run_id / LOG_RUN_METADATA
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "dataset": dataset_name,
        "split": split,
        "task_repo": task_repo,
        "allow_network": allow_network,
        "network_mode": (
            os.environ.get("SWEBENCH_NETWORK_MODE", "default")
            if allow_network
            else "none"
        ),
        "offline_deps_dir": (
            str(Path(offline_deps_dir).expanduser().resolve())
            if offline_deps_dir is not None
            else None
        ),
        "reuse_images": reuse_images,
        "prediction_mode": prediction_mode,
    }
    if path.is_file():
        existing = json.loads(path.read_text())
        # ``reuse_images`` was added after run metadata first shipped; absence means
        # the old build-before-eval behavior, which is equivalent to false.
        existing.setdefault("reuse_images", False)
        # Older metadata predates explicit negative controls and therefore represented
        # gold runs. For an in-progress legacy no-patch run, tolerate the absent field;
        # the report command can infer it from the saved model directory.
        if "prediction_mode" not in existing:
            existing["prediction_mode"] = metadata["prediction_mode"]
        mismatches = {
            key: (existing.get(key), value)
            for key, value in metadata.items()
            if existing.get(key) != value
        }
        if mismatches:
            details = ", ".join(
                f"{key}: {old!r} != {new!r}"
                for key, (old, new) in sorted(mismatches.items())
            )
            raise ValueError(
                f"Run {run_id!r} already has incompatible execution metadata: "
                + details
            )
        return path
    metadata["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(json.dumps(metadata, indent=2) + "\n")
    return path


def read_run_metadata(run_id: str) -> dict | None:
    """What a previous run graded against, if it recorded it."""
    path = RUN_EVALUATION_LOG_DIR / run_id / LOG_RUN_METADATA
    return json.loads(path.read_text()) if path.is_file() else None


def load_instances(
    dataset_name: str, split: str, instance_ids: list | None, task_repo: str | None
) -> list:
    """Instances come from the task repo when one is given, else from the dataset.

    A dataset is already one split; a task repo holds every split at once, so the
    split has to be applied here or a run picks up whatever else is in the tree --
    the multimodal repo would evaluate its dev and deprecated tasks alongside test.

    Named ids are honoured from any split, matching `select_tasks`: an instance
    being repaired can be run by name while it sits in an unpublished split.
    """
    if not task_repo:
        return load_swebench_dataset(dataset_name, split, instance_ids)
    tasks = load_task_repo(task_repo, instance_ids)
    if instance_ids:
        return tasks
    wanted = [task for task in tasks if task.get("split") == split]
    if not wanted:
        available = sorted({task["split"] for task in tasks if task.get("split")})
        raise ValueError(
            f"{task_repo} has no tasks in split {split!r}. "
            f"It has: {' '.join(available) or 'none'}"
        )
    return wanted


def get_dataset_from_preds(
    dataset_name: str,
    split: str,
    instance_ids: list,
    predictions: dict,
    run_id: str,
    rewrite_reports: bool,
    exclude_completed: bool = True,
    task_repo: str | None = None,
):
    """
    Return only instances that have predictions and are in the dataset.
    If instance_ids is provided, only return instances with those IDs.
    If exclude_completed is True, only return instances that have not been run yet.
    """
    # load dataset
    dataset = load_instances(dataset_name, split, None, task_repo)
    dataset_ids = {i["instance_id"] for i in dataset}

    if instance_ids:
        # check that all instance IDs have predictions
        missing_preds = set(instance_ids) - set(predictions.keys())
        if missing_preds:
            print(
                f"Warning: Missing predictions for {len(missing_preds)} instance IDs."
            )

    # check that all prediction IDs are in the dataset
    prediction_ids = set(predictions.keys())
    if prediction_ids - dataset_ids:
        raise ValueError(
            (
                "Some prediction IDs not found in dataset!"
                f"\nMissing IDs:\n{' '.join(prediction_ids - dataset_ids)}"
            )
        )
    if instance_ids:
        dataset = [i for i in dataset if i["instance_id"] in instance_ids]

    if rewrite_reports:
        # we only return instances that have existing test outputs
        test_output_ids = set()
        for instance in dataset:
            if instance["instance_id"] not in predictions:
                continue
            prediction = predictions[instance["instance_id"]]
            test_output_file = (
                RUN_EVALUATION_LOG_DIR
                / run_id
                / prediction["model_name_or_path"].replace("/", "__")
                / prediction["instance_id"]
                / "test_output.txt"
            )
            if test_output_file.exists():
                test_output_ids.add(instance["instance_id"])
        dataset = [
            i
            for i in dataset
            if i["instance_id"] in prediction_ids
            and i["instance_id"] in test_output_ids
        ]
        return dataset

    # check which instance IDs have already been run
    completed_ids = set()
    for instance in dataset:
        if instance["instance_id"] not in prediction_ids:
            # skip instances without predictions
            continue
        prediction = predictions[instance["instance_id"]]
        report_file = (
            RUN_EVALUATION_LOG_DIR
            / run_id
            / prediction["model_name_or_path"].replace("/", "__")
            / prediction["instance_id"]
            / LOG_REPORT
        )
        if report_file.exists():
            completed_ids.add(instance["instance_id"])

    if completed_ids and exclude_completed:
        # filter dataset to only instances that have not been run
        print(f"{len(completed_ids)} instances already run, skipping...")
        dataset = [i for i in dataset if i["instance_id"] not in completed_ids]

    empty_patch_ids = {
        k
        for k, v in predictions.items()
        if v["model_patch"] == "" or v["model_patch"] is None
    }

    # filter dataset to only instances with predictions
    dataset = [
        i
        for i in dataset
        if i["instance_id"] in prediction_ids
        and i["instance_id"] not in empty_patch_ids
    ]
    return dataset


def _build_before_eval(dataset, dataset_name, split, task_repo, max_workers, client):
    """Build this run's images from a task repo instead of trusting the registry.

    Without this a failed build is invisible: the image is pulled instead, so a stale
    published image can report a clean pass. Verification is by the image name the
    evaluation will actually use, so a naming mismatch cannot pass for a build.
    """
    from swebench.image_builder.docker_build import build_instance_images
    from swebench.image_builder.image_spec import (
        get_image_specs_from_dataset,
        image_namespace_and_tag,
    )
    from swebench.image_builder.prepare_images import resolve_task_repo
    from swebench.task.repo import load_dockerfiles, task_paths

    wanted = {
        d["instance_id"]: canonical_image_ref(make_test_spec(d).image)
        for d in dataset
    }
    # namespace and tag come from the image the dataset names, so built tags match
    sample = next(iter(wanted.values()))
    namespace, tag = image_namespace_and_tag(sample)

    print(f"Building {len(wanted)} image(s) from {task_repo} before evaluating...")
    with resolve_task_repo(task_repo) as repo_path:
        dockerfiles = load_dockerfiles(repo_path, list(wanted))
        contexts = task_paths(repo_path, list(wanted))
        image_specs = get_image_specs_from_dataset(
            dataset, dockerfiles, namespace, tag, contexts
        )
        mismatched_specs = {
            spec.instance_id: (spec.name, wanted[spec.instance_id])
            for spec in image_specs
            if spec.instance_id in wanted and spec.name != wanted[spec.instance_id]
        }
        if mismatched_specs:
            details = ", ".join(
                f"{instance_id}: {actual} != {expected}"
                for instance_id, (actual, expected) in sorted(
                    mismatched_specs.items()
                )
            )
            raise RuntimeError("Task-repo image tag mismatch: " + details)
        spec_ids = {spec.instance_id for spec in image_specs}
        missing_specs = sorted(set(wanted) - spec_ids)
        if missing_specs:
            raise RuntimeError(
                "Task repo did not produce Docker build specs for: "
                + ", ".join(missing_specs)
            )
        if not image_specs:
            print("No Dockerfiles matched these instances; nothing was built.")
        else:
            _successful, failed = build_instance_images(
                client=client,
                image_specs=image_specs,
                force_rebuild=True,
                max_workers=max_workers,
            )
            if failed:
                raise RuntimeError(
                    f"{len(failed)} task-repo image build(s) failed; "
                    "refusing registry fallback"
                )

    # A task-repo validation run must exercise exactly the image built from that
    # checkout. Falling back to a stale registry image can turn a failed build into a
    # false green result and can reintroduce files intentionally removed for isolation.
    _require_local_images(dataset, client, task_repo)
    print(f"Built {len(wanted)} image(s) locally; none pulled.")


def _require_local_images(dataset: list[dict], client, task_repo: str | Path) -> None:
    """Ensure reused images exist and match the current task-repo build inputs."""
    from swebench.image_builder.image_spec import (
        image_namespace_and_tag,
        make_image_spec,
    )
    from swebench.task.repo import load_dockerfiles, task_paths

    ids = [instance["instance_id"] for instance in dataset]
    dockerfiles = load_dockerfiles(task_repo, ids)
    contexts = task_paths(task_repo, ids)
    missing = []
    stale = []
    for instance in dataset:
        spec = make_test_spec(instance)
        try:
            image = client.images.get(canonical_image_ref(spec.image))
        except docker.errors.ImageNotFound:
            missing.append(f"{spec.instance_id} ({spec.image})")
            continue
        namespace, tag = image_namespace_and_tag(spec.image)
        build_spec = make_image_spec(
            instance,
            dockerfiles[spec.instance_id],
            namespace,
            tag,
            contexts[spec.instance_id],
        )
        labels = (image.attrs.get("Config") or {}).get("Labels") or {}
        actual_digest = labels.get("org.swebench.build-input-sha256")
        if (
            build_spec.name != canonical_image_ref(spec.image)
            or actual_digest != build_spec.build_input_digest
        ):
            stale.append(spec.instance_id)
    if missing:
        raise RuntimeError(
            "--reuse-images requires every task image to exist locally; missing: "
            + ", ".join(sorted(missing))
        )
    if stale:
        raise RuntimeError(
            "--reuse-images found images not built from the current task checkout: "
            + ", ".join(sorted(stale))
        )


def main(
    dataset_name: str,
    split: str,
    instance_ids: list,
    predictions_path: str,
    max_workers: int,
    open_file_limit: int,
    run_id: str,
    timeout: int,
    rewrite_reports: bool,
    modal: bool,
    task_repo: str | None = None,
    allow_network: bool = False,
    offline_deps_dir: str | Path | None = None,
    reuse_images: bool = False,
):
    """
    Run evaluation harness for the given dataset and predictions.
    """
    if task_repo is not None:
        local_task_repo = Path(task_repo).expanduser()
        if local_task_repo.is_dir():
            task_repo = str(local_task_repo.resolve())
    local_dataset = Path(dataset_name).expanduser()
    if local_dataset.is_file():
        dataset_name = str(local_dataset.resolve())

    if dataset_name == "SWE-bench/SWE-bench_Multimodal" and split == "test":
        print(
            "ℹ️ Running local evaluation for the test split of SWE-bench Multimodal. "
            "You may also use sb-cli (https://github.com/swe-bench/sb-cli/) to submit predictions to the hosted evaluation."
        )

    # Modal builds its own images remotely, so a task repo's Dockerfiles would be
    # ignored while its tests were used -- the run would report on a tree it never
    # built. Refused here, before any work, rather than silently proving the wrong thing.
    if modal and task_repo:
        raise ValueError(
            "--modal cannot build from a task repo: it builds images remotely, so the "
            "repo's Dockerfiles would be ignored while its tests were used. Drop "
            "--task-repo to run on Modal, or drop --modal to build the repo."
        )
    if modal and offline_deps_dir:
        raise ValueError(
            "--offline-deps-dir is only supported by local evaluation containers; "
            "drop --modal to use the private dependency bundles."
        )
    if modal and predictions_path == "no-patch":
        raise ValueError("--no-patch is currently supported only by local evaluation")
    if reuse_images and not task_repo:
        raise ValueError("--reuse-images requires --task-repo")
    if offline_deps_dir and not task_repo and not rewrite_reports:
        raise ValueError("--offline-deps-dir requires --task-repo for provenance checks")
    if (
        offline_deps_dir
        and task_repo
        and not Path(task_repo).is_dir()
        and not rewrite_reports
    ):
        raise ValueError(
            "--offline-deps-dir requires a local --task-repo for provenance checks"
        )
    if task_repo and offline_deps_dir and not reuse_images and not rewrite_reports:
        raise ValueError(
            "--offline-deps-dir with --task-repo requires --reuse-images; "
            "build images first so bundle digests cannot be invalidated"
        )

    if offline_deps_dir is not None:
        # Keep metadata and all worker payloads stable even if the caller changes
        # its working directory while a run is in progress. Re-grading starts no
        # containers, so it must still work after a private bundle has been moved.
        offline_deps_dir = str(Path(offline_deps_dir).expanduser().resolve())
        if not rewrite_reports and not Path(offline_deps_dir).is_dir():
            raise ValueError(
                f"--offline-deps-dir is not a directory: {offline_deps_dir}"
            )

    skip_patch = predictions_path == "no-patch"

    # set open file limit
    assert len(run_id) > 0, "Run ID must be provided"
    # load predictions as map of instance_id to prediction
    loaded_predictions = get_predictions_from_file(
        predictions_path, dataset_name, split, task_repo, instance_ids
    )
    # These flags control trusted grader behavior and are not part of the prediction
    # format. Never let a submitted JSON/JSONL file opt into reference-only assets or
    # claim that its patch was intentionally skipped.
    reference_patch = predictions_path == "gold"
    predictions = [
        {
            **prediction,
            "skip_patch": skip_patch,
            "reference_patch": reference_patch,
        }
        for prediction in loaded_predictions
    ]
    predictions = {pred["instance_id"]: pred for pred in predictions}
    if not rewrite_reports:
        write_run_metadata(
            run_id,
            dataset_name,
            split,
            task_repo,
            allow_network=allow_network,
            offline_deps_dir=offline_deps_dir,
            reuse_images=reuse_images,
            prediction_mode=(
                "gold"
                if predictions_path == "gold"
                else "no-patch"
                if predictions_path == "no-patch"
                else "predictions"
            ),
        )

    # get dataset from predictions
    dataset = get_dataset_from_preds(
        dataset_name,
        split,
        instance_ids,
        predictions,
        run_id,
        rewrite_reports,
        task_repo=task_repo,
    )
    full_dataset = load_instances(dataset_name, split, instance_ids, task_repo)

    if not rewrite_reports:
        selected_ids = {instance["instance_id"] for instance in dataset}
        declared_ids = _required_offline_deps(task_repo) & selected_ids
        required_ids = {
            instance_id
            for instance_id in declared_ids
            if not skip_patch
            and _patch_changes_root_package_json(
                predictions[instance_id].get("model_patch")
            )
        }
        if required_ids and offline_deps_dir is None:
            raise ValueError(
                "Dependency bundles are required for task-repo evaluation of: "
                + ", ".join(sorted(required_ids))
            )
        if offline_deps_dir is not None:
            # The store is intentionally sparse, but every task declared by this task
            # repo must be present. Other selected tasks simply get no cache mount.
            for instance_id in sorted(required_ids):
                if _offline_deps_bundle_path(offline_deps_dir, instance_id) is None:
                    raise FileNotFoundError(
                        f"No offline dependency bundle for required task {instance_id}"
                    )
            for instance in dataset:
                _offline_deps_bundle_path(offline_deps_dir, instance["instance_id"])

    if modal:
        # run instances on Modal
        if not dataset:
            print("No instances to run.")
        else:
            validate_modal_credentials()
            run_instances_modal(predictions, dataset, full_dataset, run_id, timeout)
        return

    # run instances locally
    if platform.system() == "Linux":
        resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    client = _docker_client()

    if not dataset:
        print("No instances to run.")
        return make_run_report(predictions, full_dataset, run_id, client)
    else:
        # a re-grade reads existing logs and starts no container, so building the
        # images it names would cost hours and change nothing
        if task_repo and not rewrite_reports and not reuse_images:
            _build_before_eval(
                dataset, dataset_name, split, task_repo, max_workers, client
            )
        elif task_repo and not rewrite_reports:
            _require_local_images(dataset, client, task_repo)
        # run instances (images assumed to be pre-built)
        run_instances(
            predictions,
            dataset,
            max_workers,
            run_id,
            timeout,
            rewrite_reports=rewrite_reports,
            skip_patch=skip_patch,
            task_repo=task_repo,
            allow_network=allow_network,
            offline_deps_dir=offline_deps_dir,
            pull_missing=task_repo is None,
        )

    # make final report
    return make_run_report(predictions, full_dataset, run_id, client)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Run evaluation harness for the given dataset and predictions.",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )

    # Common args
    parser.add_argument(
        "-d",
        "--dataset_name",
        default="SWE-bench/SWE-bench_Lite",
        type=str,
        help="Name of dataset or path to JSON file.",
    )
    parser.add_argument(
        "-s", "--split", type=str, default="test", help="Split of the dataset"
    )
    parser.add_argument(
        "-i",
        "--instance_ids",
        nargs="+",
        type=str,
        help="Instance IDs to run (space separated)",
    )
    parser.add_argument(
        "-p",
        "--predictions_path",
        type=str,
        help="Path to predictions file - if 'gold', uses gold predictions",
        required=True,
    )

    # Local execution args
    parser.add_argument(
        "--max_workers",
        type=int,
        default=4,
        help="Maximum number of workers (should be <= 75%% of CPU cores)",
    )
    parser.add_argument(
        "--open_file_limit", type=int, default=4096, help="Open file limit"
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=1_800,
        help="Timeout (in seconds) for running tests for each instance",
    )
    parser.add_argument(
        "-id", "--run_id", type=str, required=True, help="Run ID - identifies the run"
    )
    parser.add_argument(
        "--rewrite_reports",
        type=str2bool,
        default=False,
        help="Doesn't run new instances, only writes reports for instances with existing test outputs",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help=(
            "Allow network access in local evaluation containers (default: "
            "network_mode=none)"
        ),
    )
    parser.add_argument(
        "--offline-deps-dir",
        type=str,
        help=(
            "Private cache root; <instance_id> is mounted as an immutable seed "
            "for /run/swebench-offline"
        ),
    )
    parser.add_argument(
        "--task_repo",
        "--task-repo",
        dest="task_repo",
        type=str,
        default=None,
        help="Task repository used for image builds, fixtures, and bundle provenance",
    )
    parser.add_argument(
        "--reuse_images",
        "--reuse-images",
        dest="reuse_images",
        action="store_true",
        help="Use locally prebuilt task-repo images without rebuilding",
    )
    # Modal execution args
    parser.add_argument("--modal", type=str2bool, default=False, help="Run on Modal")

    args = parser.parse_args()
    main(**vars(args))
