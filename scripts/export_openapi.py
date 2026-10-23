"""Exporter le contrat OpenAPI versionné du service TP3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from maintenance_ml.api.main import app


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "contracts/openapi.json"
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Contrat OpenAPI écrit : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
