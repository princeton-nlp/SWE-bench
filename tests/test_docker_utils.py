"""Unit tests for exec_run_with_timeout process-group termination and stream cleanup."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from swebench.harness import docker_utils
from swebench.harness.docker_utils import exec_run_with_timeout


class _BlockingStream:
    """Yields initial chunks then blocks until close() is called."""

    def __init__(self, initial: list[bytes] | None = None):
        self._chunks = list(initial or [])
        self._closed = threading.Event()
        self.closed = False

    def __iter__(self):
        yield from self._chunks
        self._closed.wait(timeout=5)

    def close(self):
        self.closed = True
        self._closed.set()


class _FakeAPI:
    def __init__(
        self, stream, pid: int | None = 4321, inspect_error: Exception | None = None
    ):
        self.stream = stream
        self.pid = pid
        self.inspect_error = inspect_error
        self.created: list[tuple[str, str]] = []
        self.inspected: list[str] = []

    def exec_create(self, container_id: str, cmd: str) -> dict[str, str]:
        self.created.append((container_id, cmd))
        return {"Id": "exec-123"}

    def exec_start(self, exec_id: str, stream: bool = True):
        assert exec_id == "exec-123"
        assert stream is True
        return self.stream

    def exec_inspect(self, exec_id: str) -> dict[str, int | None]:
        self.inspected.append(exec_id)
        if self.inspect_error is not None:
            raise self.inspect_error
        return {"Pid": self.pid}


class _FakeContainer:
    def __init__(
        self, stream, pid: int | None = 4321, inspect_error: Exception | None = None
    ):
        self.id = "container-abc"
        self.api = _FakeAPI(stream, pid=pid, inspect_error=inspect_error)
        self.client = SimpleNamespace(api=self.api)
        self.exec_runs: list[tuple[str, dict]] = []

    def exec_run(self, cmd: str, **kwargs):
        self.exec_runs.append((cmd, kwargs))


def test_exec_run_with_timeout_completes_normally():
    stream = _BlockingStream([b"hello ", b"world\n"])
    stream._closed.set()
    container = _FakeContainer(stream)

    output, timed_out, elapsed = exec_run_with_timeout(
        container, "/bin/bash /eval.sh", timeout=5
    )

    assert output == "hello world\n"
    assert timed_out is False
    assert elapsed >= 0
    assert stream.closed is True
    assert container.exec_runs == []


def test_exec_run_with_timeout_kills_process_group_and_closes_stream():
    stream = _BlockingStream([b"partial output\n"])
    container = _FakeContainer(stream, pid=4321)

    output, timed_out, _ = exec_run_with_timeout(
        container, "/bin/bash /eval.sh", timeout=0.05
    )

    assert output == "partial output\n"
    assert timed_out is True
    assert stream.closed is True
    assert container.api.inspected == ["exec-123"]
    assert container.exec_runs == [
        (
            "/bin/sh -c 'kill -TERM -4321 4321 2>/dev/null; "
            "sleep 2; kill -KILL -4321 4321 2>/dev/null'",
            {"detach": True},
        )
    ]


def test_exec_run_with_timeout_uses_daemon_reader_thread(monkeypatch):
    seen_daemons: list[bool] = []
    real_thread = threading.Thread

    def recording_thread(*args, **kwargs):
        thread = real_thread(*args, **kwargs)
        seen_daemons.append(thread.daemon)
        return thread

    monkeypatch.setattr(docker_utils.threading, "Thread", recording_thread)
    stream = _BlockingStream([b"ok"])
    stream._closed.set()
    container = _FakeContainer(stream)

    output, timed_out, _ = exec_run_with_timeout(container, "echo ok", timeout=5)

    assert output == "ok"
    assert timed_out is False
    assert seen_daemons == [True]


def test_exec_run_with_timeout_closes_stream_when_inspect_raises():
    stream = _BlockingStream([b"before timeout\n"])
    container = _FakeContainer(stream, inspect_error=RuntimeError("container gone"))

    output, timed_out, _ = exec_run_with_timeout(
        container, "/bin/bash /eval.sh", timeout=0.05
    )

    assert output == "before timeout\n"
    assert timed_out is True
    assert stream.closed is True
    assert container.exec_runs == []


def test_exec_run_with_timeout_skips_kill_when_pid_is_zero():
    stream = _BlockingStream([b"stalled\n"])
    container = _FakeContainer(stream, pid=0)

    output, timed_out, _ = exec_run_with_timeout(
        container, "/bin/bash /eval.sh", timeout=0.05
    )

    assert output == "stalled\n"
    assert timed_out is True
    assert stream.closed is True
    assert container.exec_runs == []


def test_exec_run_with_timeout_propagates_worker_exception():
    stream = _BlockingStream()
    container = _FakeContainer(stream)

    def broken_exec_create(container_id: str, cmd: str):
        raise RuntimeError("docker socket error")

    container.api.exec_create = broken_exec_create

    with pytest.raises(RuntimeError, match="docker socket error"):
        exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout=5)
