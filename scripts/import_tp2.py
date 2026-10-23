"""Importer et vérifier le checkpoint accepté du TP2."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "models/model.joblib",
    "reports/quality_gate_decision.json",
    "reports/metrics.json",
    "reports/run_manifest.json",
    "quality_gates/baseline_metrics.json",
    "data/raw/machines.csv",
)
METRIC_NAMES = ("accuracy", "precision", "recall", "f1", "latency_ms")


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source_root: Path, relative: str) -> None:
    source = source_root / relative
    if not source.is_file():
        raise FileNotFoundError(f"TP2 file missing: {relative}")
    destination = ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def load_json(source_root: Path, relative: str) -> dict:
    try:
        return json.loads((source_root / relative).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {relative}: {exc}") from exc


def validate_metrics(metrics: dict, label: str) -> None:
    for name in METRIC_NAMES:
        value = metrics.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"{label} has no valid {name}")
    for name in ("accuracy", "precision", "recall", "f1"):
        if not 0 <= float(metrics[name]) <= 1:
            raise ValueError(f"{label} {name} must be between 0 and 1")
    if float(metrics["latency_ms"]) < 0:
        raise ValueError(f"{label} latency_ms must be non-negative")


def validate_source(source_root: Path) -> tuple[dict, dict, str]:
    if not source_root.is_dir():
        raise FileNotFoundError(f"TP2_DIR does not exist: {source_root}")
    missing = [relative for relative in REQUIRED_FILES if not (source_root / relative).is_file()]
    if missing:
        raise FileNotFoundError(f"TP2 files missing: {', '.join(missing)}")
    gate = load_json(source_root, "reports/quality_gate_decision.json")
    metrics = load_json(source_root, "reports/metrics.json")
    manifest = load_json(source_root, "reports/run_manifest.json")
    baseline = load_json(source_root, "quality_gates/baseline_metrics.json")
    if gate.get("decision") != "ACCEPT":
        raise ValueError("TP2 quality gate must contain decision: ACCEPT")
    validate_metrics(metrics, "reports/metrics.json")
    validate_metrics(baseline, "quality_gates/baseline_metrics.json")
    if not manifest.get("run_id"):
        raise ValueError("TP2 manifest must contain a non-empty run_id")
    if manifest.get("model_artifact") != "models/model.joblib":
        raise ValueError("TP3 expects manifest model_artifact: models/model.joblib")
    manifest_metrics = manifest.get("metrics")
    if not isinstance(manifest_metrics, dict):
        raise ValueError("TP2 manifest must contain metrics")
    for name in METRIC_NAMES:
        try:
            matches = math.isclose(
                float(metrics[name]),
                float(manifest_metrics[name]),
                rel_tol=1e-9,
                abs_tol=1e-12,
            )
        except (KeyError, TypeError, ValueError):
            matches = False
        if not matches:
            raise ValueError(
                f"TP2 manifest metric {name} differs from reports/metrics.json"
            )
    raw_data = source_root / "data/raw/machines.csv"
    actual_hash = sha256(raw_data)
    if manifest.get("data_sha256") != actual_hash:
        raise ValueError("TP2 manifest data_sha256 does not match the source dataset")
    if not (source_root / "models/model.joblib").is_file():
        raise FileNotFoundError("TP2 manifest model_artifact is missing: models/model.joblib")
    return gate, manifest, actual_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    source_root = args.source.resolve()
    if source_root == ROOT:
        raise ValueError("TP2_DIR must point to a separate TP2 workspace")
    _, manifest, actual_hash = validate_source(source_root)

    for relative in REQUIRED_FILES:
        copy_file(source_root, relative)
    for relative in (
        "models/run_manifest.json",
        "data/processed/train.csv",
        "data/processed/test.csv",
        "params.yaml",
    ):
        if (source_root / relative).is_file():
            copy_file(source_root, relative)

    payload = {
        "source": str(source_root),
        "quality_gate": "ACCEPT",
        "parent_run_id": manifest.get("run_id"),
        "data_sha256": actual_hash,
        "model_artifact": "models/model.joblib",
    }
    report = ROOT / "reports/tp2_import.json"
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
