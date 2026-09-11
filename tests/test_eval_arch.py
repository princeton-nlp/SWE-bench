"""Which architecture's images an evaluation runs, and what happens when there are none.

`TestSpec.image` is read from the dataset verbatim, so a dataset published for amd64
runs amd64 images everywhere -- refused where the tag is a multi-platform index, and
silently emulated where it is not. Retargeting happens once, when the dataset is loaded.

The second half is the reporting rule: on arm64, 219 of SWE-bench Verified's 500
instances have no published image at all. Counting those as unresolved drops the
headline score by 44% with nothing in the report saying why, so they are their own class.
"""

import json

import pytest

from swebench.harness import reporting, run_evaluation
from swebench.harness.reporting import make_run_report
from swebench.harness.run_evaluation import (
    _retarget_dataset,
    image_platform,
    write_run_metadata,
)

AMD64 = "swebench/sweb.eval.x86_64.a_1776_a-1:latest"
ARM64 = "swebench/sweb.eval.arm64.a_1776_a-1:latest"


def test_the_dataset_is_retargeted_to_the_requested_architecture():
    dataset, changed = _retarget_dataset([{"instance_id": "a__a-1", "image": AMD64}], "arm64")
    assert changed == 1
    assert dataset[0]["image"] == ARM64


def test_retargeting_the_architecture_it_already_names_changes_nothing():
    # nothing was retargeted, which is how the caller knows not to probe the registry
    dataset, changed = _retarget_dataset([{"instance_id": "a__a-1", "image": AMD64}], "amd64")
    assert changed == 0
    assert dataset[0]["image"] == AMD64


def test_an_image_naming_no_architecture_is_left_alone():
    rows = [{"instance_id": "a__a-1", "image": "ghcr.io/someone/custom:latest"}]
    dataset, changed = _retarget_dataset(rows, "arm64")
    assert changed == 0
    assert dataset[0]["image"] == "ghcr.io/someone/custom:latest"


def test_a_row_without_an_image_is_left_alone():
    dataset, changed = _retarget_dataset([{"instance_id": "a__a-1"}], "arm64")
    assert changed == 0
    assert dataset == [{"instance_id": "a__a-1"}]


def test_retargeting_does_not_mutate_the_loaded_dataset():
    # full_dataset and dataset share rows; rewriting in place would retarget twice
    rows = [{"instance_id": "a__a-1", "image": AMD64}]
    _retarget_dataset(rows, "arm64")
    assert rows[0]["image"] == AMD64


@pytest.mark.parametrize(
    "image,expected",
    [
        (AMD64, "linux/amd64"),
        (ARM64, "linux/arm64/v8"),
        # no platform is passed for a name that declares none, so behaviour is unchanged
        ("ghcr.io/someone/custom:latest", None),
    ],
)
def test_the_platform_passed_to_docker_comes_from_the_image_name(image, expected):
    assert image_platform(image) == expected


def test_modal_refuses_a_non_amd64_architecture():
    # the Modal path never looks at test_spec.image and installs an x86_64 Miniconda,
    # so an --arch arm64 run there would report a result it did not produce
    with pytest.raises(ValueError, match="only runs amd64"):
        run_evaluation.main(
            dataset_name="SWE-bench/SWE-bench_Lite",
            split="test",
            instance_ids=None,
            predictions_path="gold",
            max_workers=1,
            open_file_limit=4096,
            run_id="modal-arm64",
            timeout=1,
            rewrite_reports=False,
            modal=True,
            arch="arm64",
        )


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """RUN_EVALUATION_LOG_DIR is CWD-relative; point it somewhere disposable."""
    root = tmp_path / "logs" / "evaluation"
    monkeypatch.setattr(reporting, "RUN_EVALUATION_LOG_DIR", root)
    monkeypatch.setattr(run_evaluation, "RUN_EVALUATION_LOG_DIR", root)
    return root


def _fixture():
    predictions = {
        "a__a-1": {
            "instance_id": "a__a-1",
            "model_name_or_path": "gold",
            "model_patch": "diff",
        }
    }
    return predictions, [{"instance_id": "a__a-1", "image": ARM64}]


def test_an_unpublished_image_is_its_own_outcome(log_dir):
    predictions, full_dataset = _fixture()
    out = make_run_report(
        predictions, full_dataset, "no-arm64", None, {"a__a-1": ARM64}
    )
    report = json.loads(out.read_text())
    assert report["unavailable_image_ids"] == ["a__a-1"]
    assert report["unavailable_images"] == {"a__a-1": ARM64}
    # an image that does not exist says nothing about the prediction
    assert report["unresolved_ids"] == []
    assert report["error_ids"] == []
    assert report["completed_ids"] == []
    assert report["total_instances"] == 1


def test_without_an_unpublished_image_the_instance_still_errors(log_dir):
    # the new class must not swallow a genuine failure: same run, no unavailable images
    predictions, full_dataset = _fixture()
    out = make_run_report(predictions, full_dataset, "with-image")
    report = json.loads(out.read_text())
    assert report["error_ids"] == ["a__a-1"]
    assert report["unavailable_image_ids"] == []


def test_the_run_records_which_architecture_it_used(log_dir):
    path = write_run_metadata("a-run", "org/ds", "test", None, "arm64")
    assert json.loads(path.read_text())["arch"] == "arm64"
    # a re-grade passes no architecture, and must not overwrite the recorded one
    write_run_metadata("a-run", "org/ds", "test", None)
    assert json.loads(path.read_text())["arch"] == "arm64"
