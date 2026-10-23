"""Utilities shared by the TP3 Registry commands."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = dict(payload)
    document.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quality_gate_status(payload: dict) -> str:
    """Normalize TP2's canonical decision and the old starter spelling."""

    decision = payload.get("decision")
    if decision in {"ACCEPT", "REJECT"}:
        return decision
    if "accepted" in payload:
        return "ACCEPT" if payload["accepted"] is True else "REJECT"
    return "REJECT"


def numeric_tag(tags: dict, key: str, default: float = float("-inf")) -> float:
    try:
        return float(tags.get(key, default))
    except (TypeError, ValueError):
        return default
