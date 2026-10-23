"""Produire un checkpoint TP2 de secours, clairement identifié comme tel."""

from __future__ import annotations

import subprocess
import sys
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def generate_reference_dataset() -> None:
    """Créer un dataset équilibré et déterministe pour le parcours de secours."""

    rng = np.random.default_rng(42)
    rows = 5_000
    machine_type = rng.choice(["A", "B", "C"], rows, p=[0.45, 0.35, 0.20])
    air_temperature = rng.normal(298, 3, rows).clip(290, 310)
    frame = pd.DataFrame(
        {
            "machine_id": [f"REF-{index:05d}" for index in range(rows)],
            "machine_type": machine_type,
            "air_temperature_k": air_temperature,
            "process_temperature_k": (air_temperature + rng.normal(10, 1.5, rows)).clip(
                300, 320
            ),
            "rotational_speed_rpm": rng.normal(1500, 180, rows)
            .clip(900, 2300)
            .round()
            .astype(int),
            "torque_nm": rng.normal(45, 8, rows).clip(15, 80),
            "tool_wear_min": rng.integers(0, 250, rows),
        }
    )
    frame["machine_failure"] = (
        ((frame["torque_nm"] > 55) & (frame["tool_wear_min"] > 100))
        | ((frame["rotational_speed_rpm"] < 1200) & (frame["torque_nm"] > 50))
    ).astype(int)
    frame.to_csv(ROOT / "data/raw/machines.csv", index=False)


def main() -> int:
    generate_reference_dataset()
    commands = (
        [sys.executable, "-m", "maintenance_ml.data.prepare"],
        [sys.executable, "-m", "maintenance_ml.modeling.train"],
        [sys.executable, "-m", "maintenance_ml.modeling.evaluate"],
        [sys.executable, "-m", "maintenance_ml.modeling.quality_gate"],
    )
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    digest = hashlib.sha256((ROOT / "data/raw/machines.csv").read_bytes()).hexdigest()
    metrics = json.loads((ROOT / "reports/metrics.json").read_text(encoding="utf-8"))
    manifest = {
        "run_id": "tp3-reference-run",
        "data_sha256": digest,
        "metrics": metrics,
        "model_artifact": "models/model.joblib",
        "source": "bootstrap-reference",
    }
    (ROOT / "reports/run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "reports/tp2_import.json").write_text(
        json.dumps(
            {
                "source": "bootstrap-reference",
                "quality_gate": "ACCEPT",
                "parent_run_id": "tp3-reference-run",
                "data_sha256": digest,
                "model_artifact": "models/model.joblib",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        "Checkpoint de secours généré. Pour le parcours complet, démarrez MLflow "
        "puis exécutez make register, make select et make promote."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
