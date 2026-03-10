"""Pydantic schemas for environment management."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.environments.venv_utils import mask_url_credentials


def _strip_url(v: str | None) -> str | None:
    """Strip whitespace from a URL string; return None for empty strings."""
    if v is None:
        return None
    stripped = v.strip()
    return stripped if stripped else None


class EnvCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    python_version: str = "3.12"
    docker_image: str | None = None
    default_runner_type: str = "subprocess"
    max_docker_containers: int = 1
    is_default: bool = False
    description: str | None = None
    index_url: str | None = Field(default=None, max_length=500)
    extra_index_url: str | None = Field(default=None, max_length=500)

    @field_validator("index_url", "extra_index_url", mode="before")
    @classmethod
    def strip_registry_urls(cls, v: str | None) -> str | None:
        return _strip_url(v)


class EnvUpdate(BaseModel):
    name: str | None = None
    python_version: str | None = None
    docker_image: str | None = None
    default_runner_type: str | None = None
    max_docker_containers: int | None = None
    is_default: bool | None = None
    description: str | None = None
    index_url: str | None = Field(default=None, max_length=500)
    extra_index_url: str | None = Field(default=None, max_length=500)

    @field_validator("index_url", "extra_index_url", mode="before")
    @classmethod
    def strip_registry_urls(cls, v: str | None) -> str | None:
        return _strip_url(v)


class EnvResponse(BaseModel):
    id: int
    name: str
    python_version: str
    venv_path: str | None = None
    docker_image: str | None = None
    default_runner_type: str
    max_docker_containers: int
    is_default: bool
    description: str | None = None
    index_url: str | None = None
    extra_index_url: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("index_url", "extra_index_url", mode="after")
    @classmethod
    def mask_registry_credentials(cls, v: str | None) -> str | None:
        return mask_url_credentials(v)


class PackageCreate(BaseModel):
    package_name: str = Field(..., min_length=1, max_length=255)
    version: str | None = None


class PackageResponse(BaseModel):
    id: int
    environment_id: int
    package_name: str
    version: str | None = None
    installed_version: str | None = None
    install_status: str = "pending"
    install_error: str | None = None

    model_config = {"from_attributes": True}


class PyPISearchResult(BaseModel):
    name: str
    version: str = ""
    summary: str = ""
    author: str = ""


class EnvVarCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: str
    is_secret: bool = False


class EnvVarResponse(BaseModel):
    id: int
    environment_id: int
    key: str
    value: str
    is_secret: bool

    model_config = {"from_attributes": True}
