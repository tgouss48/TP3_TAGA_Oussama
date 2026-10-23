"""Filtrer les versions admissibles puis désigner le challenger."""

from __future__ import annotations

import json

import mlflow

from .utils import ROOT, load_yaml, numeric_tag, write_json


def is_eligible(candidate: dict, policy: dict) -> bool:
    return (
        bool(candidate.get("data_sha256"))
        and candidate["f1"] >= policy["min_f1"]
        and candidate["recall"] >= policy["min_recall"]
        and candidate["latency_ms"] <= policy["max_latency_ms"]
        and (candidate["quality_gate"] or not policy["require_quality_gate"])
    )


def choose_candidate(candidates: list[dict], ranking_metric: str) -> dict | None:
    eligible = [candidate for candidate in candidates if candidate["eligible"]]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda candidate: (
            candidate[ranking_metric],
            candidate["recall"],
            -candidate["latency_ms"],
            int(candidate["version"]),
        ),
    )


def main() -> None:
    mlflow_cfg = load_yaml(ROOT / "configs/mlflow.yaml")
    policy = load_yaml(ROOT / "configs/promotion_policy.yaml")
    mlflow.set_tracking_uri(mlflow_cfg["tracking_uri"])
    client = mlflow.MlflowClient()
    try:
        champion_version = str(
            client.get_model_version_by_alias(
                policy["model_name"], policy["aliases"]["champion"]
            ).version
        )
    except mlflow.exceptions.MlflowException:
        champion_version = None
    inspected = []
    for version in client.search_model_versions(
        f"name='{policy['model_name']}'"
    ):
        tags = version.tags or {}
        row = {
            "version": str(version.version),
            "f1": numeric_tag(tags, "candidate_f1"),
            "recall": numeric_tag(tags, "candidate_recall"),
            "latency_ms": numeric_tag(tags, "latency_ms", float("inf")),
            "quality_gate": tags.get("quality_gate") == "ACCEPT",
            "data_sha256": tags.get("data_sha256"),
        }
        row["is_current_champion"] = row["version"] == champion_version
        row["eligible"] = (
            not row["is_current_champion"]
            and is_eligible(row, policy["eligibility"])
        )
        inspected.append(row)

    candidate = choose_candidate(inspected, policy["ranking_metric"])
    if candidate is None:
        decision = {
            "selected_candidate": None,
            "challenger_alias": policy["aliases"]["challenger"],
            "versions": inspected,
            "reason": "no eligible model version",
        }
    else:
        alias = policy["aliases"]["challenger"]
        client.set_registered_model_alias(policy["model_name"], alias, candidate["version"])
        decision = {
            "selected_candidate": candidate["version"],
            "challenger_alias": alias,
            "candidate": candidate,
            "versions": inspected,
        }
    write_json(ROOT / "reports/model_selection.json", decision)
    print(json.dumps(decision, indent=2))
    if candidate is None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
