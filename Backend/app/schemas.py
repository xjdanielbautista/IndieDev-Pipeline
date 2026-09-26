from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import BuildStatus, StorageProvider, TaskArea, TaskStage, TaskStatus


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    owner_email: str = Field(min_length=3, max_length=255)


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    owner_user_id: int
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    created_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    stage: TaskStage = TaskStage.PRE_PRODUCTION
    area: TaskArea = TaskArea.PROGRAMMING
    status: TaskStatus = TaskStatus.TODO


class TaskRead(TaskCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    project_id: int
    created_at: datetime


class BuildCreate(BaseModel):
    version: str = Field(min_length=1, max_length=60)
    notes: str | None = None
    status: BuildStatus = BuildStatus.PENDING
    build_url: str | None = Field(default=None, max_length=500)


class BuildRead(BuildCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    project_id: int
    created_at: datetime


class AssetCreate(BaseModel):
    original_name: str = Field(min_length=1, max_length=255)
    storage_key: str = Field(min_length=1, max_length=500)
    storage_provider: StorageProvider


class AssetRead(AssetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    project_id: int
    locked_by_user_id: int | None
    locked_at: datetime | None
    created_at: datetime


class AssetLock(BaseModel):
    user_id: int