from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Optional, Union, cast

from swebench.types import (
    SWEbenchInstance,
)


@dataclass
class ImageSpec:
    """
    A dataclass that represents an image specification for building Docker images
    for a single SWE-bench instance.
    """

    instance_id: str
    dockerfile: str
    namespace: Optional[str]
    tag: str = "latest"
    arch: str = "amd64"
    context_dir: Optional[str] = None

    def __post_init__(self):
        """Validate the dataclass fields after initialization."""
        if not self.instance_id:
            raise ValueError("instance_id cannot be empty")
        if not self.dockerfile:
            raise ValueError("dockerfile cannot be empty")
        if self.arch not in ["amd64", "arm64"]:
            raise ValueError(
                f"Invalid architecture: {self.arch}. Must be 'x86_64' or 'arm64'"
            )
        if self.namespace is not None and not self.namespace:
            raise ValueError("namespace cannot be empty string if provided")

    @property
    def name(self):
        # keep the published naming; amd64 images are tagged x86_64 as they always were
        arch = "x86_64" if self.arch == "amd64" else self.arch
        key = f"sweb.eval.{arch}.{self.instance_id}:{self.tag}"
        if self.is_remote_image:
            # docker hub doesn't allow dunders in image names, so we replace them with _1776_
            key = f"{self.namespace}/{key}".replace("__", "_1776_")
        return key.lower()

    @property
    def filesafe_name(self):
        return self.name.replace(":", "__")

    @property
    def is_remote_image(self):
        return self.namespace is not None

    @property
    def platform(self):
        if self.arch == "amd64":
            return "linux/amd64"
        elif self.arch == "x86_64":
            return "linux/amd64"
        elif self.arch == "arm64":
            return "linux/arm64/v8"
        else:
            raise ValueError(f"Invalid architecture: {self.arch}")

    @property
    def build_input_digest(self) -> str:
        """Digest the Dockerfile and explicitly public multimodal build inputs."""
        digest = hashlib.sha256()

        def add(name: str, payload: bytes) -> None:
            digest.update(name.encode())
            digest.update(b"\0")
            digest.update(str(len(payload)).encode())
            digest.update(b"\0")
            digest.update(payload)

        add("Dockerfile", self.dockerfile.encode())
        if self.context_dir:
            context = Path(self.context_dir)
            dockerignore = context / ".dockerignore"
            if dockerignore.is_file():
                add(".dockerignore", dockerignore.read_bytes())
            problem_assets = context / "problem_assets"
            if problem_assets.is_dir():
                for asset in sorted(path for path in problem_assets.rglob("*") if path.is_file()):
                    add(asset.relative_to(context).as_posix(), asset.read_bytes())
        return digest.hexdigest()


def image_namespace_and_tag(image: str) -> tuple[str | None, str]:
    """Return the complete registry/repository prefix and tag of an image ref."""
    image = canonical_image_ref(image)
    namespace = image.rsplit("/", 1)[0] if "/" in image else None
    leaf = image.rsplit("/", 1)[-1]
    tag = leaf.rsplit(":", 1)[1] if ":" in leaf else "latest"
    return namespace, tag


def canonical_image_ref(image: str) -> str:
    """Expand Docker Hub short names so Podman and Docker use the same tag."""
    if not image:
        return image
    first = image.split("/", 1)[0]
    if "/" not in image:
        return f"docker.io/library/{image}".lower()
    if "." not in first and ":" not in first and first != "localhost":
        return f"docker.io/{image}".lower()
    return image.lower()


def get_image_specs_from_dataset(
    dataset: Union[list[SWEbenchInstance], list[ImageSpec]],
    dockerfiles: dict[str, str],
    namespace: Optional[str] = None,
    tag: str = "latest",
    context_dirs: Optional[dict] = None,
) -> list[ImageSpec]:
    """
    Idempotent function that converts a list of SWEbenchInstance objects to a list of ImageSpec objects.

    Args:
        dataset: List of SWEbenchInstance objects or ImageSpec objects.
        dockerfiles: Dict mapping instance_id to Dockerfile content.
        namespace: Docker registry namespace.
        tag: Docker image tag.
        context_dirs: Dict mapping instance_id to its build context directory.
    """
    if isinstance(dataset[0], ImageSpec):
        return cast(list[ImageSpec], dataset)
    context_dirs = context_dirs or {}
    return [
        make_image_spec(
            x,
            dockerfiles[x["instance_id"]],
            namespace,
            tag,
            context_dirs.get(x["instance_id"]),
        )
        for x in cast(list[SWEbenchInstance], dataset)
    ]


def make_image_spec(
    instance: SWEbenchInstance,
    dockerfile: str,
    namespace: Optional[str] = None,
    tag: str = "latest",
    context_dir: Optional[str] = None,
) -> ImageSpec:
    """
    Create an ImageSpec from a SWEbenchInstance for image building purposes.

    Args:
        instance: SWEbenchInstance dict.
        dockerfile: Dockerfile content string (pre-generated).
        namespace: Docker registry namespace.
        tag: Docker image tag.
        context_dir: Directory to build in, when the Dockerfile COPYs from it.
    """
    if isinstance(instance, ImageSpec):
        return instance
    assert tag is not None, "tag cannot be None"

    return ImageSpec(
        instance_id=instance["instance_id"],
        dockerfile=dockerfile,
        namespace=namespace,
        tag=tag,
        context_dir=str(context_dir) if context_dir else None,
    )
