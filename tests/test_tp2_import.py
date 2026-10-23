import json

import pytest

from scripts import import_tp2


METRICS = {
    "accuracy": 0.82,
    "precision": 0.78,
    "recall": 0.71,
    "f1": 0.74,
    "latency_ms": 12.0,
}


def make_tp2_checkpoint(tmp_path, *, decision="ACCEPT", manifest_metrics=None):
    root = tmp_path / "tp2"
    for relative in ("models", "reports", "quality_gates", "data/raw"):
        (root / relative).mkdir(parents=True)
    data = root / "data/raw/machines.csv"
    data.write_text("machine_type,torque_nm\nA,42.8\n", encoding="utf-8")
    (root / "models/model.joblib").write_bytes(b"model")
    (root / "reports/quality_gate_decision.json").write_text(
        json.dumps({"decision": decision}), encoding="utf-8"
    )
    (root / "reports/metrics.json").write_text(
        json.dumps(METRICS), encoding="utf-8"
    )
    (root / "quality_gates/baseline_metrics.json").write_text(
        json.dumps(METRICS), encoding="utf-8"
    )
    manifest = {
        "run_id": "run-tp2-test",
        "model_artifact": "models/model.joblib",
        "data_sha256": import_tp2.sha256(data),
        "metrics": manifest_metrics or METRICS,
    }
    (root / "reports/run_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return root


def test_import_validation_accepts_coherent_checkpoint(tmp_path):
    root = make_tp2_checkpoint(tmp_path)

    gate, manifest, data_hash = import_tp2.validate_source(root)

    assert gate["decision"] == "ACCEPT"
    assert manifest["run_id"] == "run-tp2-test"
    assert data_hash == manifest["data_sha256"]


def test_import_validation_rejects_quality_gate(tmp_path):
    root = make_tp2_checkpoint(tmp_path, decision="REJECT")

    with pytest.raises(ValueError, match="quality gate"):
        import_tp2.validate_source(root)


def test_import_validation_rejects_manifest_metric_mismatch(tmp_path):
    mismatch = {**METRICS, "f1": 0.91}
    root = make_tp2_checkpoint(tmp_path, manifest_metrics=mismatch)

    with pytest.raises(ValueError, match="metric f1"):
        import_tp2.validate_source(root)
