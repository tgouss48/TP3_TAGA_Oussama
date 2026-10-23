.PHONY: install doctor lock export-requirements openapi check-openapi release-manifest security-audit image-scan mlflow-server import-tp2 bootstrap-reference validate-tp2 pipeline registry-pipeline api docker-build docker-run docker-smoke test lint validate-submission register select promote rollback report package

UV ?= uv
RUN := $(UV) run --locked
MLFLOW_URL ?= http://127.0.0.1:5000
MODEL_NAME ?= predictive-maintenance
MODEL_ALIAS ?= champion
IMAGE ?= maintenance-ml:tp3
VCS_REF ?= local
CONTAINER ?= maintenance-ml-tp3
PORT ?= 8000
ARCHIVE ?= MLOps_TP3_Nom_Prenom.zip

install:
	$(UV) sync --locked

doctor:
	@command -v $(UV) >/dev/null || { echo "uv est requis : https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@command -v git >/dev/null || { echo "git est requis"; exit 1; }
	@command -v docker >/dev/null || { echo "Docker Engine/Desktop est requis"; exit 1; }
	@command -v curl >/dev/null || { echo "curl est requis"; exit 1; }
	@$(RUN) pytest --version
	@$(RUN) ruff --version
	@$(RUN) mlflow --version
	@echo "Environnement TP3 prêt"

lock:
	$(UV) lock

export-requirements:
	$(UV) export --locked --no-dev --no-hashes --no-header --no-emit-project --output-file requirements.txt

openapi:
	PYTHONPATH=. $(RUN) python scripts/export_openapi.py

check-openapi: openapi
	git diff --exit-code -- contracts/openapi.json

release-manifest:
	PYTHONPATH=. $(RUN) python scripts/create_release_manifest.py

security-audit:
	$(UV) tool run --from pip-audit pip-audit --requirement requirements.txt

image-scan:
	command -v trivy >/dev/null || { echo "Trivy est requis pour ce contrôle optionnel"; exit 2; }
	trivy image --exit-code 1 --severity HIGH,CRITICAL "$(IMAGE)"

mlflow-server:
	$(RUN) mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000

import-tp2:
	test -n "$(TP2_DIR)" || { echo "Usage: make import-tp2 TP2_DIR=/chemin/vers/TP2"; exit 2; }
	PYTHONPATH=. $(RUN) python scripts/import_tp2.py --source "$(TP2_DIR)"

bootstrap-reference:
	PYTHONPATH=. $(RUN) python scripts/bootstrap_reference.py

validate-tp2:
	PYTHONPATH=. $(RUN) python scripts/validate_tp2_input.py

pipeline: test validate-tp2

registry-pipeline: validate-tp2 register select promote

api:
	MLFLOW_TRACKING_URI=$(MLFLOW_URL) MODEL_NAME=$(MODEL_NAME) MODEL_ALIAS=$(MODEL_ALIAS) MODEL_SOURCE=registry $(RUN) uvicorn maintenance_ml.api.main:app --host 127.0.0.1 --port $(PORT)

docker-build:
	docker build --build-arg VCS_REF="$(VCS_REF)" --tag "$(IMAGE)" .

docker-run:
	docker run --rm --init --read-only --tmpfs /tmp --cap-drop=ALL --security-opt no-new-privileges --name "$(CONTAINER)" -p $(PORT):8000 \
		-e MODEL_SOURCE=local -e MODEL_NAME=$(MODEL_NAME) -e MODEL_ALIAS=$(MODEL_ALIAS) \
		"$(IMAGE)"

docker-smoke:
	set -eu; \
	cleanup() { docker rm --force "$(CONTAINER)" >/dev/null 2>&1 || true; }; \
	trap cleanup EXIT; \
	docker rm --force "$(CONTAINER)" >/dev/null 2>&1 || true; \
	docker run --rm --init --read-only --tmpfs /tmp --cap-drop=ALL --security-opt no-new-privileges --detach --name "$(CONTAINER)" -p $(PORT):8000 \
		-e MODEL_SOURCE=local -e MODEL_NAME=$(MODEL_NAME) -e MODEL_ALIAS=$(MODEL_ALIAS) \
		"$(IMAGE)"; \
	if ! $(RUN) python scripts/smoke_test.py --base-url http://127.0.0.1:$(PORT); then \
		docker logs "$(CONTAINER)" || true; \
		exit 1; \
	fi

test:
	mkdir -p reports
	PYTHONPATH=. $(RUN) python -m pytest -q --junitxml=reports/test_report.xml

lint:
	$(RUN) ruff check .

validate-submission:
	PYTHONPATH=. $(RUN) python tests/validate_submission.py

register:
	$(RUN) python -m maintenance_ml.registry.register

select:
	$(RUN) python -m maintenance_ml.registry.select_candidate

promote:
	$(RUN) python -m maintenance_ml.registry.promotion

rollback:
	test -n "$(ROLLBACK_VERSION)" || { echo "Usage: make rollback ROLLBACK_VERSION=1"; exit 2; }
	$(RUN) python -m maintenance_ml.registry.rollback --version "$(ROLLBACK_VERSION)"

report:
	mkdir -p reports/figures
	test -f reports/tp3_report.md || cp reports/tp3_report_template.md reports/tp3_report.md

package:
	$(MAKE) validate-submission
	PYTHONPATH=. $(RUN) python scripts/package_submission.py --output "$(ARCHIVE)"
