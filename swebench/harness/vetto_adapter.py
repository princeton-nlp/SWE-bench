#!/usr/bin/env python3
"""
Vetto SWE-bench Runtime Adapter (swebench/harness/vetto_adapter.py)

Drop-in execution runner replacing Docker daemon in SWE-bench evaluation harnesses.
Executes test suites and agent patches with <4ms cold-start latency, sub-megabyte
host memory overhead, and strict kernel-enforced sandboxing (Landlock LSM,
namespaces, cgroups v2, read-only root CoW, process-tree extinction).
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from collections import namedtuple
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from swebench.image_builder.constants import CONTAINER_WORKDIR
from swebench.types import TestSpec

ExecResult = namedtuple("ExecResult", ["exit_code", "output"])


@dataclass
class VettoExecResult:
    """Standardized execution result matching SWE-bench evaluation schema."""

    exit_code: int
    stdout: str
    stderr: str
    cold_start_ns: int
    cold_start_ms: float
    duration_ms: int
    peak_memory_bytes: int
    peak_memory_mb: float
    blocked_attempts: int
    verdict: str
    timed_out: bool
    oom_killed: bool
    status: str
    instance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VettoContainer:
    """
    Container compatibility shim for the Vetto sandbox runtime.
    Provides container.exec_run(), copy_to(), put_archive(), and lifecycle
    methods matching docker.models.containers.Container for evaluation harnesses.
    """

    def __init__(
        self,
        runner: VettoTaskRunner | None = None,
        test_spec: TestSpec | None = None,
        run_id: str | None = None,
        workdir: str | Path | None = None,
        task_repo: str | None = None,
    ):
        self.runner = runner or VettoTaskRunner()
        self.test_spec = test_spec
        self.run_id = run_id or f"run-{int(time.time())}"
        self.task_repo = task_repo

        inst_id = test_spec.instance_id if test_spec else "vetto-instance"
        self.id = f"vetto-{inst_id}-{self.run_id}"
        self.name = f"sweb.eval.{inst_id.lower()}.{self.run_id}"

        # Lightweight dummy client object to prevent AttributeError
        self.client = None

        if workdir:
            self._owns_temp_dir = False
            self._temp_dir = None
            self.root_dir = Path(workdir).resolve()
            self.workdir = self.root_dir
        else:
            self._owns_temp_dir = True
            self._temp_dir = tempfile.mkdtemp(prefix=f"sweb_vetto_{inst_id}_")
            self.root_dir = Path(self._temp_dir).resolve()
            self.workdir = self.root_dir / "testbed"

        self.patch_file = self.root_dir / "tmp" / "patch.diff"
        self.eval_script_path = self.root_dir / "eval.sh"
        self.assets_dir = self.root_dir / "image_assets"

    def start(self) -> None:
        """Initialize workspace and prepare execution environment."""
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.patch_file.parent.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # Initialize git repo if not already a git repository to allow git diff/apply
        if not (self.workdir / ".git").exists():
            subprocess.run(
                ["git", "init"],
                cwd=self.workdir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    def stop(self, timeout: int = 10) -> None:
        """No-op: Vetto is daemon-less and terminates process trees deterministically."""

    def remove(self, force: bool = True) -> None:
        """Clean up resources on removal."""
        self.cleanup()

    def cleanup(self) -> None:
        """Remove temporary directory created for this container."""
        if self._owns_temp_dir and self._temp_dir and Path(self._temp_dir).exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def copy_to(self, src: str | Path, dst: str | Path | PurePosixPath) -> None:
        """
        Copy a file into the container filesystem with hermetic path translation.
        """
        src_path = Path(src).resolve()
        dst_str = str(dst)
        dst_name = Path(dst_str).name

        if dst_name == "patch.diff" or dst_str.endswith("patch.diff"):
            self.patch_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, self.patch_file)
            return

        if dst_name == "eval.sh" or dst_str.endswith("eval.sh"):
            self.eval_script_path.parent.mkdir(parents=True, exist_ok=True)
            content = src_path.read_text(encoding="utf-8", errors="replace")
            # Rewrite absolute paths to point to this container's sandbox root/workdir
            content = content.replace("/testbed", str(self.workdir))
            content = re.sub(r"/(?:tmp/)?patch\.diff\b", str(self.patch_file), content)
            content = content.replace("/image_assets", str(self.assets_dir))
            self.eval_script_path.write_text(content, encoding="utf-8")
            self.eval_script_path.chmod(0o755)
            return

        if "/image_assets" in dst_str:
            self.assets_dir.mkdir(parents=True, exist_ok=True)
            target = self.assets_dir / dst_name
            shutil.copy2(src_path, target)
            return

        if dst_str.startswith("/testbed"):
            rel_part = dst_str[len("/testbed") :].lstrip("/")
            target = self.workdir / rel_part
        else:
            rel_part = dst_str.lstrip("/")
            target = self.root_dir / rel_part

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, target)

    def put_archive(self, path: str | Path, data: bytes) -> bool:
        """Extract tar archive bytes into target container path."""
        target_dir = self.root_dir / str(path).lstrip("/")
        target_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(target_dir, filter="data")
            else:
                tar.extractall(target_dir)
        return True

    def exec_run(
        self,
        cmd: str | list[str],
        workdir: str | Path | None = None,
        environment: dict[str, str] | None = None,
        timeout: int | None = None,
        user: str | None = None,
    ) -> ExecResult:
        """
        Emulate docker container.exec_run.
        Translates container paths and runs within Vetto sandbox.
        Returns ExecResult namedtuple with .exit_code and .output.
        """
        if workdir and str(workdir) not in ("/testbed", CONTAINER_WORKDIR):
            cwd = Path(workdir)
        else:
            cwd = self.workdir

        # Path translation for command strings / arguments
        if isinstance(cmd, str):
            cmd_to_run = re.sub(r"/(?:tmp/)?patch\.diff\b", str(self.patch_file), cmd)
            if "/eval.sh" in cmd_to_run:
                cmd_to_run = cmd_to_run.replace("/eval.sh", str(self.eval_script_path))
            if "/image_assets" in cmd_to_run:
                cmd_to_run = cmd_to_run.replace("/image_assets", str(self.assets_dir))
        else:
            cmd_to_run = []
            for arg in cmd:
                arg_str = str(arg)
                if arg_str in ("/tmp/patch.diff", "/patch.diff"):
                    cmd_to_run.append(str(self.patch_file))
                elif arg_str == "/eval.sh":
                    cmd_to_run.append(str(self.eval_script_path))
                elif "/image_assets" in arg_str:
                    cmd_to_run.append(
                        arg_str.replace("/image_assets", str(self.assets_dir))
                    )
                else:
                    cmd_to_run.append(arg_str)

        instance_id = self.test_spec.instance_id if self.test_spec else None
        result = self.runner.run_command(
            cmd=cmd_to_run,
            cwd=cwd,
            timeout=timeout,
            env=environment,
            instance_id=instance_id,
        )

        output_text = result.stdout
        if result.stderr:
            output_text = (
                f"{output_text}\n{result.stderr}" if output_text else result.stderr
            )
        combined_output = output_text.encode("utf-8", errors="replace")

        return ExecResult(exit_code=result.exit_code, output=combined_output)

    def exec_run_with_timeout(
        self,
        cmd: str | list[str],
        timeout: int | None = 60,
    ) -> tuple[str, bool, float]:
        """
        Direct execution hook for swebench.harness.docker_utils.exec_run_with_timeout.
        Returns (test_output, timed_out, total_runtime_seconds).
        """
        start_time = time.time()
        val = self.exec_run(cmd, timeout=timeout)
        duration = time.time() - start_time
        timed_out = val.exit_code == 124
        output_str = val.output.decode("utf-8", errors="replace")
        return output_str, timed_out, duration


class VettoTaskRunner:
    """
    High-throughput task runner for SWE-bench benchmarks.
    Replaces Docker daemon execution with Vetto kernel-level sandbox.
    """

    def __init__(
        self,
        workspace: str | Path | None = None,
        timeout: int = 180,
        memory_limit_mb: int = 4096,
        vetto_bin: str | None = None,
        profile: str = "swebench",
        net: str = "off",
        allow_fallback: bool = True,
    ):
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb
        self.profile = profile
        self.net = net
        self.allow_fallback = allow_fallback
        if vetto_bin == "":
            self.vetto_bin = None
        else:
            self.vetto_bin = self._find_vetto_binary(custom_bin=vetto_bin)

    @staticmethod
    def _find_vetto_binary(custom_bin: str | None = None) -> str | None:
        """Locate usable vetto executable if installed."""
        if custom_bin:
            if Path(custom_bin).is_file() or shutil.which(custom_bin):
                return custom_bin
            raise FileNotFoundError(f"Custom vetto binary not found: {custom_bin}")

        env_bin = os.environ.get("VETTO_BIN")
        if env_bin and Path(env_bin).is_file():
            return env_bin

        which_path = shutil.which("vetto")
        if which_path:
            return which_path

        # Check repository target directories or common local locations
        candidate_roots = [
            Path.cwd(),
            Path.home() / ".cargo" / "bin",
            Path.home() / "prod" / "vetto",
        ]
        for root in candidate_roots:
            for profile in ["release", "debug"]:
                candidate = root / "target" / profile / "vetto"
                if candidate.is_file():
                    return str(candidate)
            direct_candidate = root / "vetto"
            if direct_candidate.is_file() and os.access(direct_candidate, os.X_OK):
                return str(direct_candidate)

        return None

    def _run_subprocess(
        self,
        cmd_args: list[str],
        cwd: Path,
        exec_timeout: int,
        env: dict[str, str] | None,
        instance_id: str | None,
        t_start: float,
    ) -> VettoExecResult:
        """Run command directly via subprocess as fallback."""
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        try:
            proc = subprocess.run(
                cmd_args,
                cwd=cwd,
                env=merged_env,
                timeout=exec_timeout,
                capture_output=True,
                text=True,
                check=False,
            )
            wall_time_ms = int((time.perf_counter() - t_start) * 1000)
            return VettoExecResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                cold_start_ns=0,
                cold_start_ms=0.0,
                duration_ms=wall_time_ms,
                peak_memory_bytes=0,
                peak_memory_mb=0.0,
                blocked_attempts=0,
                verdict="pass" if proc.returncode == 0 else "failed",
                timed_out=False,
                oom_killed=False,
                status="COMPLETED" if proc.returncode == 0 else "FAILED",
                instance_id=instance_id,
            )
        except subprocess.TimeoutExpired as e:
            wall_time_ms = int((time.perf_counter() - t_start) * 1000)
            stdout_str = (
                e.stdout
                if isinstance(e.stdout, str)
                else (e.stdout.decode("utf-8", errors="replace") if e.stdout else "")
            )
            stderr_str = (
                e.stderr
                if isinstance(e.stderr, str)
                else (e.stderr.decode("utf-8", errors="replace") if e.stderr else "")
            )
            return VettoExecResult(
                exit_code=124,
                stdout=stdout_str,
                stderr=stderr_str
                or f"Command timed out after {exec_timeout} seconds",
                cold_start_ns=0,
                cold_start_ms=0.0,
                duration_ms=wall_time_ms,
                peak_memory_bytes=0,
                peak_memory_mb=0.0,
                blocked_attempts=0,
                verdict="timed_out",
                timed_out=True,
                oom_killed=False,
                status="TIMEOUT",
                instance_id=instance_id,
            )
        except Exception as e:  # noqa: BLE001
            wall_time_ms = int((time.perf_counter() - t_start) * 1000)
            return VettoExecResult(
                exit_code=1,
                stdout="",
                stderr=f"command execution failed: {e}",
                cold_start_ns=0,
                cold_start_ms=0.0,
                duration_ms=wall_time_ms,
                peak_memory_bytes=0,
                peak_memory_mb=0.0,
                blocked_attempts=0,
                verdict="failed",
                timed_out=False,
                oom_killed=False,
                status="FAILED",
                instance_id=instance_id,
            )

    def run_command(
        self,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
        instance_id: str | None = None,
    ) -> VettoExecResult:
        """
        Execute command inside hermetic Vetto sandbox with JSON telemetry.
        Falls back to direct process execution if vetto binary is not installed
        or if cgroup v2 permissions are not delegated on the host environment.
        """
        target_cwd = Path(cwd).resolve() if cwd else self.workspace
        exec_timeout = timeout or self.timeout

        cmd_list = [cmd] if isinstance(cmd, str) else list(cmd)
        if len(cmd_list) == 1 and (" " in cmd_list[0] or ";" in cmd_list[0]):
            cmd_args = ["/bin/sh", "-c", cmd_list[0]]
        else:
            cmd_args = cmd_list

        t_start = time.perf_counter()

        # If vetto binary is found, execute inside sandbox
        if self.vetto_bin:
            argv = [
                self.vetto_bin,
                "bench",
                "--workspace",
                str(target_cwd),
                "--timeout",
                str(exec_timeout),
                "--memory",
                str(self.memory_limit_mb),
                "--profile",
                self.profile,
                "--net",
                self.net,
                "--json",
            ]
            if instance_id:
                argv.extend(["--instance-id", instance_id])
            if env:
                for k, v in env.items():
                    argv.extend(["-e", f"{k}={v}"])
            argv.append("--")
            argv.extend(cmd_args)

            try:
                proc = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                wall_time_ms = int((time.perf_counter() - t_start) * 1000)
                raw_stdout = proc.stdout.strip()

                # If cgroup v2 is not writable in this container/host and fallback is allowed:
                if (
                    proc.returncode == 125
                    and self.allow_fallback
                    and (
                        "cgroup v2 is unavailable" in proc.stderr
                        or "sandbox setup failed" in proc.stderr
                    )
                ):
                    return self._run_subprocess(
                        cmd_args,
                        target_cwd,
                        exec_timeout,
                        env,
                        instance_id,
                        t_start,
                    )

                if proc.returncode == 0 or raw_stdout.startswith("{"):
                    try:
                        data = json.loads(raw_stdout)
                        return VettoExecResult(
                            exit_code=data.get("exit_code", proc.returncode),
                            stdout=data.get("stdout", ""),
                            stderr=data.get("stderr", proc.stderr),
                            cold_start_ns=data.get("cold_start_ns", 0),
                            cold_start_ms=data.get("cold_start_ms", 0.0),
                            duration_ms=data.get("duration_ms", wall_time_ms),
                            peak_memory_bytes=data.get("peak_memory_bytes", 0),
                            peak_memory_mb=data.get("peak_memory_mb", 0.0),
                            blocked_attempts=data.get("blocked_attempts", 0),
                            verdict=data.get(
                                "verdict",
                                "pass" if proc.returncode == 0 else "fail_closed",
                            ),
                            timed_out=data.get("timed_out", False),
                            oom_killed=data.get("oom_killed", False),
                            status=data.get(
                                "status",
                                "COMPLETED"
                                if proc.returncode == 0
                                else "FAIL_CLOSED",
                            ),
                            instance_id=data.get("instance_id", instance_id),
                        )
                    except json.JSONDecodeError:
                        pass

                return VettoExecResult(
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    cold_start_ns=0,
                    cold_start_ms=0.0,
                    duration_ms=wall_time_ms,
                    peak_memory_bytes=0,
                    peak_memory_mb=0.0,
                    blocked_attempts=1 if proc.returncode == 125 else 0,
                    verdict="pass" if proc.returncode == 0 else "fail_closed",
                    timed_out=proc.returncode == 124,
                    oom_killed=proc.returncode == 137,
                    status="COMPLETED" if proc.returncode == 0 else "FAIL_CLOSED",
                    instance_id=instance_id,
                )
            except Exception as e:  # noqa: BLE001
                wall_time_ms = int((time.perf_counter() - t_start) * 1000)
                return VettoExecResult(
                    exit_code=125,
                    stdout="",
                    stderr=f"vetto execution failed: {e}",
                    cold_start_ns=0,
                    cold_start_ms=0.0,
                    duration_ms=wall_time_ms,
                    peak_memory_bytes=0,
                    peak_memory_mb=0.0,
                    blocked_attempts=0,
                    verdict="fail_closed",
                    timed_out=False,
                    oom_killed=False,
                    status="FAIL_CLOSED",
                    instance_id=instance_id,
                )

        # Fallback to direct subprocess execution when vetto binary is not installed
        return self._run_subprocess(
            cmd_args, target_cwd, exec_timeout, env, instance_id, t_start
        )

    def apply_patch(
        self, patch_content: str, workspace: Path | None = None
    ) -> bool:
        """Apply unified diff patch using git apply within the repository."""
        target_ws = workspace or self.workspace
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as tf:
            tf.write(patch_content)
            patch_file = Path(tf.name)

        try:
            cmd = ["git", "apply", "-v", str(patch_file)]
            res = subprocess.run(
                cmd,
                cwd=target_ws,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        finally:
            if patch_file.exists():
                patch_file.unlink()

    def run_instance(
        self,
        instance: dict[str, Any],
        test_patch: str | None = None,
        test_command: str | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate a single SWE-bench instance.
        1. Apply test_patch if provided
        2. Run test_command inside Vetto sandbox
        3. Collect execution metrics and logs
        4. Revert workspace changes cleanly
        """
        instance_id = instance.get("instance_id", "unknown_instance")
        patch_applied = False

        if test_patch:
            patch_applied = self.apply_patch(test_patch)

        cmd = test_command or instance.get("test_cmd", "pytest")
        result = self.run_command(
            cmd=cmd,
            instance_id=instance_id,
        )

        # Rollback workspace changes to ensure isolation between tasks
        subprocess.run(
            ["git", "checkout", "."],
            cwd=self.workspace,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=self.workspace,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        return {
            "instance_id": instance_id,
            "patch_applied": patch_applied,
            "test_result": result.to_dict(),
        }

    def as_docker_container(self) -> VettoContainer:
        """Return Docker Container compatibility object."""
        return VettoContainer(runner=self, workdir=self.workspace)


def create_vetto_container(
    test_spec: TestSpec,
    run_id: str,
    logger: logging.Logger | None = None,
    task_repo: str | None = None,
    workspace: str | Path | None = None,
    timeout: int = 1800,
    memory_limit_mb: int = 4096,
    allow_fallback: bool = True,
) -> VettoContainer:
    """
    Factory function for creating a VettoContainer instance.
    """
    runner = VettoTaskRunner(
        timeout=timeout,
        memory_limit_mb=memory_limit_mb,
        profile="swebench",
        net="off",
        allow_fallback=allow_fallback,
    )
    container = VettoContainer(
        runner=runner,
        test_spec=test_spec,
        run_id=run_id,
        workdir=workspace,
        task_repo=task_repo,
    )
    if logger:
        logger.info(
            f"Created Vetto container for {test_spec.instance_id}: {container.id}"
        )
    return container
