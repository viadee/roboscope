"""Pydantic schemas for environment management."""

from datetime import datetime

from pydantic import BaseModel, Field


class EnvCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    python_version: str = "3.12"
    docker_image: str | None = None
    is_default: bool = False
    description: str | None = None


class EnvUpdate(BaseModel):
    name: str | None = None
    python_version: str | None = None
    docker_image: str | None = None
    is_default: bool | None = None
    description: str | None = None


class EnvResponse(BaseModel):
    id: int
    name: str
    python_version: str
    venv_path: str | None = None
    docker_image: str | None = None
    is_default: bool
    description: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PackageCreate(BaseModel):
    package_name: str = Field(..., min_length=1, max_length=255)
    version: str | None = None


class PackageResponse(BaseModel):
    id: int
    environment_id: int
    package_name: str
    version: str | None = None
    installed_version: str | None = None

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
