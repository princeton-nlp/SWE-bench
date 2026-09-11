import platform as py_platform
import re
from dataclasses import dataclass
from typing import Optional, Union, cast

from swebench.types import (
    SWEbenchInstance,
)

# The published image names spell amd64 "x86_64". That is what is on Docker Hub, so it is
# what the name template has to emit -- but it is not what platform.machine() returns and
# not what Docker calls the platform, hence the three tables below rather than one.
ARCH_IN_IMAGE_NAME = {"amd64": "x86_64", "arm64": "arm64"}
DOCKER_PLATFORMS = {"amd64": "linux/amd64", "arm64": "linux/arm64/v8"}
ARCH_ALIASES = {"amd64": "amd64", "x86_64": "amd64", "arm64": "arm64", "aarch64": "arm64"}

# Matches the architecture segment of a built image name, e.g. the "x86_64" in
# "swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest".
_IMAGE_ARCH_RE = re.compile(r"(sweb\.eval\.)(x86_64|arm64)(\.)", re.IGNORECASE)


def normalize_arch(value: str) -> str:
    """Canonicalise an architecture spelling to 'amd64' or 'arm64'.

    Needed because the three spellings in play disagree: platform.machine() says
    "x86_64"/"aarch64", Docker says "amd64"/"arm64", and the image names say
    "x86_64"/"arm64".
    """
    arch = ARCH_ALIASES.get(str(value).lower())
    if arch is None:
        raise ValueError(
            f"Invalid architecture: {value}. Must be one of {sorted(ARCH_ALIASES)}"
        )
    return arch


def host_arch() -> str:
    """The architecture of the machine this is running on.

    The single host-detection point; everything else takes an explicit arch.
    """
    return normalize_arch(py_platform.machine())


def image_name(
    instance_id: str,
    tag: str = "latest",
    arch: str = "amd64",
    namespace: Optional[str] = None,
) -> str:
    """The image name for an instance. The one place this template lives."""
    key = f"sweb.eval.{ARCH_IN_IMAGE_NAME[normalize_arch(arch)]}.{instance_id}:{tag}"
    if namespace is not None:
        # docker hub doesn't allow dunders in image names, so we replace them with _1776_
        key = f"{namespace}/{key}".replace("__", "_1776_")
    return key.lower()


def image_arch(image: str) -> Optional[str]:
    """The architecture an existing image name is built for, or None if it names none."""
    match = _IMAGE_ARCH_RE.search(image)
    return normalize_arch(match.group(2)) if match else None


def retarget_image(image: str, arch: str) -> str:
    """Rewrite the architecture segment of an existing image name.

    Lets the eval path ask for the arm64 family of an image the dataset names in its
    amd64 family, without rebuilding the name from its parts.
    """
    wanted = ARCH_IN_IMAGE_NAME[normalize_arch(arch)]
    retargeted, count = _IMAGE_ARCH_RE.subn(
        lambda m: f"{m.group(1)}{wanted}{m.group(3)}", image, count=1
    )
    if count == 0:
        raise ValueError(
            f"Cannot retarget {image!r}: it does not name an architecture. Expected a "
            f"sweb.eval.<arch>.<instance_id> image name."
        )
    return retargeted


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
        # Accepts every spelling, including the "x86_64" that platform.machine() returns
        # and that the old error message here claimed was valid while the check rejected it.
        self.arch = normalize_arch(self.arch)
        if self.namespace is not None and not self.namespace:
            raise ValueError("namespace cannot be empty string if provided")

    @property
    def name(self):
        return image_name(self.instance_id, self.tag, self.arch, self.namespace)

    @property
    def filesafe_name(self):
        return self.name.replace(":", "__")

    @property
    def is_remote_image(self):
        return self.namespace is not None

    @property
    def platform(self):
        return DOCKER_PLATFORMS[self.arch]


def get_image_specs_from_dataset(
    dataset: Union[list[SWEbenchInstance], list[ImageSpec]],
    dockerfiles: dict[str, str],
    namespace: Optional[str] = None,
    tag: str = "latest",
    context_dirs: Optional[dict] = None,
    arch: Optional[str] = None,
) -> list[ImageSpec]:
    """
    Idempotent function that converts a list of SWEbenchInstance objects to a list of ImageSpec objects.

    Args:
        dataset: List of SWEbenchInstance objects or ImageSpec objects.
        dockerfiles: Dict mapping instance_id to Dockerfile content.
        namespace: Docker registry namespace.
        tag: Docker image tag.
        context_dirs: Dict mapping instance_id to its build context directory.
        arch: Architecture to build for. Defaults to the host's.
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
            arch=arch,
        )
        for x in cast(list[SWEbenchInstance], dataset)
    ]


def make_image_spec(
    instance: SWEbenchInstance,
    dockerfile: str,
    namespace: Optional[str] = None,
    tag: str = "latest",
    context_dir: Optional[str] = None,
    arch: Optional[str] = None,
) -> ImageSpec:
    """
    Create an ImageSpec from a SWEbenchInstance for image building purposes.

    Args:
        instance: SWEbenchInstance dict.
        dockerfile: Dockerfile content string (pre-generated).
        namespace: Docker registry namespace.
        tag: Docker image tag.
        context_dir: Directory to build in, when the Dockerfile COPYs from it.
        arch: Architecture to build for. Defaults to the host's, so that building on an
            arm64 machine no longer cross-builds amd64 by default.
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
        arch=arch if arch is not None else host_arch(),
    )
