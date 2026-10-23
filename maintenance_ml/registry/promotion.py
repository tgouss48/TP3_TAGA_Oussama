"""Comparer challenger et champion puis produire une décision auditable."""

from __future__ import annotations

import json

import mlflow

from .select_candidate import is_eligible
from .utils import ROOT, load_yaml, numeric_tag, write_json


def decide_promotion(
    champion: dict | None, challenger: dict, policy: dict
) -> tuple[bool, dict]:
    if champion is None:
        return True, {"reason": "no current champion"}
    f1_gain = challenger["f1"] - champion["f1"]
    recall_gain = challenger["recall"] - champion["recall"]
    promote = (
        f1_gain >= policy["minimum_f1_gain"]
        and recall_gain >= policy["minimum_recall_gain"]
    )
    return promote, {
        "f1_gain": f1_gain,
        "recall_gain": recall_gain,
        "challenger_latency_ms": challenger["latency_ms"],
        "minimum_f1_gain": policy["minimum_f1_gain"],
        "minimum_recall_gain": policy["minimum_recall_gain"],
    }


def _version_metrics(version) -> dict:
    tags = version.tags or {}
    return {
        "version": str(version.version),
        "f1": numeric_tag(tags, "candidate_f1"),
        "recall": numeric_tag(tags, "candidate_recall"),
        "latency_ms": numeric_tag(tags, "latency_ms", float("inf")),
        "quality_gate": tags.get("quality_gate") == "ACCEPT",
        "data_sha256": tags.get("data_sha256"),
    }


def main() -> None:
    mlflow_cfg = load_yaml(ROOT / "configs/mlflow.yaml")
    policy = load_yaml(ROOT / "configs/promotion_policy.yaml")
    mlflow.set_tracking_uri(mlflow_cfg["tracking_uri"])
    client = mlflow.MlflowClient()
    name = policy["model_name"]
    challenger = client.get_model_version_by_alias(name, policy["aliases"]["challenger"])
    try:
        champion = client.get_model_version_by_alias(name, policy["aliases"]["champion"])
    except mlflow.exceptions.MlflowException:
        champion = None

    challenger_metrics = _version_metrics(challenger)
    if not is_eligible(challenger_metrics, policy["eligibility"]):
        raise RuntimeError(
            "challenger alias does not point to an eligible ACCEPT candidate"
        )
    promote, reasons = decide_promotion(
        None if champion is None else _version_metrics(champion),
        challenger_metrics,
        policy["promotion"],
    )
    decision = {
        "champion_version": None if champion is None else str(champion.version),
        "challenger_version": str(challenger.version),
        "decision": "PROMOTE" if promote else "KEEP_CHAMPION",
        "reasons": reasons,
    }
    if promote:
        client.set_registered_model_alias(name, policy["aliases"]["champion"], challenger.version)
    write_json(ROOT / "reports/promotion_decision.json", decision)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
