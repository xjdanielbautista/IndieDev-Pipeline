from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TaskStage(str, Enum):
    PRE_PRODUCTION = "pre_production"
    ALPHA = "alpha"
    BETA = "beta"
    TESTING = "testing"


class TaskArea(str, Enum):
    PROGRAMMING = "programming"
    ART_3D = "art_3d"
    SOUND = "sound"
    LEVEL_DESIGN = "level_design"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class MemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    ARTIST = "artist"
    TESTER = "tester"


class BuildStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class StorageProvider(str, Enum):
    FIREBASE = "firebase"
    S3 = "s3"
    LOCAL = "local"


class AssetCategory(str, Enum):
    CODE = "code"
    ART = "art"


class AssetStatus(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class AssetAssignmentMode(str, Enum):
    OPEN = "open"
    RESTRICTED = "restricted"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Nullable so existing users can be migrated and assigned credentials later.
    username: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[MemberRole] = mapped_column(SqlEnum(MemberRole), default=MemberRole.DEVELOPER)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[TaskStage] = mapped_column(SqlEnum(TaskStage), default=TaskStage.PRE_PRODUCTION)
    area: Mapped[TaskArea] = mapped_column(SqlEnum(TaskArea), default=TaskArea.PROGRAMMING)
    status: Mapped[TaskStatus] = mapped_column(SqlEnum(TaskStatus), default=TaskStatus.TODO)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Build(Base):
    __tablename__ = "builds"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BuildStatus] = mapped_column(SqlEnum(BuildStatus), default=BuildStatus.PENDING)
    build_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))
    storage_provider: Mapped[StorageProvider] = mapped_column(SqlEnum(StorageProvider))
    category: Mapped[str] = mapped_column(
        String(20), default=AssetCategory.ART.value, server_default=text("'art'")
    )
    status: Mapped[str] = mapped_column(
        String(20), default=AssetStatus.BACKLOG.value, server_default=text("'backlog'")
    )
    assignment_mode: Mapped[str] = mapped_column(
        String(20), default=AssetAssignmentMode.OPEN.value, server_default=text("'open'")
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    locked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    assignments: Mapped[list["AssetAssignment"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def assigned_user_ids(self) -> list[int]:
        return [assignment.user_id for assignment in self.assignments]

    @property
    def assigned_users(self) -> list[User]:
        return [assignment.user for assignment in self.assignments]


class AssetAssignment(Base):
    __tablename__ = "asset_assignments"
    __table_args__ = (UniqueConstraint("asset_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    asset: Mapped[Asset] = relationship(back_populates="assignments")
    user: Mapped[User] = relationship()


class AssetHistory(Base):
    __tablename__ = "asset_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_username: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(40))
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
