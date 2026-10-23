"""Créer l'archive finale TP3 après validation."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = re.compile(r"^MLOps_TP3_[^/\\]+\.zip$")
EXCLUDED_DIRECTORIES = {
    ".dvc",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "mlartifacts",
    "mlruns",
}
EXCLUDED_FILES = {"mlflow.db", ".env", ".env.local", ".DS_Store"}


def files_for_archive(output: Path):
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        if (
            path.name in EXCLUDED_FILES
            or path.name.endswith(".env")
            or path.suffix.lower() in {".zip", ".log"}
        ):
            continue
        if path.resolve() == output:
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="MLOps_TP3_Nom_Prenom.zip")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not ARCHIVE_NAME.fullmatch(output.name):
        parser.error("le nom doit respecter MLOps_TP3_Nom_Prenom.zip")
    if ROOT not in output.parents:
        parser.error("l'archive doit être créée dans la racine du projet")
    entries = list(files_for_archive(output))
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in entries:
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"Archive créée : {output}")
    print(f"Fichiers archivés : {len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
