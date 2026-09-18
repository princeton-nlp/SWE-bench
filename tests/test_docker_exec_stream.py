"""Docker exec stream collection and cleanup.

An unclosed stream's urllib3 response is finalized by the garbage collector, which
reports `ValueError: I/O operation on closed file` from inside __del__ and leaves the
socket open until then.
"""

from types import SimpleNamespace

from swebench.harness.docker_utils import (
    _close_exec_stream,
    _unwrap_docker_stream_frames,
    exec_run_with_timeout,
)


class _Closeable:
    def __init__(self, raises=False):
        self.closed = False
        self._raises = raises

    def close(self):
        if self._raises:
            raise ValueError("I/O operation on closed file")
        self.closed = True


class _Stream(_Closeable):
    def __init__(self, response=None, raises=False):
        super().__init__(raises=raises)
        self._response = response


def test_closes_stream_and_response():
    response = _Closeable()
    stream = _Stream(response)
    _close_exec_stream(stream)
    assert stream.closed and response.closed


def test_none_is_a_noop():
    _close_exec_stream(None)  # a timeout before exec_start leaves it unset


def test_a_raising_stream_still_closes_the_response():
    # CancellableStream.close() reaches into _fp.fp and throws when already closed;
    # the response underneath is the one whose finalizer produces the noise.
    response = _Closeable()
    _close_exec_stream(_Stream(response, raises=True))
    assert response.closed


def test_a_raising_response_is_swallowed():
    stream = _Stream(_Closeable(raises=True))
    _close_exec_stream(stream)
    assert stream.closed


def test_stream_without_a_response_attribute():
    stream = _Closeable()
    _close_exec_stream(stream)
    assert stream.closed


def test_double_close_is_safe():
    response = _Closeable()
    stream = _Stream(response)
    _close_exec_stream(stream)
    _close_exec_stream(stream)  # reader thread and timeout path can both call it
    assert stream.closed and response.closed


def _frame(payload: bytes, stream_id: int = 1) -> bytes:
    return bytes([stream_id, 0, 0, 0]) + len(payload).to_bytes(4, "big") + payload


def test_unwraps_a_complete_nested_docker_frame_sequence():
    framed = _frame(b"first\n") + _frame(b"second\n", stream_id=2)
    assert _unwrap_docker_stream_frames(framed) == b"first\nsecond\n"


def test_unwraps_multiple_nested_frame_layers():
    framed = _frame(_frame(b"PASS target\n"))
    assert _unwrap_docker_stream_frames(framed) == b"PASS target\n"


def test_does_not_strip_a_truncated_frame():
    framed = _frame(b"PASS target\n")[:-1]
    assert _unwrap_docker_stream_frames(framed) == framed


def test_does_not_strip_valid_frame_followed_by_unframed_bytes():
    mixed = _frame(b"PASS target\n") + b"ordinary output\n"
    assert _unwrap_docker_stream_frames(mixed) == mixed


def test_does_not_strip_an_invalid_header():
    invalid = bytes([1, 0, 1, 0]) + (4).to_bytes(4, "big") + b"test"
    assert _unwrap_docker_stream_frames(invalid) == invalid


class _ExecStream:
    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    def __iter__(self):
        return iter(self._chunks)

    def close(self):
        self.closed = True


class _ExecApi:
    def __init__(self, chunks):
        self.stream = _ExecStream(chunks)
        self.start_kwargs = None

    def exec_create(self, container_id, cmd):
        assert container_id == "container-id"
        assert cmd == "run tests"
        return {"Id": "exec-id"}

    def exec_start(self, exec_id, **kwargs):
        assert exec_id == "exec-id"
        self.start_kwargs = kwargs
        return self.stream


def test_exec_merges_tuple_frames_in_arrival_order():
    api = _ExecApi([(b"stdout-1\n", None), (None, b"stderr\n"), (b"stdout-2\n", None)])
    container = SimpleNamespace(id="container-id", client=SimpleNamespace(api=api))

    output, timed_out, _ = exec_run_with_timeout(container, "run tests")

    assert output == "stdout-1\nstderr\nstdout-2\n"
    assert timed_out is False
    assert api.start_kwargs == {"stream": True}
    assert api.stream.closed


def test_exec_unwraps_nested_frames_left_by_a_compatible_daemon():
    # The daemon may nest framing for some outer frames but not others.  Validate
    # and unwrap each SDK-provided frame before concatenating the complete output.
    api = _ExecApi(
        [
            (b"unframed prefix\n", None),
            (_frame(b"PASS one\n") + _frame(b"PASS two\n"), None),
            (None, b"unframed suffix\n"),
        ]
    )
    container = SimpleNamespace(id="container-id", client=SimpleNamespace(api=api))

    output, timed_out, _ = exec_run_with_timeout(container, "run tests")

    assert output == "unframed prefix\nPASS one\nPASS two\nunframed suffix\n"
    assert timed_out is False


def test_exec_accepts_raw_chunks_from_a_client_that_ignores_demux():
    api = _ExecApi([b"raw ", b"output"])
    container = SimpleNamespace(id="container-id", client=SimpleNamespace(api=api))

    output, timed_out, _ = exec_run_with_timeout(container, "run tests")

    assert output == "raw output"
    assert timed_out is False
