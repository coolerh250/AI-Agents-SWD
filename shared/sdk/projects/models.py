"""Step 57 -- multi-project registry domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

RegistryStatus = Literal["active", "paused", "completed", "archived"]
EnvironmentScope = Literal["dev", "test", "nonprod"]


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    environment_scope: EnvironmentScope = "dev"
    requester: str | None = None


class Project(BaseModel):
    project_id: UUID
    project_key: str
    name: str
    description: str | None = None
    registry_status: RegistryStatus = "active"
    environment_scope: EnvironmentScope = "dev"
    production_allowed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
