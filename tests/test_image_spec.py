"""How an instance's image is named, and for which architecture.

There are two independent derivations of the same name -- `ImageSpec.name` on the build
side and the dataset's `image` column on the evaluation side -- and they have to agree.
When they did not, the build "succeeded" and the evaluation quietly pulled the other
architecture's image instead, so these are the tests that hold the template in one place.
"""

import pytest

from swebench.image_builder.image_spec import (
    DOCKER_PLATFORMS,
    ImageSpec,
    host_arch,
    image_arch,
    image_name,
    make_image_spec,
    normalize_arch,
    retarget_image,
)


def _spec(**kwargs) -> ImageSpec:
    return ImageSpec(
        instance_id="astropy__astropy-12907",
        dockerfile="FROM scratch",
        namespace="swebench",
        **kwargs,
    )


@pytest.mark.parametrize(
    "spelling,expected",
    [
        ("amd64", "amd64"),
        # what platform.machine() returns on x86 Linux, and what the image names use
        ("x86_64", "amd64"),
        ("X86_64", "amd64"),
        ("arm64", "arm64"),
        # what platform.machine() returns on Graviton
        ("aarch64", "arm64"),
        ("AArch64", "arm64"),
    ],
)
def test_every_spelling_in_play_normalizes(spelling, expected):
    assert normalize_arch(spelling) == expected


def test_an_unknown_architecture_is_refused():
    with pytest.raises(ValueError, match="Invalid architecture"):
        normalize_arch("riscv64")


def test_the_host_architecture_is_one_of_the_two():
    assert host_arch() in DOCKER_PLATFORMS


def test_image_names_spell_amd64_as_x86_64():
    # the published names say x86_64, which is neither what Docker nor platform.machine() say
    assert image_name("google__gson-2479", namespace="swebench") == (
        "swebench/sweb.eval.x86_64.google_1776_gson-2479:latest"
    )
    assert image_name("google__gson-2479", namespace="swebench", arch="arm64") == (
        "swebench/sweb.eval.arm64.google_1776_gson-2479:latest"
    )


def test_a_name_without_a_namespace_keeps_its_dunders():
    # the _1776_ mangling exists because docker hub disallows dunders in *repository*
    # names; a local name has no repository, so nothing is mangled
    assert image_name("a__a-1") == "sweb.eval.x86_64.a__a-1:latest"


def test_the_tag_is_carried_through():
    assert (
        image_name("a__a-1", tag="v1", namespace="ns")
        == "ns/sweb.eval.x86_64.a_1776_a-1:v1"
    )


def test_the_spec_accepts_the_host_spelling_of_amd64():
    # platform.machine() returns "x86_64", which __post_init__ used to reject while its
    # error message claimed it was valid
    assert _spec(arch="x86_64").arch == "amd64"
    assert _spec(arch="aarch64").arch == "arm64"


def test_the_spec_refuses_an_unknown_architecture():
    with pytest.raises(ValueError, match="Invalid architecture"):
        _spec(arch="ppc64le")


def test_the_spec_name_is_the_shared_template():
    spec = _spec(arch="arm64")
    assert spec.name == image_name(spec.instance_id, spec.tag, "arm64", spec.namespace)
    assert spec.filesafe_name == spec.name.replace(":", "__")


@pytest.mark.parametrize(
    "arch,expected", [("amd64", "linux/amd64"), ("arm64", "linux/arm64/v8")]
)
def test_the_platform_matches_the_architecture(arch, expected):
    assert _spec(arch=arch).platform == expected


def test_the_architecture_of_a_published_name_is_readable():
    assert image_arch("swebench/sweb.eval.x86_64.a_1776_a-1:latest") == "amd64"
    assert image_arch("swebench/sweb.eval.arm64.a_1776_a-1:latest") == "arm64"


def test_a_name_that_declares_no_architecture_reads_as_none():
    # a custom image is left alone rather than being rewritten into a name nobody built
    assert image_arch("ghcr.io/someone/custom:latest") is None


def test_retargeting_swaps_only_the_architecture_segment():
    amd64 = "swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest"
    arm64 = "swebench/sweb.eval.arm64.astropy_1776_astropy-12907:latest"
    assert retarget_image(amd64, "arm64") == arm64
    assert retarget_image(arm64, "amd64") == amd64
    # idempotent, and reachable from the host spellings too
    assert retarget_image(arm64, "aarch64") == arm64
    assert retarget_image(amd64, "x86_64") == amd64


def test_retargeting_a_name_without_an_architecture_is_refused():
    with pytest.raises(ValueError, match="does not name an architecture"):
        retarget_image("ghcr.io/someone/custom:latest", "arm64")


def test_the_factory_defaults_to_the_host_architecture():
    # the dataclass default stays amd64 -- it is a record -- but building on Graviton
    # must not silently cross-build amd64
    instance = {"instance_id": "a__a-1"}
    assert make_image_spec(instance, "FROM scratch").arch == host_arch()
    assert make_image_spec(instance, "FROM scratch", arch="arm64").arch == "arm64"


def test_a_dataset_already_on_arm64_reports_no_retargeting():
    """The reason the unavailable-image check cannot be gated on a rewrite count.

    A dataset published for arm64 -- or one whose image column was rewritten before the
    run -- needs no retargeting, so `_retarget_dataset` reports zero changes. Gating the
    "no image for this architecture" partition on that count skipped it exactly where it
    was needed, and the misses landed in the generic error bucket next to throttled
    pulls. The gate is on the architecture instead.
    """
    from swebench.harness.run_evaluation import _retarget_dataset

    arm64 = [{"instance_id": "a__a-1",
              "image": "swebench/sweb.eval.arm64.a_1776_a-1:latest"}]
    rows, changed = _retarget_dataset(arm64, "arm64")
    assert changed == 0
    assert rows == arm64

    amd64 = [{"instance_id": "a__a-1",
              "image": "swebench/sweb.eval.x86_64.a_1776_a-1:latest"}]
    _, changed = _retarget_dataset(amd64, "arm64")
    assert changed == 1
