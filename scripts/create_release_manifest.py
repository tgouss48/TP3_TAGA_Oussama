"""Assembler les identités du modèle, de l'image et des décisions de release."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

import mlflow
import yaml


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/release_manifest.json")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output

    registration = read_json(ROOT / "reports/registration.json")
    promotion = read_json(ROOT / "reports/promotion_decision.json")
    rollback_path = ROOT / "reports/rollback_decision.json"
    rollback = read_json(rollback_path) if rollback_path.is_file() else None
    selection_path = ROOT / "reports/model_selection.json"
    selection = read_json(selection_path) if selection_path.is_file() else None

    promotion_decision = promotion.get("decision")
    if rollback is not None and rollback.get("decision") == "ROLLBACK":
        expected_version = str(rollback.get("restored_version"))
    elif promotion_decision == "PROMOTE":
        expected_version = str(promotion.get("challenger_version"))
    elif promotion_decision == "KEEP_CHAMPION":
        expected_version = str(promotion.get("champion_version"))
    else:
        raise ValueError("Impossible de déterminer la version champion effective")

    mlflow_config = yaml.safe_load(
        (ROOT / "configs/mlflow.yaml").read_text(encoding="utf-8")
    ) or {}
    model_name = registration["registered_model"]
    mlflow.set_tracking_uri(mlflow_config["tracking_uri"])
    client = mlflow.MlflowClient()
    champion = client.get_model_version_by_alias(model_name, "champion")
    if str(champion.version) != expected_version:
        raise ValueError(
            "L'alias champion ne correspond pas à la décision effective : "
            f"attendu={expected_version}, observé={champion.version}"
        )
    tags = champion.tags or {}
    if tags.get("quality_gate") != "ACCEPT" or not tags.get("data_sha256"):
        raise ValueError("La version champion effective doit être ACCEPT et porter data_sha256")
    run_metrics = dict(client.get_run(champion.run_id).data.metrics)
    for metric in ("f1", "recall", "latency_ms"):
        if metric not in run_metrics:
            raise ValueError(f"La version champion effective ne porte pas la métrique {metric}")

    manifest = {
        "schema_version": "tp3.release_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": git_revision(),
        "model": {
            "name": model_name,
            "alias": "champion",
            "version": str(champion.version),
            "run_id": champion.run_id,
            "data_sha256": tags["data_sha256"],
            "quality_gate": tags["quality_gate"],
            "source_registration_version": registration["version"],
            "metrics": run_metrics,
        },
        "image": {
            "name": os.getenv("IMAGE", "maintenance-ml:tp3"),
            "id": os.getenv("IMAGE_ID"),
        },
        "decisions": {
            "selected_candidate": None if selection is None else selection.get("selected_candidate"),
            "promotion": promotion_decision,
            "rollback": None if rollback is None else rollback.get("decision"),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Release manifest écrit : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
