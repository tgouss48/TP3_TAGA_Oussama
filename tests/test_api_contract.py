import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from maintenance_ml.api import main


PAYLOAD = {
    "machine_type": "A",
    "air_temperature_k": 298.1,
    "process_temperature_k": 308.6,
    "rotational_speed_rpm": 1551,
    "torque_nm": 42.8,
    "tool_wear_min": 0,
}


class FakeModel:
    def predict(self, frame):
        assert list(frame.columns) == list(PAYLOAD)
        return [1]

    def predict_proba(self, frame):
        return [[0.2, 0.8]]


@pytest.fixture
def loaded_service(monkeypatch):
    metadata = {
        "model_name": "predictive-maintenance",
        "alias": "champion",
        "version": "2",
        "run_id": "run-test",
        "data_sha256": "sha-test",
        "quality_gate": "ACCEPT",
        "source": "registry",
    }
    monkeypatch.setattr(main, "resolve_model", lambda: (FakeModel(), metadata))
    with TestClient(main.app) as client:
        yield client


def test_health_exposes_loaded_model(loaded_service):
    response = loaded_service.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is True
    assert response.json()["version"] == "2"
    assert response.headers["X-Request-ID"]

    versioned = loaded_service.get("/v1/health")
    assert versioned.status_code == 200
    assert versioned.json()["version"] == "2"


def test_model_info_exposes_registry_identity(loaded_service):
    response = loaded_service.get("/model-info")
    assert response.status_code == 200
    assert response.json()["alias"] == "champion"
    assert response.json()["run_id"] == "run-test"


def test_predict_returns_prediction_probability_and_identity(loaded_service):
    response = loaded_service.post("/predict", json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] == 1
    assert body["probability"] == pytest.approx(0.8)
    assert body["version"] == "2"

    versioned = loaded_service.post("/v1/predict", json=PAYLOAD)
    assert versioned.status_code == 200
    assert versioned.json()["model_name"] == "predictive-maintenance"


def test_missing_field_is_rejected_before_inference(loaded_service):
    invalid = dict(PAYLOAD)
    invalid.pop("torque_nm")
    response = loaded_service.post("/predict", json=invalid)
    assert response.status_code == 422


def test_unknown_field_is_rejected_by_pydantic(loaded_service):
    invalid = {**PAYLOAD, "unexpected": 1}
    response = loaded_service.post("/predict", json=invalid)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["request_id"]
    assert response.json()["error"]["details"]


def test_negative_operating_value_is_rejected(loaded_service):
    invalid = {**PAYLOAD, "rotational_speed_rpm": 0}
    response = loaded_service.post("/predict", json=invalid)
    assert response.status_code == 422


def test_metrics_endpoint_exposes_service_metrics(loaded_service):
    loaded_service.get("/health")
    response = loaded_service.get("/metrics")
    assert response.status_code == 200
    assert "mlops_http_requests_total" in response.text


def test_missing_model_returns_503(monkeypatch):
    def fail_to_load():
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(main, "resolve_model", fail_to_load)
    with TestClient(main.app) as client:
        health = client.get("/health")
        info = client.get("/model-info")
    assert health.status_code == 503
    assert health.json()["model_loaded"] is False
    assert info.status_code == 503
    assert info.json()["error"]["code"] == "http_503"
    assert info.json()["error"]["request_id"]


def test_prediction_response_rejects_invalid_probability():
    with pytest.raises(ValidationError):
        main.PredictionResponse(
            prediction=1,
            probability=1.2,
            model_name="predictive-maintenance",
            alias="champion",
            version="2",
        )


def test_service_defaults_come_from_single_configuration(monkeypatch):
    for variable in ("MLFLOW_TRACKING_URI", "MODEL_NAME", "MODEL_ALIAS", "MODEL_SOURCE"):
        monkeypatch.delenv(variable, raising=False)
    config = main.settings()
    assert config == {
        "tracking_uri": "http://127.0.0.1:5000",
        "model_name": "predictive-maintenance",
        "alias": "champion",
        "source": "registry",
        "cors_allowed_origins": [],
    }


def test_cors_origins_are_explicitly_configurable(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000, http://localhost:4173")
    assert main.settings()["cors_allowed_origins"] == [
        "http://localhost:3000",
        "http://localhost:4173",
    ]
