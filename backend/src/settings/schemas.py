"""Pydantic schemas for application settings."""

from pydantic import BaseModel


class SettingResponse(BaseModel):
    id: int
    key: str
    value: str
    value_type: str
    category: str
    description: str | None = None

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingsBulkUpdate(BaseModel):
    settings: list[SettingUpdate]
