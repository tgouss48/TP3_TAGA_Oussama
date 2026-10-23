"""Produire une décision TP2-compatible avant l'enregistrement du modèle."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def evaluate_quality_gate(metrics: dict, baseline: dict, policy: dict) -> dict:
    checks = []

    def minimum(name: str) -> None:
        observed = float(metrics[name])
        threshold = float(policy[f"min_{name}"])
        checks.append(
            {
                "name": f"minimum_{name}",
                "observed": observed,
                "threshold": threshold,
                "passed": observed >= threshold,
            }
        )

    for name in ("accuracy", "recall", "f1"):
        minimum(name)
    for metric in ("recall", "f1"):
        observed = float(metrics[metric])
        reference = float(baseline[metric])
        allowed_drop = float(policy[f"max_{metric}_regression"])
        checks.append(
            {
                "name": f"baseline_{metric}",
                "observed": observed,
                "baseline": reference,
                "allowed_drop": allowed_drop,
                "passed": observed >= reference - allowed_drop,
            }
        )
    failed = [check["name"] for check in checks if not check["passed"]]
    return {
        "decision": "ACCEPT" if not failed else "REJECT",
        "accepted": not failed,
        "checks": checks,
        "reasons": [f"règle échouée : {name}" for name in failed],
        "metrics": metrics,
        "baseline": baseline,
    }


def main() -> None:
    params = yaml.safe_load((ROOT / "params.yaml").read_text(encoding="utf-8"))
    metrics = json.loads((ROOT / "reports/metrics.json").read_text(encoding="utf-8"))
    baseline = json.loads(
        (ROOT / "quality_gates/baseline_metrics.json").read_text(encoding="utf-8")
    )
    decision = evaluate_quality_gate(metrics, baseline, params["quality"])
    path = ROOT / "reports/quality_gate_decision.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2))
    if decision["decision"] != "ACCEPT":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
