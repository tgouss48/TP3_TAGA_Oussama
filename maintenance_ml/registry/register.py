"""Enregistrer un candidat accepté dans le MLflow Model Registry."""

from __future__ import annotations

import json
import math

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature

from .utils import ROOT, load_json, load_yaml, quality_gate_status, sha256, write_json


def validate_registration_input(
    gate: dict, metrics: dict, manifest: dict, data_path, model_path
) -> str:
    if quality_gate_status(gate) != "ACCEPT":
        raise RuntimeError("Model rejected by TP2 quality gate; registration cancelled.")
    if not model_path.is_file():
        raise FileNotFoundError(f"missing model artifact: {model_path}")
    if not data_path.is_file():
        raise FileNotFoundError(f"missing dataset: {data_path}")
    data_sha256 = sha256(data_path)
    if manifest.get("data_sha256") != data_sha256:
        raise RuntimeError("run_manifest data_sha256 does not match the dataset")
    if not manifest.get("run_id") or manifest.get("model_artifact") != "models/model.joblib":
        raise RuntimeError("run_manifest has an invalid run_id or model_artifact")
    required_metrics = ("accuracy", "precision", "recall", "f1", "latency_ms")
    for name in required_metrics:
        value = metrics.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise RuntimeError(f"reports/metrics.json has no valid {name}")
    if any(not 0 <= float(metrics[name]) <= 1 for name in ("accuracy", "precision", "recall", "f1")):
        raise RuntimeError("classification metrics must be between 0 and 1")
    if float(metrics["latency_ms"]) < 0:
        raise RuntimeError("latency_ms must be non-negative")
    manifest_metrics = manifest.get("metrics")
    if not isinstance(manifest_metrics, dict):
        raise RuntimeError("run_manifest must contain metrics")
    for name in required_metrics:
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
            raise RuntimeError(f"run_manifest metric {name} differs from reports/metrics.json")
    return data_sha256


def main() -> None:
    mlflow_cfg = load_yaml(ROOT / "configs/mlflow.yaml")
    gate = load_json(ROOT / "reports/quality_gate_decision.json")
    metrics = load_json(ROOT / "reports/metrics.json")
    manifest = load_json(ROOT / "reports/run_manifest.json")
    data_path = ROOT / "data/raw/machines.csv"
    model_path = ROOT / "models/model.joblib"

    data_sha256 = validate_registration_input(gate, metrics, manifest, data_path, model_path)

    mlflow.set_tracking_uri(mlflow_cfg["tracking_uri"])
    mlflow.set_experiment(mlflow_cfg["experiment_name"])
    model = joblib.load(model_path)
    sample_path = ROOT / "data/processed/test.csv"
    if sample_path.is_file():
        sample = pd.read_csv(sample_path).drop(
            columns=["machine_failure", "machine_id"], errors="ignore"
        ).head(5)
    else:
        sample = pd.read_csv(data_path).drop(
            columns=["machine_failure", "machine_id"], errors="ignore"
        ).head(5)
    signature = infer_signature(sample, model.predict(sample))
    numeric_metrics = {
        key: float(value)
        for key, value in metrics.items()
        if isinstance(value, (int, float))
    }

    with mlflow.start_run() as run:
        mlflow.log_metrics(numeric_metrics)
        mlflow.log_params(
            {
                "quality_gate": "ACCEPT",
                "data_sha256": data_sha256,
                "tp2_run_id": str(manifest.get("run_id", "unknown")),
            }
        )
        mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            signature=signature,
            input_example=sample,
            registered_model_name=mlflow_cfg["registered_model_name"],
        )
        client = mlflow.MlflowClient()
        versions = client.search_model_versions(
            f"name='{mlflow_cfg['registered_model_name']}'"
        )
        current = [version for version in versions if version.run_id == run.info.run_id]
        if not current:
            raise RuntimeError("Could not resolve registered model version.")
        model_version = max(current, key=lambda version: int(version.version))
        tags = {
            "quality_gate": "ACCEPT",
            "data_sha256": data_sha256,
            "tp2_run_id": str(manifest.get("run_id", "unknown")),
            "candidate_f1": str(metrics["f1"]),
            "candidate_recall": str(metrics["recall"]),
            "latency_ms": str(metrics.get("latency_ms", 0.0)),
        }
        for key, value in tags.items():
            client.set_model_version_tag(
                mlflow_cfg["registered_model_name"], model_version.version, key, value
            )

        result = {
            "registered_model": mlflow_cfg["registered_model_name"],
            "version": str(model_version.version),
            "run_id": run.info.run_id,
            "data_sha256": data_sha256,
            "quality_gate": "ACCEPT",
            "metrics": numeric_metrics,
            "model_uri": f"models:/{mlflow_cfg['registered_model_name']}/{model_version.version}",
        }
        write_json(ROOT / "reports/registration.json", result)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
