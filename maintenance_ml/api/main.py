"""Service FastAPI du TP3, chargé depuis un alias MLflow.

Le service garde les routes historiques et expose le même contrat sous ``/v1``.
Cette compatibilité permet au TP4 et à un futur frontend de migrer sans
dupliquer la logique d'inférence.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time
from uuid import uuid4

import joblib
import mlflow
import mlflow.sklearn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
import yaml

from .schemas import (
    ErrorResponse,
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
)


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models/model.joblib"
SERVICE_CONFIG_PATH = ROOT / "configs/service.yaml"
LOGGER = logging.getLogger("maintenance_ml.api")
model = None
model_metadata: dict = {}
model_load_error: str | None = None

REQUESTS = Counter(
    "mlops_http_requests",
    "HTTP requests handled by the TP3 service",
    ("method", "route", "status"),
)
REQUEST_LATENCY = Histogram(
    "mlops_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "route"),
)
INFERENCE_ERRORS = Counter(
    "mlops_inference_errors",
    "Inference errors by category",
    ("reason",),
)
MODEL_LOADED = Gauge(
    "mlops_model_loaded",
    "Whether the configured model is loaded",
    ("model_name", "alias", "version"),
)


def settings() -> dict:
    """Read the single service configuration with explicit env overrides."""

    config = {}
    if SERVICE_CONFIG_PATH.is_file():
        config = yaml.safe_load(SERVICE_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    configured_origins = config.get("cors_allowed_origins", []) or []
    raw_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    cors_origins = (
        [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        if raw_origins is not None
        else list(configured_origins)
    )
    return {
        "tracking_uri": os.getenv(
            "MLFLOW_TRACKING_URI", config.get("tracking_uri", "http://127.0.0.1:5000")
        ),
        "model_name": os.getenv(
            "MODEL_NAME", config.get("model_name", "predictive-maintenance")
        ),
        "alias": os.getenv("MODEL_ALIAS", config.get("model_alias", "champion")),
        "source": os.getenv("MODEL_SOURCE", config.get("model_source", "registry")),
        "cors_allowed_origins": cors_origins,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _local_metadata(config: dict) -> dict:
    gate_path = ROOT / "reports/quality_gate_decision.json"
    manifest_path = ROOT / "reports/run_manifest.json"
    data_path = ROOT / "data/raw/machines.csv"
    if not gate_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("TP2 acceptance artifacts are missing")
    gate = _load_json(gate_path)
    manifest = _load_json(manifest_path)
    if gate.get("decision") != "ACCEPT":
        raise RuntimeError("TP2 quality gate is not ACCEPT")
    data_sha256 = manifest.get("data_sha256")
    if not data_sha256:
        raise RuntimeError("TP2 manifest has no data_sha256")
    if not data_path.is_file():
        raise RuntimeError("TP2 reference dataset is missing")
    if _sha256(data_path) != data_sha256:
        raise RuntimeError("TP2 data_sha256 does not match the local dataset")
    return {
        "model_name": config["model_name"],
        "alias": config["alias"],
        "version": "local",
        "run_id": manifest.get("run_id"),
        "data_sha256": data_sha256,
        "quality_gate": "ACCEPT",
        "source": "local",
    }


def resolve_model() -> tuple[object, dict]:
    config = settings()
    if config["source"] == "local":
        metadata = _local_metadata(config)
        return joblib.load(MODEL_PATH), metadata
    if config["source"] != "registry":
        raise RuntimeError("MODEL_SOURCE must be either local or registry")

    mlflow.set_tracking_uri(config["tracking_uri"])
    client = mlflow.MlflowClient()
    version = client.get_model_version_by_alias(config["model_name"], config["alias"])
    loaded = mlflow.sklearn.load_model(
        f"models:/{config['model_name']}@{config['alias']}"
    )
    tags = version.tags or {}
    if tags.get("quality_gate") != "ACCEPT":
        raise RuntimeError("Registry version is not backed by an ACCEPT quality gate")
    if not tags.get("data_sha256"):
        raise RuntimeError("Registry version has no data_sha256 tag")
    return loaded, {
        "model_name": config["model_name"],
        "alias": config["alias"],
        "version": str(version.version),
        "run_id": version.run_id,
        "data_sha256": tags.get("data_sha256"),
        "quality_gate": "ACCEPT",
        "source": "registry",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, model_load_error, model_metadata
    try:
        model, model_metadata = resolve_model()
        model_load_error = None
        MODEL_LOADED.labels(
            model_metadata["model_name"],
            model_metadata["alias"],
            model_metadata["version"],
        ).set(1)
    except Exception as exc:
        model = None
        model_metadata = {}
        model_load_error = type(exc).__name__
        config = settings()
        MODEL_LOADED.labels(config["model_name"], config["alias"], "unresolved").set(0)
        LOGGER.warning("Model loading failed: %s", model_load_error)
    yield
    model = None


app = FastAPI(
    title="Predictive Maintenance API",
    version="2.1.0",
    description="Versioned inference contract for the MLOps TP3 product.",
    lifespan=lifespan,
    responses={
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)

_config = settings()
if _config["cors_allowed_origins"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_config["cors_allowed_origins"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": _request_id(request),
                "details": details,
            }
        },
    )
    response.headers["X-Request-ID"] = _request_id(request)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [
        {
            "type": error.get("type", "validation_error"),
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid value"),
        }
        for error in exc.errors()
    ]
    return _error_response(
        request,
        422,
        "validation_error",
        "Request validation failed",
        details,
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    details = exc.detail if isinstance(exc.detail, list) else None
    return _error_response(
        request,
        exc.status_code,
        f"http_{exc.status_code}",
        message,
        details,
    )


@app.middleware("http")
async def observe_http(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        route = request.scope.get("route")
        route_name = getattr(route, "path", request.url.path)
        duration = time.perf_counter() - start
        REQUESTS.labels(request.method, route_name, str(status_code)).inc()
        REQUEST_LATENCY.labels(request.method, route_name).observe(duration)
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_name,
                    "status": status_code,
                    "duration_ms": round(duration * 1000, 3),
                },
                ensure_ascii=False,
            )
        )


@app.get("/health", tags=["service"], operation_id="health")
@app.get("/v1/health", tags=["service"], operation_id="v1_health")
def health():
    payload = {
        "status": "ok" if model is not None else "degraded",
        "model_loaded": model is not None,
        "model_name": model_metadata.get("model_name"),
        "alias": model_metadata.get("alias"),
        "version": model_metadata.get("version"),
        "source": model_metadata.get("source"),
        "load_error": model_load_error,
    }
    if model is None:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get(
    "/model-info",
    response_model=ModelInfoResponse,
    tags=["service"],
    operation_id="model_info",
)
@app.get(
    "/v1/model-info",
    response_model=ModelInfoResponse,
    tags=["service"],
    operation_id="v1_model_info",
)
def model_info():
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return model_metadata


@app.get("/metrics", tags=["observability"], operation_id="metrics")
@app.get("/v1/metrics", tags=["observability"], operation_id="v1_metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["inference"],
    operation_id="predict",
)
@app.post(
    "/v1/predict",
    response_model=PredictionResponse,
    tags=["inference"],
    operation_id="v1_predict",
)
def predict(payload: PredictionRequest):
    if model is None:
        INFERENCE_ERRORS.labels("model_not_loaded").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")
    import pandas as pd

    frame = pd.DataFrame([payload.model_dump()])
    frame["machine_type"] = frame["machine_type"].astype(str)
    try:
        prediction = int(model.predict(frame)[0])
        probabilities = model.predict_proba(frame)[0]
        classes = list(getattr(model, "classes_", [0, 1]))
        class_index = classes.index(1) if 1 in classes else 1
        probability = float(probabilities[class_index])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("model returned an invalid probability")
    except Exception as exc:
        INFERENCE_ERRORS.labels("model_inference").inc()
        raise HTTPException(status_code=500, detail="Inference failed") from exc
    return PredictionResponse(
        prediction=prediction,
        probability=probability,
        model_name=model_metadata["model_name"],
        alias=model_metadata["alias"],
        version=model_metadata["version"],
    )
