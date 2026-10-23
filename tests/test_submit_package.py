"""`swebench submit package` -- building a submission from an evaluated run.

The dataset and grading are stubbed: these tests are about the shape of what gets
written and about the guarantee that resolution is re-derived from the logs rather than
read out of the run's own report.json.
"""

import gzip
import json

import pytest
import yaml

from swebench.submit import package as pkg


@pytest.fixture
def run(tmp_path):
    """A fake eval run: <run_dir>/<model>/<iid>/{patch.diff,...}."""
    root = tmp_path / "logs" / "evaluation"

    def add(iid, *, patch="diff --git a/x b/x\n", output="ok", report=True):
        d = root / "my-run" / "my-model" / iid
        d.mkdir(parents=True)
        if patch is not None:
            (d / "patch.diff").write_text(patch)
        if output is not None:
            (d / "test_output.txt").write_text(output)
        if report:
            # deliberately claims resolved; packaging must ignore it
            (d / "report.json").write_text(json.dumps({iid: {"resolved": True}}))
        (d / "eval.sh").write_text("#!/bin/sh\n")
        (d / "run_instance.log").write_text("noise\n")

    add.run_dir = root / "my-run"
    return add


@pytest.fixture
def dataset(monkeypatch):
    """Stub load_dataset + grading. `resolved` names the instances that pass."""

    def setup(instance_ids, resolved=()):
        rows = [
            {
                "instance_id": iid,
                "repo": f"org/{iid.split('__')[0]}",
                "created_at": "2023-05-01T00:00:00Z",
            }
            for iid in instance_ids
        ]
        monkeypatch.setattr(
            "datasets.load_dataset", lambda *a, **k: rows, raising=False
        )
        monkeypatch.setattr(
            pkg, "_grade", lambda inst, *a, **k: inst["instance_id"] in resolved
        )

    return setup


def test_builds_both_trees(tmp_path, run, dataset):
    run("astropy__astropy-1")
    run("django__django-2")
    dataset(["astropy__astropy-1", "django__django-2"], resolved=["django__django-2"])

    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out")

    entry, repo = tmp_path / "out" / "entry", tmp_path / "out" / "submission-repo"
    assert result.resolved == ["django__django-2"]
    assert json.loads((entry / "results" / "results.json").read_text())["resolved"] == [
        "django__django-2"
    ]
    assert (entry / "metadata.yaml").is_file()
    assert (entry / "README.md").is_file()
    # logs mirror the S3 layout, with test output gzipped
    assert (repo / "logs" / "django__django-2" / "patch.diff").is_file()
    assert (repo / "logs" / "django__django-2" / "test_output.txt.gz").is_file()
    assert (repo / "all_preds.jsonl").is_file()


def test_ignores_the_runs_own_report(tmp_path, run, dataset):
    # Both reports claim resolved:true; only the grader's verdict counts.
    run("a__a-1")
    run("b__b-2")
    dataset(["a__a-1", "b__b-2"], resolved=[])
    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    assert result.resolved == []


def test_drops_artifacts_not_needed_for_submission(tmp_path, run, dataset):
    run("a__a-1")
    dataset(["a__a-1"], resolved=["a__a-1"])
    pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    written = {
        p.name
        for p in (tmp_path / "out" / "submission-repo" / "logs" / "a__a-1").iterdir()
    }
    assert written == {"patch.diff", "report.json", "test_output.txt.gz"}


def test_test_output_round_trips_through_gzip(tmp_path, run, dataset):
    run("a__a-1", output="verbose test log\n" * 100)
    dataset(["a__a-1"])
    pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    gz = tmp_path / "out" / "submission-repo" / "logs" / "a__a-1" / "test_output.txt.gz"
    assert gzip.open(gz, "rt").read() == "verbose test log\n" * 100


def test_missing_patch_counts_as_no_generation(tmp_path, run, dataset):
    run("a__a-1", patch=None)
    dataset(["a__a-1"])
    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    assert result.no_generation == ["a__a-1"] and result.resolved == []


def test_missing_test_output_counts_as_no_logs(tmp_path, run, dataset):
    run("a__a-1", output=None)
    dataset(["a__a-1"])
    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    assert result.no_logs == ["a__a-1"]


def test_instance_never_attempted_is_no_generation(tmp_path, run, dataset):
    run("a__a-1")
    dataset(["a__a-1", "never__ran-9"], resolved=["a__a-1"])
    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    assert result.no_generation == ["never__ran-9"]


def test_breakdowns_count_every_dataset_instance(tmp_path, run, dataset):
    run("a__a-1")
    dataset(["a__a-1", "never__ran-9"], resolved=["a__a-1"])
    pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    results = tmp_path / "out" / "entry" / "results"
    by_repo = json.loads((results / "resolved_by_repo.json").read_text())
    assert by_repo == {
        "org/a": {"resolved": 1, "total": 1},
        "org/never": {"resolved": 0, "total": 1},
    }
    assert json.loads((results / "resolved_by_time.json").read_text()) == {
        "2023": {"resolved": 1, "total": 2}
    }


def test_oversized_test_output_is_refused(tmp_path, run, dataset, monkeypatch):
    monkeypatch.setattr(pkg, "MAX_ARTIFACT_BYTES", 10)
    run("a__a-1", output="x" * 100_000)  # incompressible enough to exceed 10 bytes
    dataset(["a__a-1"])
    with pytest.raises(pkg.PackageError, match="too large to host"):
        pkg.package_run(run.run_dir, "verified", tmp_path / "out")


def test_multimodal_builds_entry_only(tmp_path, run, dataset):
    run("carbon__carbon-1")
    dataset(["carbon__carbon-1"], resolved=["carbon__carbon-1"])
    pkg.package_run(run.run_dir, "multimodal", tmp_path / "out")
    assert (tmp_path / "out" / "entry" / "results" / "results.json").is_file()
    assert not (tmp_path / "out" / "submission-repo").exists()


def test_unknown_split_is_rejected(tmp_path, run):
    run("a__a-1")
    with pytest.raises(pkg.PackageError, match="unknown split"):
        pkg.package_run(run.run_dir, "bash-only", tmp_path / "out")


def test_predictions_rebuilt_from_patches_when_not_supplied(tmp_path, run, dataset):
    run("a__a-1", patch="PATCH-A")
    dataset(["a__a-1"])
    pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    rows = [
        json.loads(x)
        for x in (tmp_path / "out" / "submission-repo" / "all_preds.jsonl")
        .read_text()
        .splitlines()
    ]
    assert rows == [
        {
            "instance_id": "a__a-1",
            "model_name_or_path": "my-model",
            "model_patch": "PATCH-A",
        }
    ]


def test_supplied_predictions_are_preserved(tmp_path, run, dataset):
    run("a__a-1")
    dataset(["a__a-1"])
    preds = tmp_path / "preds.json"
    preds.write_text(
        json.dumps(
            {
                "a__a-1": {
                    "instance_id": "a__a-1",
                    "model_name_or_path": "real",
                    "model_patch": "P",
                }
            }
        )
    )
    pkg.package_run(run.run_dir, "verified", tmp_path / "out", predictions=preds)
    row = json.loads(
        (tmp_path / "out" / "submission-repo" / "all_preds.jsonl").read_text().strip()
    )
    assert row["model_name_or_path"] == "real"


def test_trajs_are_flattened(tmp_path, run, dataset):
    run("a__a-1")
    dataset(["a__a-1"])
    # mini-swe-agent's layout: <iid>/<iid>.traj.json
    src = tmp_path / "mini-out"
    (src / "a__a-1").mkdir(parents=True)
    (src / "a__a-1" / "a__a-1.traj.json").write_text("{}")
    pkg.package_run(
        run.run_dir, "verified", tmp_path / "out", model="my-model", trajs=src
    )
    assert (
        tmp_path / "out" / "submission-repo" / "trajs" / "a__a-1.traj.json"
    ).is_file()


@pytest.mark.parametrize("nested", [False, True])
def test_trajs_match_complete_instance_ids(tmp_path, run, dataset, nested):
    run("a__a-1")
    dataset(["a__a-1"])
    src = tmp_path / "agent-output"
    for iid in ("a__a-1", "a__a-10", "a__a-1-backup"):
        parent = src / iid if nested else src
        parent.mkdir(parents=True, exist_ok=True)
        (parent / f"{iid}.traj.json").write_text(json.dumps({"instance_id": iid}))

    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out", trajs=src)

    dest = tmp_path / "out" / "submission-repo" / "trajs"
    assert sorted(p.name for p in dest.iterdir()) == ["a__a-1.traj.json"]
    assert result.n_trajs == 1
    assert json.loads((dest / "a__a-1.traj.json").read_text()) == {
        "instance_id": "a__a-1"
    }


def test_metadata_stub_is_valid_yaml_with_todos(tmp_path, run, dataset):
    run("a__a-1")
    dataset(["a__a-1"])
    pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    meta = yaml.safe_load((tmp_path / "out" / "entry" / "metadata.yaml").read_text())
    assert meta["tags"]["model"] == ["my-model"]
    assert "TODO" in meta["info"]["report"]
    # publish fills this in; it must not be guessed here
    assert "assets" not in meta


def test_submission_id_shape():
    from datetime import datetime

    assert (
        pkg.submission_id("my agent/v2", when=datetime(2026, 9, 1))
        == "20260901_my-agent__v2"
    )


def test_several_models_needs_a_choice(tmp_path, run, dataset):
    run("a__a-1")
    # a second model with real artifacts; an empty directory is not a candidate
    other = run.run_dir / "other-model" / "a__a-1"
    other.mkdir(parents=True)
    (other / "patch.diff").write_text("d")
    with pytest.raises(pkg.PackageError, match="several models"):
        pkg.package_run(run.run_dir, "verified", tmp_path / "out")


def test_single_model_is_found(tmp_path, run, dataset):
    run("a__a-1")
    dataset(["a__a-1"])
    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    assert result.submission_id.endswith("_my-model")


def test_the_model_directory_is_accepted_directly(tmp_path, run, dataset):
    """Tab-completing one level deeper should still work."""
    run("a__a-1")
    dataset(["a__a-1"], resolved=["a__a-1"])
    result = pkg.package_run(run.run_dir / "my-model", "verified", tmp_path / "out")
    assert result.resolved == ["a__a-1"]


def test_unknown_model_names_the_candidates(tmp_path, run, dataset):
    run("a__a-1")
    with pytest.raises(pkg.PackageError, match="have: my-model"):
        pkg.package_run(run.run_dir, "verified", tmp_path / "out", model="nope")


def test_missing_run_directory_is_a_clear_error(tmp_path):
    with pytest.raises(pkg.PackageError, match="no such run directory"):
        pkg.package_run(tmp_path / "ghost", "verified", tmp_path / "out")


def test_a_directory_with_no_models_is_a_clear_error(tmp_path):
    empty = tmp_path / "empty-run"
    empty.mkdir()
    with pytest.raises(pkg.PackageError, match="no evaluation artifacts"):
        pkg.package_run(empty, "verified", tmp_path / "out")


# --- split and output are derived from the run --------------------------------


def _record_dataset(run_dir, dataset="SWE-bench/SWE-bench_Verified"):
    from swebench.harness.constants import LOG_RUN_METADATA

    (run_dir / LOG_RUN_METADATA).write_text(json.dumps({"dataset": dataset}))


def test_split_comes_from_the_recorded_dataset(tmp_path, run, dataset):
    run("a__a-1")
    _record_dataset(run.run_dir)
    dataset(["a__a-1"], resolved=["a__a-1"])
    result = pkg.package_run(run.run_dir, out_dir=tmp_path / "out")
    assert result.split == "verified"


def test_explicit_split_overrides_the_run(tmp_path, run, dataset):
    run("a__a-1")
    _record_dataset(run.run_dir, "SWE-bench/SWE-bench_Lite")
    dataset(["a__a-1"])
    result = pkg.package_run(run.run_dir, "verified", tmp_path / "out")
    assert result.split == "verified"


def test_split_required_when_the_run_recorded_nothing(tmp_path, run, dataset):
    run("a__a-1")
    with pytest.raises(pkg.PackageError, match="does not record which dataset"):
        pkg.package_run(run.run_dir, out_dir=tmp_path / "out")


def test_output_defaults_beside_the_run(run, dataset):
    run("a__a-1")
    _record_dataset(run.run_dir)
    dataset(["a__a-1"], resolved=["a__a-1"])
    result = pkg.package_run(run.run_dir)
    assert result.out_dir == run.run_dir / "submission"
    assert (result.out_dir / "entry" / "results" / "results.json").is_file()


def test_the_default_output_is_not_mistaken_for_a_model(run, dataset):
    """submission/ lands inside the run dir, so packaging twice must still resolve."""
    run("a__a-1")
    _record_dataset(run.run_dir)
    dataset(["a__a-1"], resolved=["a__a-1"])
    pkg.package_run(run.run_dir)
    again = pkg.package_run(run.run_dir)
    assert again.model == "my-model" and again.resolved == ["a__a-1"]


def test_existing_metadata_and_readme_are_kept(tmp_path, run, dataset):
    """publish writes assets into metadata.yaml, and humans fill in the rest --
    re-running package must not throw either away."""
    run("a__a-1")
    _record_dataset(run.run_dir)
    dataset(["a__a-1"], resolved=["a__a-1"])
    out = tmp_path / "out"
    pkg.package_run(run.run_dir, out_dir=out)

    entry = out / "entry"
    (entry / "metadata.yaml").write_text("assets:\n  repo: https://example.com/mine\n")
    (entry / "README.md").write_text("my own description")

    result = pkg.package_run(run.run_dir, out_dir=out)
    assert sorted(result.kept) == ["README.md", "metadata.yaml"]
    assert "example.com/mine" in (entry / "metadata.yaml").read_text()
    assert (entry / "README.md").read_text() == "my own description"


def test_derived_files_are_still_refreshed(tmp_path, run, dataset):
    run("a__a-1")
    _record_dataset(run.run_dir)
    dataset(["a__a-1"], resolved=["a__a-1"])
    out = tmp_path / "out"
    pkg.package_run(run.run_dir, out_dir=out)
    results = out / "entry" / "results" / "results.json"
    results.write_text("{}")
    pkg.package_run(run.run_dir, out_dir=out)
    assert json.loads(results.read_text())["resolved"] == ["a__a-1"]
