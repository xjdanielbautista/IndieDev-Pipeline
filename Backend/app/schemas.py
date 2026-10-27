from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AssetCategory,
    AssetAssignmentMode,
    AssetStatus,
    BuildStatus,
    MemberRole,
    TaskArea,
    TaskStage,
    TaskStatus,
)


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None


class TenantActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_username: str
    action: str
    summary: str
    created_at: datetime


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    owner_user_id: int
    created_at: datetime


class TenantMembershipRead(TenantRead):
    role: MemberRole


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    github_repo: str | None = None
    created_at: datetime


class GithubConnect(BaseModel):
    github_repo: str = Field(min_length=3, max_length=200, pattern=r"^[^/\s]+/[^/\s]+$")


class GithubConnectRead(BaseModel):
    github_repo: str
    webhook_url: str
    secret: str


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
    category: AssetCategory = AssetCategory.ART
    status: AssetStatus = AssetStatus.BACKLOG
    assignment_mode: AssetAssignmentMode = AssetAssignmentMode.OPEN
    assigned_user_ids: list[int] = Field(default_factory=list)


class AssetUpdate(BaseModel):
    category: AssetCategory | None = None
    status: AssetStatus | None = None
    assignment_mode: AssetAssignmentMode | None = None
    assigned_user_ids: list[int] | None = None


class MemberRead(BaseModel):
    id: int
    username: str | None
    email: str
    role: MemberRole


class MemberAdd(BaseModel):
    identifier: str = Field(min_length=3, max_length=255, description="Nombre de usuario o correo")
    role: MemberRole = MemberRole.DEVELOPER


class MemberRoleUpdate(BaseModel):
    role: MemberRole


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None


class AssetRead(AssetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    project_id: int
    created_by_user_id: int | None
    created_by: UserSummary | None
    assigned_users: list[UserSummary]
    locked_by_user_id: int | None
    locked_at: datetime | None
    file_size: int | None
    content_type: str | None
    file_uploaded_at: datetime | None
    created_at: datetime


class AssetHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    asset_id: int
    user_id: int | None
    actor_username: str
    action: str
    previous_value: str | None
    new_value: str | None
    created_at: datetime


class AssetLock(BaseModel):
    """Empty request body; the authenticated user is the one locking the asset."""

    pass


class AssetCommitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sha: str
    message: str
    author_name: str
    url: str
    committed_at: datetime


class AssetCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class AssetCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    user: UserSummary | None
    body: str
    created_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    message: str
    tenant_id: int
    project_id: int | None
    asset_id: int | None
    read: bool
    created_at: datetime


class NotificationReadUpdate(BaseModel):
    ids: list[int] | None = None
    all: bool = False
