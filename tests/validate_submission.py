"""Contrôle final du contrat de remise TP3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REPORT_SECTIONS = (
    "## 0. Continuité avec le TP2",
    "## 1. Contrat d'inférence",
    "## 2. Docker et exécution",
    "## 3. CI",
    "## 4. Enregistrement Registry",
    "## 5. Sélection du challenger",
    "## 6. Promotion",
    "## 7. Rollback",
    "## Questions d'ingénierie",
    "## Index des preuves",
    "## Conclusion",
)
REQUIRED_EVIDENCE_LABELS = (
    "Installation et `make doctor`",
    "Tests API",
    "Réponses des trois endpoints",
    "Contrat OpenAPI",
    "Erreur HTTP 422",
    "Image Docker",
    "Conteneur Docker",
    "Job CI vert",
    "Job CI échoué",
    "Version Registry",
    "Décision de promotion",
    "Rollback",
    "Release manifest",
)
EVIDENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
PLACEHOLDER_PATTERNS = (
    re.compile(r"\[\s*à\s+compléter\s*\]", re.IGNORECASE),
    re.compile(r"\bà\s+compléter\b", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
)


def read_json(path: Path, label: str, errors: list[str]) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} JSON invalide: {exc}")
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_report(path: Path) -> list[str]:
    errors: list[str] = []
    content = path.read_text(encoding="utf-8")
    for section in REPORT_SECTIONS:
        if section not in content:
            errors.append(f"rapport: section absente: {section}")
    for label in REQUIRED_EVIDENCE_LABELS:
        if label not in content:
            errors.append(f"rapport: preuve obligatoire absente: {label}")
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(content):
            errors.append(f"rapport: marqueur non remplacé: {pattern.pattern}")
            break

    question_matches = list(re.finditer(r"^### Q(\d+) — .+$", content, re.MULTILINE))
    numbers = [int(match.group(1)) for match in question_matches]
    if numbers != list(range(1, 9)):
        errors.append("rapport: les questions Q1 à Q8 doivent être présentes dans l'ordre")
    for index, match in enumerate(question_matches):
        next_match = question_matches[index + 1] if index + 1 < len(question_matches) else None
        end = next_match.start() if next_match else content.find("## Index des preuves")
        block = content[match.start() : end if end > match.start() else len(content)]
        marker = "**Réponse de l'étudiant :**"
        if marker not in block:
            errors.append(f"rapport: réponse absente pour Q{match.group(1)}")
        elif len(block.split(marker, 1)[1].strip()) < 80:
            errors.append(f"rapport: réponse Q{match.group(1)} trop courte")
    return errors


def validate_test_report(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return [f"test_report.xml invalide: {exc}"]
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    total = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", 0)) for suite in suites)
    failures += sum(int(suite.attrib.get("errors", 0)) for suite in suites)
    if total - skipped < 6:
        errors.append("test_report.xml: au moins six tests doivent être exécutés")
    if failures:
        errors.append(f"test_report.xml: tests en échec ({failures})")
    return errors


def validate_evidence(root: Path) -> list[str]:
    figures = root / "reports/figures"
    files = [
        path
        for path in figures.rglob("*")
        if path.is_file() and path.name != ".gitkeep" and path.suffix.lower() in EVIDENCE_EXTENSIONS
    ]
    if len(files) < len(REQUIRED_EVIDENCE_LABELS):
        return [
            f"reports/figures doit contenir au moins {len(REQUIRED_EVIDENCE_LABELS)} preuves réelles"
        ]
    return []


def validate_json_contracts(root: Path) -> list[str]:
    errors: list[str] = []
    registration = read_json(root / "reports/registration.json", "registration", errors)
    selection = read_json(root / "reports/model_selection.json", "model_selection", errors)
    promotion = read_json(root / "reports/promotion_decision.json", "promotion", errors)
    rollback = read_json(root / "reports/rollback_decision.json", "rollback", errors)
    if registration is not None:
        for key in ("registered_model", "version", "run_id", "model_uri", "data_sha256"):
            if key not in registration:
                errors.append(f"registration.json: champ manquant {key}")
            elif not registration.get(key):
                errors.append(f"registration.json: champ vide {key}")
        if registration.get("quality_gate") != "ACCEPT":
            errors.append("registration.json: seul un modèle ACCEPT peut être enregistré")
        if not isinstance(registration.get("metrics"), dict):
            errors.append("registration.json: métriques absentes")
    if selection is not None:
        selected = selection.get("selected_candidate")
        if selected is None:
            errors.append("model_selection.json: aucun challenger sélectionné")
        else:
            selected_row = next(
                (
                    row
                    for row in selection.get("versions", [])
                    if str(row.get("version")) == str(selected)
                ),
                None,
            )
            if selected_row is None:
                errors.append(
                    "model_selection.json: le challenger sélectionné est absent des versions inspectées"
                )
            elif selected_row.get("eligible") is not True:
                errors.append(
                    "model_selection.json: le challenger sélectionné doit être éligible"
                )
    if promotion is not None:
        decision = promotion.get("decision")
        if decision not in {"PROMOTE", "KEEP_CHAMPION"}:
            errors.append("promotion_decision.json: décision invalide")
        if decision == "PROMOTE":
            if selection is not None and str(promotion.get("challenger_version")) != str(
                selection.get("selected_candidate")
            ):
                errors.append(
                    "promotion_decision.json: PROMOTE doit concerner le challenger sélectionné"
                )
        elif decision == "KEEP_CHAMPION" and not promotion.get("champion_version"):
            errors.append(
                "promotion_decision.json: KEEP_CHAMPION exige une version champion"
            )
    if rollback is not None:
        if rollback.get("decision") != "ROLLBACK":
            errors.append("rollback_decision.json: décision ROLLBACK attendue")
        if not rollback.get("restored_version"):
            errors.append("rollback_decision.json: version restaurée absente")
        if rollback.get("previous_version") == rollback.get("restored_version"):
            errors.append("rollback_decision.json: le rollback doit changer la version champion")
    release = read_json(root / "reports/release_manifest.json", "release_manifest", errors)
    if release is not None:
        if release.get("schema_version") != "tp3.release_manifest.v1":
            errors.append("release_manifest.json: schema_version incorrecte")
        for section in ("model", "image", "decisions"):
            if not isinstance(release.get(section), dict):
                errors.append(f"release_manifest.json: section absente {section}")
        model = release.get("model", {})
        for key in ("name", "alias", "version", "run_id", "data_sha256", "quality_gate", "metrics"):
            if not model.get(key):
                errors.append(f"release_manifest.json: champ modèle absent {key}")
        if model.get("quality_gate") != "ACCEPT":
            errors.append("release_manifest.json: le modèle doit être ACCEPT")
        if model.get("alias") != "champion":
            errors.append("release_manifest.json: le modèle effectif doit être champion")
        if not isinstance(model.get("metrics"), dict):
            errors.append("release_manifest.json: métriques du modèle effectif absentes")
        promotion_decision = promotion.get("decision") if promotion else None
        expected_version = None
        if promotion_decision == "PROMOTE":
            expected_version = promotion.get("challenger_version")
        elif promotion_decision == "KEEP_CHAMPION":
            expected_version = promotion.get("champion_version")
        if rollback is not None and rollback.get("decision") == "ROLLBACK":
            expected_version = rollback.get("restored_version")
        if expected_version is not None and str(model.get("version")) != str(expected_version):
            errors.append("release_manifest.json: version champion incohérente avec les décisions")
    return errors


def main() -> int:
    required = (
        ".github/workflows/mlops-ci.yml",
        ".dockerignore",
        "Dockerfile",
        "Makefile",
        "configs/mlflow.yaml",
        "configs/promotion_policy.yaml",
        "configs/service.yaml",
        "maintenance_ml/api/main.py",
        "maintenance_ml/api/schemas.py",
        "contracts/openapi.json",
        "maintenance_ml/registry/register.py",
        "maintenance_ml/registry/select_candidate.py",
        "maintenance_ml/registry/promotion.py",
        "maintenance_ml/registry/rollback.py",
        "tests/test_api_contract.py",
        "tests/test_openapi_contract.py",
        "tests/test_registry_policy.py",
        "reports/test_report.xml",
        "reports/tp3_report.md",
        "reports/registration.json",
        "reports/model_selection.json",
        "reports/promotion_decision.json",
        "reports/rollback_decision.json",
        "reports/release_manifest.json",
        "reports/quality_gate_decision.json",
        "reports/run_manifest.json",
        "reports/metrics.json",
        "reports/tp2_import.json",
        "models/model.joblib",
    )
    errors = [f"fichier manquant: {path}" for path in required if not (ROOT / path).exists()]
    report = ROOT / "reports/tp3_report.md"
    if report.exists():
        errors.extend(validate_report(report))
    test_report = ROOT / "reports/test_report.xml"
    if test_report.exists():
        errors.extend(validate_test_report(test_report))
    errors.extend(validate_evidence(ROOT))
    errors.extend(validate_json_contracts(ROOT))

    gate = read_json(ROOT / "reports/quality_gate_decision.json", "quality_gate", errors)
    manifest = read_json(ROOT / "reports/run_manifest.json", "run_manifest", errors)
    data = ROOT / "data/raw/machines.csv"
    if gate is not None and gate.get("decision") != "ACCEPT":
        errors.append("quality_gate_decision.json: la remise doit partir d'un ACCEPT")
    if manifest is not None and data.exists() and manifest.get("data_sha256") != sha256(data):
        errors.append("run_manifest.json: data_sha256 incohérent")
    if manifest is not None:
        if not manifest.get("run_id"):
            errors.append("run_manifest.json: run_id absent")
        if manifest.get("model_artifact") != "models/model.joblib":
            errors.append("run_manifest.json: model_artifact doit être models/model.joblib")
    tp2_import = read_json(ROOT / "reports/tp2_import.json", "tp2_import", errors)
    if tp2_import is not None and tp2_import.get("quality_gate") != "ACCEPT":
        errors.append("tp2_import.json: seul un import ACCEPT est recevable")

    dockerfile = ROOT / "Dockerfile"
    if dockerfile.exists():
        docker_text = dockerfile.read_text(encoding="utf-8")
        for marker in ("USER app", "HEALTHCHECK", "CMD [", "@sha256:"):
            if marker not in docker_text:
                errors.append(f"Dockerfile: directive obligatoire absente: {marker}")
    makefile = ROOT / "Makefile"
    if makefile.exists():
        make_text = makefile.read_text(encoding="utf-8")
        for marker in ("--read-only", "--tmpfs /tmp", "--cap-drop=ALL", "no-new-privileges"):
            if marker not in make_text:
                errors.append(f"Makefile: durcissement Docker absent: {marker}")
    workflow = ROOT / ".github/workflows/mlops-ci.yml"
    if workflow.exists():
        workflow_text = workflow.read_text(encoding="utf-8")
        for marker in ("pytest", "docker build", "docker-smoke"):
            if marker not in workflow_text:
                errors.append(f"workflow CI: étape absente: {marker}")
        if "make promote" in workflow_text or "promotion.py" in workflow_text:
            errors.append("workflow CI: la promotion ne doit pas être automatique")

    openapi = read_json(ROOT / "contracts/openapi.json", "openapi", errors)
    if openapi is not None:
        paths = openapi.get("paths", {})
        for path in ("/v1/health", "/v1/model-info", "/v1/predict", "/v1/metrics"):
            if path not in paths:
                errors.append(f"openapi.json: route versionnée absente: {path}")

    if errors:
        print("VALIDATION TP3: REJECT")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("VALIDATION TP3: ACCEPT — contrat de remise complet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
