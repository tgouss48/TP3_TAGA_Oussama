"""Réaffecter explicitement l'alias champion à une version antérieure."""

from __future__ import annotations

import argparse
import json

import mlflow

from .utils import ROOT, load_yaml, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    config = load_yaml(ROOT / "configs/mlflow.yaml")
    policy = load_yaml(ROOT / "configs/promotion_policy.yaml")
    mlflow.set_tracking_uri(config["tracking_uri"])
    client = mlflow.MlflowClient()
    name = policy["model_name"]
    alias = policy["aliases"]["champion"]
    before = client.get_model_version_by_alias(name, alias)
    if str(before.version) == str(args.version):
        raise RuntimeError("rollback target is already the current champion")
    target = client.get_model_version(name, str(args.version))
    target_tags = target.tags or {}
    if target_tags.get("quality_gate") != "ACCEPT" or not target_tags.get(
        "data_sha256"
    ):
        raise RuntimeError(
            "rollback target must have quality_gate=ACCEPT and data_sha256"
        )
    client.set_registered_model_alias(name, alias, target.version)
    decision = {
        "alias": alias,
        "previous_version": str(before.version),
        "restored_version": str(target.version),
        "decision": "ROLLBACK",
        "reason": "explicit operator request",
    }
    write_json(ROOT / "reports/rollback_decision.json", decision)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
