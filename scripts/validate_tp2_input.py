"""Vérifier le contrat d'entrée TP2 avant toute opération de serving."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    errors = []
    paths = {
        "gate": ROOT / "reports/quality_gate_decision.json",
        "metrics": ROOT / "reports/metrics.json",
        "manifest": ROOT / "reports/run_manifest.json",
        "baseline": ROOT / "quality_gates/baseline_metrics.json",
        "model": ROOT / "models/model.joblib",
        "data": ROOT / "data/raw/machines.csv",
    }
    payloads = {}
    for name in ("gate", "metrics", "manifest", "baseline"):
        path = paths[name]
        if not path.is_file():
            errors.append(f"{path.relative_to(ROOT)} is missing")
            continue
        try:
            payloads[name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)} is invalid JSON: {exc}")

    if not paths["model"].is_file():
        errors.append("models/model.joblib is missing")
    if not paths["data"].is_file():
        errors.append("data/raw/machines.csv is missing")

    gate = payloads.get("gate", {})
    metrics = payloads.get("metrics", {})
    manifest = payloads.get("manifest", {})
    baseline = payloads.get("baseline", {})
    if gate.get("decision") != "ACCEPT":
        errors.append("reports/quality_gate_decision.json must contain decision: ACCEPT")
    if not manifest.get("run_id"):
        errors.append("run_manifest.json must contain a non-empty run_id")
    if manifest.get("model_artifact") != "models/model.joblib":
        errors.append("run_manifest.json model_artifact must be models/model.joblib")
    metric_names = ("accuracy", "precision", "recall", "f1", "latency_ms")
    for name in metric_names:
        value = metrics.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            errors.append(f"metrics.json: metric {name} is missing or non-numeric")
    for name in ("accuracy", "precision", "recall", "f1"):
        value = metrics.get(name)
        if isinstance(value, (int, float)) and not 0 <= float(value) <= 1:
            errors.append(f"metrics.json: metric {name} must be between 0 and 1")
    if isinstance(metrics.get("latency_ms"), (int, float)) and metrics["latency_ms"] < 0:
        errors.append("metrics.json: latency_ms must be non-negative")
    for name in ("accuracy", "precision", "recall", "f1", "latency_ms"):
        value = baseline.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            errors.append(f"baseline_metrics.json: metric {name} is missing or non-numeric")
    data = paths["data"]
    if data.is_file() and manifest.get("data_sha256") != sha256(data):
        errors.append("run_manifest.json data_sha256 does not match the dataset")
    if paths["model"].is_file() and manifest.get("model_artifact"):
        artifact = ROOT / "models/model.joblib"
        if not artifact.is_file():
            errors.append("run_manifest.json model_artifact is missing: models/model.joblib")
    manifest_metrics = manifest.get("metrics")
    if isinstance(manifest_metrics, dict):
        for name in metric_names:
            if name in metrics and name in manifest_metrics and not math.isclose(
                float(metrics[name]), float(manifest_metrics[name]), rel_tol=1e-9, abs_tol=1e-12
            ):
                errors.append(f"run_manifest.json metric {name} differs from reports/metrics.json")
    else:
        errors.append("run_manifest.json must contain metrics")
    if errors:
        print("TP2 INPUT: REJECT")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("TP2 INPUT: ACCEPT — model, gate and data hash are coherent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
