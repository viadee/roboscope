"""Pydantic schemas for environment management."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class EnvCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    python_version: str = "3.12"
    docker_image: str | None = None
    default_runner_type: str = "subprocess"
    max_docker_containers: int = 1
    is_default: bool = False
    description: str | None = None
    index_url: str | None = None
    extra_index_url: str | None = None


class EnvUpdate(BaseModel):
    name: str | None = None
    python_version: str | None = None
    docker_image: str | None = None
    default_runner_type: str | None = None
    max_docker_containers: int | None = None
    is_default: bool | None = None
    description: str | None = None
    index_url: str | None = None
    extra_index_url: str | None = None


class EnvResponse(BaseModel):
    id: int
    name: str
    python_version: str
    venv_path: str | None = None
    docker_image: str | None = None
    docker_image_built_at: datetime | None = None
    packages_changed_at: datetime | None = None
    docker_image_stale: bool = False
    docker_build_status: str | None = None
    docker_build_error: str | None = None
    docker_build_log: str | None = None
    default_runner_type: str
    max_docker_containers: int
    is_default: bool
    description: str | None = None
    index_url: str | None = None
    extra_index_url: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    python_version_warning: str | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_docker_image_stale(self) -> "EnvResponse":
        if self.docker_image:
            if self.docker_image_built_at is None:
                self.docker_image_stale = True
            elif self.packages_changed_at and self.packages_changed_at > self.docker_image_built_at:
                self.docker_image_stale = True
            else:
                self.docker_image_stale = False
        else:
            self.docker_image_stale = False
        return self


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
