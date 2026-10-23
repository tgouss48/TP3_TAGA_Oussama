import pytest

from maintenance_ml.registry.promotion import decide_promotion
from maintenance_ml.registry.select_candidate import choose_candidate, is_eligible


ELIGIBILITY = {
    "min_f1": 0.64,
    "min_recall": 0.60,
    "max_latency_ms": 50,
    "require_quality_gate": True,
}


def candidate(version, f1, recall, latency_ms=20, gate=True):
    row = {
        "version": str(version),
        "f1": f1,
        "recall": recall,
        "latency_ms": latency_ms,
        "quality_gate": gate,
        "data_sha256": "sha-test" if gate else None,
    }
    row["eligible"] = is_eligible(row, ELIGIBILITY)
    return row


def test_quality_gate_rejection_makes_candidate_ineligible():
    assert candidate(1, f1=0.90, recall=0.80, gate=False)["eligible"] is False


def test_data_hash_is_required_for_registry_eligibility():
    row = candidate(1, f1=0.90, recall=0.80)
    row["data_sha256"] = None
    assert is_eligible(row, ELIGIBILITY) is False


def test_latency_is_applied_before_ranking():
    slow = candidate(1, f1=0.90, recall=0.80, latency_ms=80)
    eligible = candidate(2, f1=0.70, recall=0.65)
    assert choose_candidate([slow, eligible], "f1")["version"] == "2"


def test_no_eligible_candidate_is_not_selected():
    rejected = candidate(1, f1=0.40, recall=0.30)
    assert choose_candidate([rejected], "f1") is None


def test_ranking_uses_recall_as_tie_breaker():
    first = candidate(1, f1=0.70, recall=0.60)
    second = candidate(2, f1=0.70, recall=0.65)
    assert choose_candidate([first, second], "f1")["version"] == "2"


def test_first_candidate_can_be_promoted():
    promote, reasons = decide_promotion(
        None,
        {"f1": 0.70, "recall": 0.65, "latency_ms": 20},
        {"minimum_f1_gain": 0.01, "minimum_recall_gain": -0.01},
    )
    assert promote is True
    assert reasons["reason"] == "no current champion"


def test_small_gain_keeps_champion():
    promote, reasons = decide_promotion(
        {"f1": 0.70, "recall": 0.65, "latency_ms": 20},
        {"f1": 0.705, "recall": 0.66, "latency_ms": 18},
        {"minimum_f1_gain": 0.01, "minimum_recall_gain": -0.01},
    )
    assert promote is False
    assert reasons["f1_gain"] < 0.01


def test_recall_regression_beyond_policy_keeps_champion():
    promote, reasons = decide_promotion(
        {"f1": 0.70, "recall": 0.70, "latency_ms": 20},
        {"f1": 0.72, "recall": 0.68, "latency_ms": 18},
        {"minimum_f1_gain": 0.01, "minimum_recall_gain": -0.01},
    )
    assert promote is False
    assert reasons["recall_gain"] == pytest.approx(-0.02)
