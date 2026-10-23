from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MachineType(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_type: MachineType
    air_temperature_k: float = Field(..., ge=250, le=350)
    process_temperature_k: float = Field(..., ge=250, le=380)
    rotational_speed_rpm: int = Field(..., gt=0, le=5000)
    torque_nm: float = Field(..., ge=0, le=200)
    tool_wear_min: int = Field(..., ge=0, le=1000)


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction: int = Field(..., ge=0, le=1)
    probability: float = Field(..., ge=0, le=1)
    model_name: str
    alias: str
    version: str


class ModelInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    alias: str
    version: str
    run_id: str | None = None
    data_sha256: str
    quality_gate: str
    source: str


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
