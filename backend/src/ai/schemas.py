"""Pydantic schemas for AI module."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Provider schemas ---


class AiProviderCreate(BaseModel):
    """Request to create/update an LLM provider."""

    name: str = Field(..., min_length=1, max_length=100)
    provider_type: str = Field(..., pattern=r"^(openai|anthropic|openrouter|ollama)$")
    api_base_url: str | None = None
    api_key: str | None = None  # plaintext; encrypted before storage
    model_name: str = Field(..., min_length=1, max_length=100)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=256, le=128000)
    is_default: bool = False


class AiProviderUpdate(BaseModel):
    """Partial update for a provider."""

    name: str | None = None
    provider_type: str | None = None
    api_base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    is_default: bool | None = None


class AiProviderResponse(BaseModel):
    """Provider response (never exposes API key)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider_type: str
    api_base_url: str | None = None
    has_api_key: bool = False
    model_name: str
    temperature: float
    max_tokens: int
    is_default: bool
    created_by: int
    created_at: datetime
    updated_at: datetime


# --- Job schemas ---


class GenerateRequest(BaseModel):
    """Request to generate .robot from .roboscope spec."""

    repository_id: int
    spec_path: str = Field(..., min_length=1)
    provider_id: int | None = None  # None = use default provider
    force: bool = False  # skip drift warning


class ReverseRequest(BaseModel):
    """Request to extract .roboscope spec from .robot file."""

    repository_id: int
    robot_path: str = Field(..., min_length=1)
    provider_id: int | None = None
    output_path: str | None = None  # where to save .roboscope; auto-derived if None


class JobAcceptRequest(BaseModel):
    """Accept a completed job's result (writes file)."""

    job_id: int


class ValidateSpecRequest(BaseModel):
    """Request to validate .roboscope YAML syntax."""

    content: str


class AiJobResponse(BaseModel):
    """Job status response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: str
    repository_id: int
    provider_id: int
    spec_path: str
    target_path: str | None = None
    result_preview: str | None = None
    error_message: str | None = None
    token_usage: int | None = None
    triggered_by: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


# --- Drift schemas ---


class DriftResult(BaseModel):
    """Drift detection result for a single .roboscope file."""

    spec_file: str
    target_file: str
    status: str  # in_sync, drifted, missing


class DriftResponse(BaseModel):
    """Drift check response for a repository."""

    repository_id: int
    results: list[DriftResult]


# --- Spec validation ---


class ValidateSpecResponse(BaseModel):
    """Validation result."""

    valid: bool
    errors: list[str] = []
    test_count: int = 0
