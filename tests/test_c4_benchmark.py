"""Tests for C4 item 1.

No number in the C4 artifact is reportable until the function that produced it
lands here. Two of these tests are unusual and worth explaining.

``test_cli_pins_threads_before_importing_caprm`` reads the CLI's source and
checks statement order with ``ast``. The invariant it protects — that the thread
environment is fixed before numpy loads — cannot be checked by importing the
module, because importing it is the thing that would break it. This is the
positive-control rule from 18.25 applied to import order: a check performed
after the event cannot detect the event.

``test_batch_sweep_agrees_across_batch_sizes`` uses a loose local tolerance
rather than ``C2_BATCH_AGREEMENT_TOLERANCE``. The C2 constant belongs to the C2
architecture at the C2 scale; asserting it against a toy model would be
asserting a number this test has no standing to assert.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from caprm import c4_benchmark as c4
from caprm.surrogate import (
    CoordinateNormalizer,
    FourierConfig,
    MLPConfig,
    TrainedModel,
    init_parameters,
    save_model,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPOSITORY_ROOT / "python" / "scripts" / "benchmark_c4_inference.py"

SYNTHETIC_AGREEMENT_TOLERANCE = 1e-3


def synthetic_model(n_features: int = 8, hidden: tuple[int, ...] = (16, 16), seed: int = 7):
    fourier = FourierConfig(n_features=n_features, scale=4.0, include_raw=True)
    mlp = MLPConfig(hidden=hidden, dtype="float32")
    return TrainedModel(
        normalizer=CoordinateNormalizer.from_bounds(0.0, 1000.0, 0.0, 800.0),
        fourier=fourier,
        frequencies=fourier.draw(seed),
        parameters=init_parameters(fourier.n_columns, mlp, seed),
        mlp=mlp,
        target_mean=40.0,
        target_std=12.0,
        seeds={"seed": seed},
    )


def synthetic_coordinates(n: int = 512, seed: int = 11):
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, 1000.0, n), rng.uniform(0.0, 800.0, n)


# --- timing -----------------------------------------------------------------


def test_timing_result_statistics_are_computed_from_the_sample():
    result = c4.TimingResult(n_warmup=2, seconds=(1.0, 2.0, 4.0))
    assert result.n_repeat == 3
    assert result.median == 2.0
    assert result.minimum == 1.0
    assert result.maximum == 4.0
    assert result.relative_spread == pytest.approx(1.5)
    assert result.to_dict()["seconds"] == [1.0, 2.0, 4.0]


def test_timing_result_rejects_an_empty_sample():
    with pytest.raises(c4.C4BenchmarkError):
        c4.TimingResult(n_warmup=1, seconds=())


def test_single_repeat_reports_zero_stdev_rather_than_raising():
    result = c4.TimingResult(n_warmup=0, seconds=(0.5,))
    assert result.stdev == 0.0


def test_timed_repeats_discards_warmups_and_returns_the_first_timed_value():
    calls = []

    def call():
        calls.append(len(calls))
        return len(calls)

    timing, first = c4.timed_repeats(call, n_warmup=2, n_repeat=3)
    assert len(calls) == 5
    assert timing.n_repeat == 3
    assert timing.n_warmup == 2
    assert first == 3


def test_timed_repeats_rejects_zero_repeats():
    with pytest.raises(c4.C4BenchmarkError):
        c4.timed_repeats(lambda: None, n_warmup=0, n_repeat=0)


# --- the sweep --------------------------------------------------------------


def test_batch_label_names_the_full_array():
    assert c4.batch_label(None) == "full"
    assert c4.batch_label(4096) == "4096"


def test_batch_sweep_reports_every_batch_size_with_counts():
    model = synthetic_model()
    x, y = synthetic_coordinates(256)
    rows, predictions = c4.batch_sweep(
        model, x, y, batch_sizes=(1, 64, None), n_warmup=0, n_repeat=2
    )
    assert [row["batch_label"] for row in rows] == ["1", "64", "full"]
    assert rows[0]["n_batches"] == 256
    assert rows[1]["n_batches"] == 4
    assert rows[2]["n_batches"] == 1
    assert all(row["n_properties"] == 256 for row in rows)
    assert all(row["properties_per_second_median"] > 0 for row in rows)
    assert set(predictions) == {"1", "64", "full"}


def test_batch_sweep_agrees_across_batch_sizes():
    model = synthetic_model()
    x, y = synthetic_coordinates(256)
    _, predictions = c4.batch_sweep(
        model, x, y, batch_sizes=(1, 64, None), n_warmup=0, n_repeat=1
    )
    report = c4.agreement_report(
        predictions, reference_label="full", tolerance=SYNTHETIC_AGREEMENT_TOLERANCE
    )
    assert report["all_within_tolerance"]


def test_batch_sweep_rejects_a_nonpositive_batch():
    model = synthetic_model()
    x, y = synthetic_coordinates(32)
    with pytest.raises(c4.C4BenchmarkError):
        c4.batch_sweep(model, x, y, batch_sizes=(0,), n_warmup=0, n_repeat=1)


def test_agreement_report_flags_a_deviation_above_tolerance():
    reference = np.zeros(16, dtype=np.float64)
    perturbed = reference.copy()
    perturbed[3] = 1e-4
    report = c4.agreement_report(
        {"full": reference, "64": perturbed}, tolerance=c4.C2_BATCH_AGREEMENT_TOLERANCE
    )
    assert not report["all_within_tolerance"]
    assert report["per_batch"]["64"]["max_abs_deviation"] == pytest.approx(1e-4)
    assert report["per_batch"]["full"]["within_tolerance"]
    assert report["max_abs_deviation_index_points"] == pytest.approx(1e-4)


def test_agreement_report_needs_its_reference():
    with pytest.raises(c4.C4BenchmarkError):
        c4.agreement_report({"64": np.zeros(4)}, reference_label="full")


# --- the split --------------------------------------------------------------


def test_stage_split_reports_a_ratio_and_publishes_the_non_additive_gap():
    """The split must not present itself as a decomposition it is not.

    An earlier version divided each half by the full predict wall clock and
    returned 101 percent encoding with a negative residual. These assertions
    are what stop that from coming back: no fraction-of-total key exists, the
    gap between the parts and the whole is published, and the reportable
    quantity is the ratio between the two halves.
    """
    model = synthetic_model()
    x, y = synthetic_coordinates(256)
    split = c4.stage_split(model, x, y, batch_size=64, n_warmup=0, n_repeat=2)

    assert not any(key.endswith("_fraction_of_total") for key in split)
    assert split["sum_of_parts_s"] == pytest.approx(
        split["fourier_encoding"]["median_s"] + split["mlp_forward"]["median_s"]
    )
    assert split["parts_minus_whole_s"] == pytest.approx(
        split["sum_of_parts_s"] - split["full_predict_s"]
    )
    assert split["fourier_over_mlp_ratio"] > 0
    assert "allocator reuse" in split["decomposition_is_not_additive"]
    assert split["n_properties"] == 256
    assert split["feature_dtype"] == "float32"
    assert split["feature_matrix_bytes"] == 256 * model.fourier.n_columns * 4


# --- models -----------------------------------------------------------------


def test_model_size_record_separates_mlp_parameters_from_stored_values(tmp_path):
    model = synthetic_model(n_features=8, hidden=(16, 16))
    path = tmp_path / "synthetic.npz"
    save_model(model, path)
    record = c4.model_size_record(model, path)
    expected_mlp = sum(w.size + b.size for w, b in model.parameters)
    assert record["n_mlp_parameters"] == expected_mlp
    # the (2, n_features) frequency matrix is stored and digested but not counted
    # by TrainedModel.n_parameters, which is the whole reason both are reported
    assert record["n_stored_values"] == expected_mlp + model.frequencies.size
    assert record["disk_bytes"] > 0
    assert record["memory_bytes"] == sum(a.nbytes for _, a in model.named_arrays())


def test_assert_identical_architecture_rejects_a_mixed_set():
    def record(shapes):
        return c4.ModelRecord(
            label="l",
            partition="p",
            seed=1,
            fold=0,
            path="p.npz",
            expected_weights_sha256="a",
            observed_weights_sha256="a",
            n_mlp_parameters=1,
            n_stored_values=1,
            layer_shapes=shapes,
            disk_bytes=1,
            memory_bytes=1,
        )

    same = [record((((18, 16)), (16, 1))), record((((18, 16)), (16, 1)))]
    assert c4.assert_identical_architecture(same)["n_models"] == 2
    with pytest.raises(c4.C4BenchmarkError):
        c4.assert_identical_architecture([same[0], record((((18, 32)), (32, 1)))])


def test_assert_identical_architecture_rejects_an_empty_set():
    with pytest.raises(c4.C4BenchmarkError):
        c4.assert_identical_architecture([])


def test_verify_models_raises_on_a_digest_mismatch(tmp_path):
    model = synthetic_model()
    model_dir = tmp_path / "outputs" / "models"
    model_dir.mkdir(parents=True)
    save_model(model, model_dir / "m.npz")
    manifest = {
        "results": {
            "blocked_kfold": [
                {
                    "folds": [
                        {
                            "label": "m",
                            "partition": "blocked_kfold",
                            "seed": 1,
                            "fold": 0,
                            "model_path": "outputs\\models\\m.npz",
                            "weights_sha256": "0" * 64,
                        }
                    ]
                }
            ]
        }
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(c4.C4BenchmarkError, match="do not match"):
        c4.verify_models(manifest_path, tmp_path)


def test_verify_models_accepts_the_recorded_digest(tmp_path):
    model = synthetic_model()
    model_dir = tmp_path / "outputs" / "models"
    model_dir.mkdir(parents=True)
    save_model(model, model_dir / "m.npz")
    manifest = {
        "results": {
            "blocked_kfold": [
                {
                    "folds": [
                        {
                            "label": "m",
                            "partition": "blocked_kfold",
                            "seed": 1,
                            "fold": 0,
                            "model_path": "outputs\\models\\m.npz",
                            "weights_sha256": model.weights_sha256(),
                        }
                    ]
                }
            ]
        }
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    records, models = c4.verify_models(manifest_path, tmp_path)
    assert len(records) == 1
    assert records[0].observed_weights_sha256 == records[0].expected_weights_sha256
    assert "m" in models


def test_verify_models_raises_when_a_recorded_model_is_missing(tmp_path):
    manifest = {
        "results": {
            "blocked_kfold": [
                {
                    "folds": [
                        {
                            "label": "gone",
                            "partition": "blocked_kfold",
                            "seed": 1,
                            "fold": 0,
                            "model_path": "outputs\\models\\gone.npz",
                            "weights_sha256": "0" * 64,
                        }
                    ]
                }
            ]
        }
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(c4.C4BenchmarkError, match="missing"):
        c4.verify_models(manifest_path, tmp_path)


# --- provenance -------------------------------------------------------------


def test_thread_environment_reports_unset_variables_as_none(monkeypatch):
    monkeypatch.delenv("OPENBLAS_NUM_THREADS", raising=False)
    monkeypatch.setenv("OMP_NUM_THREADS", "4")
    observed = c4.thread_environment()
    assert observed["OPENBLAS_NUM_THREADS"] is None
    assert observed["OMP_NUM_THREADS"] == "4"


def test_environment_record_labels_operator_declared_fields():
    record = c4.environment_record(cpu_name="Test CPU", physical_cores=8)
    assert record["operator_declared"]["cpu_name"] == "Test CPU"
    assert record["operator_declared"]["physical_cores"] == 8
    assert "not read by this process" in record["operator_declared"]["source"]
    assert "numpy_version" in record


def test_sha256_file_matches_hashlib(tmp_path):
    import hashlib

    path = tmp_path / "f.bin"
    payload = b"caprm" * 1000
    path.write_bytes(payload)
    assert c4.sha256_file(path, chunk_bytes=7) == hashlib.sha256(payload).hexdigest()


# --- the CLI's import order -------------------------------------------------


def _cli_tree() -> ast.Module:
    return ast.parse(CLI_PATH.read_text(encoding="utf-8"))


def _imported_roots(node: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name.split(".")[0] for alias in node.names}
    return {(node.module or "").split(".")[0]}


def test_cli_imports_nothing_numeric_at_module_level():
    forbidden = {"numpy", "pandas", "caprm", "scipy", "geopandas", "rasterio"}
    for node in _cli_tree().body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert not (_imported_roots(node) & forbidden), ast.dump(node)


def test_cli_pins_threads_before_importing_caprm():
    main = next(
        node
        for node in _cli_tree().body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    environ_writes = [
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "environ"
            for target in node.targets
        )
    ]
    numeric_imports = [
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and (_imported_roots(node) & {"numpy", "pandas", "caprm"})
    ]
    assert environ_writes, "the CLI no longer pins the thread environment"
    assert numeric_imports, "the CLI no longer imports numpy inside main()"
    assert max(environ_writes) < min(numeric_imports)


def test_cli_defaults_write_outside_the_frozen_benchmark_summary():
    """The default output path, read from the parser rather than from prose.

    ``build_property_evidence.py`` asserts that the water benchmark summary's
    algorithm set equals {brute_force, feature_bvh}. A C4 default that pointed
    anywhere near that file would break the evidence build, so the check reads
    the argparse default itself; a substring search over the source would be
    satisfied or defeated by a comment.
    """
    defaults: dict[str, str] = {}
    for node in ast.walk(_cli_tree()):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "add_argument"):
            continue
        flags = [a.value for a in node.args if isinstance(a, ast.Constant)]
        for keyword in node.keywords:
            if keyword.arg == "default" and isinstance(keyword.value, ast.Constant):
                for flag in flags:
                    defaults[flag] = keyword.value.value

    assert defaults["--output"] == "outputs/validation/c4_inference_benchmark.json"
    assert all(
        "water_cpp_benchmark_summary" not in str(value) for value in defaults.values()
    )