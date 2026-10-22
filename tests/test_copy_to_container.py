"""Copying a file to Docker must not modify files in its source directory."""

import io
import tarfile
from pathlib import Path

import pytest

from swebench.harness.docker_utils import copy_to_container


class RecordingContainer:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.commands = []
        self.archives = []

    def exec_run(self, command):
        self.commands.append(command)
        if self.fail_at == "mkdir":
            raise RuntimeError("container unavailable")

    def put_archive(self, destination, data):
        self.archives.append((destination, data))
        if self.fail_at == "upload":
            raise RuntimeError("container unavailable")


@pytest.mark.parametrize(
    "filename", ["patch.diff", "patch.tar", "patch.tar.gz", "patch"]
)
def test_copy_preserves_source_and_existing_sibling_archive(tmp_path, filename):
    source = tmp_path / filename
    content = b"original source\x00\xff\n"
    source.write_bytes(content)
    source.chmod(0o640)
    sibling = source.with_suffix(".tar")
    if sibling != source:
        sibling.write_bytes(b"unrelated archive")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    container = RecordingContainer()

    copy_to_container(container, source, Path("/testbed/renamed.patch"))

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert container.commands == ["mkdir -p /testbed"]
    assert len(container.archives) == 1
    destination, data = container.archives[0]
    assert destination == "/testbed"
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        assert archive.getnames() == ["renamed.patch"]
        member = archive.getmember("renamed.patch")
        assert member.mode == 0o640
        assert archive.extractfile(member).read() == content


@pytest.mark.parametrize("fail_at", ["mkdir", "upload"])
@pytest.mark.parametrize("existing_archive", [False, True])
def test_container_failure_preserves_source_directory(
    tmp_path, fail_at, existing_archive
):
    source = tmp_path / "patch.diff"
    source.write_bytes(b"original patch")
    if existing_archive:
        source.with_suffix(".tar").write_bytes(b"unrelated archive")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    container = RecordingContainer(fail_at=fail_at)

    with pytest.raises(RuntimeError, match="container unavailable"):
        copy_to_container(container, source, Path("/testbed/patch.diff"))

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


@pytest.mark.parametrize("filename", ["patch.diff", "patch.tar"])
def test_packaging_failure_preserves_source_directory(tmp_path, monkeypatch, filename):
    source = tmp_path / filename
    source.write_bytes(b"original patch")
    if source.suffix != ".tar":
        source.with_suffix(".tar").write_bytes(b"unrelated archive")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    container = RecordingContainer()

    def fail_add(archive, *args, **kwargs):
        archive.fileobj.write(b"partial archive")
        raise OSError("cannot package source")

    monkeypatch.setattr(tarfile.TarFile, "add", fail_add)
    with pytest.raises(OSError, match="cannot package source"):
        copy_to_container(container, source, Path("/testbed/patch.diff"))

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert not container.commands
    assert not container.archives


def test_copy_directory_keeps_recursive_archive_contents(tmp_path):
    source = tmp_path / "assets"
    source.mkdir()
    (source / "image.png").write_bytes(b"image data")
    container = RecordingContainer()

    copy_to_container(container, source, Path("/testbed/images"))

    with tarfile.open(fileobj=io.BytesIO(container.archives[0][1])) as archive:
        assert archive.getnames() == ["images", "images/image.png"]
        assert archive.extractfile("images/image.png").read() == b"image data"
    assert list(tmp_path.iterdir()) == [source]


def test_destination_without_parent_is_rejected(tmp_path):
    source = tmp_path / "patch.diff"
    source.write_bytes(b"patch")
    container = RecordingContainer()

    with pytest.raises(ValueError, match="parent directory cannot be empty"):
        copy_to_container(container, source, Path("patch.diff"))

    assert not container.commands
    assert not container.archives
    assert list(tmp_path.iterdir()) == [source]
