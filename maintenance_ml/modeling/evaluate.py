from pathlib import Path
import json
import time

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    frame = pd.read_csv(ROOT / "data/processed/test.csv")
    features = frame.drop(columns=["machine_failure", "machine_id"])
    target = frame["machine_failure"]
    model = joblib.load(ROOT / "models/model.joblib")
    start = time.perf_counter()
    predictions = model.predict(features)
    latency_ms = (time.perf_counter() - start) * 1000 / len(features)
    metrics = {
        "accuracy": accuracy_score(target, predictions),
        "precision": precision_score(target, predictions, zero_division=0),
        "recall": recall_score(target, predictions, zero_division=0),
        "f1": f1_score(target, predictions, zero_division=0),
        "latency_ms": latency_ms,
    }
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
