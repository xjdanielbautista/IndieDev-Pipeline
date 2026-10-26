import hashlib
import hashlib
import hmac
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import (
    Asset,
    AssetAssignment,
    AssetAssignmentMode,
    AssetCommit,
    AssetComment,
    AssetHistory,
    AssetStatus,
    Build,
    MemberRole,
    Membership,
    Notification,
    Project,
    StorageProvider,
    Task,
    Tenant,
    User,
)
from .schemas import (
    AssetCommitRead,
    AssetCommentCreate,
    AssetCommentRead,
    AssetCreate,
    AssetHistoryRead,
    AssetLock,
    AssetRead,
    AssetUpdate,
    BuildCreate,
    BuildRead,
    MemberAdd,
    MemberRead,
    GithubConnect,
    GithubConnectRead,
    MemberRoleUpdate,
    NotificationRead,
    NotificationReadUpdate,
    ProjectCreate,
    ProjectRead,
    TaskCreate,
    TaskRead,
    TenantCreate,
    TenantMembershipRead,
    TenantRead,
    Token,
    UserRead,
    UserRegister,
)
from .permissions import (
    is_manager,
    require_build_role,
    require_can_lock,
    require_can_manage_member,
    require_can_move,
    require_manager,
)
from .security import (
    create_access_token,
    get_current_user,
    hash_password,
    validate_secret_key,
    verify_password,
)
from .storage import (
    tenant_storage_key,
    firebase_download_url,
    format_file_size,
    local_file,
    s3_download_url,
    save_firebase,
    save_local,
    save_s3,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_secret_key()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Indie Dev Pipeline API",
    description="API inicial para la gestión multi-tenant de estudios indie.",
    version="0.1.0",
    lifespan=lifespan,
)
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("indiedev.backend")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error interno no controlado en %s %s", request.method, request.url.path)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )
    origin = request.headers.get("origin")
    if origin in allowed_origins or "*" in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Vary"] = "Origin"
        if origin and "*" not in allowed_origins:
            response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def require_tenant_membership(db: Session, tenant_id: int, user_id: int) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="El usuario no pertenece a este estudio")
    return membership


def get_project(db: Session, tenant_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


def record_asset_change(
    db: Session,
    asset: Asset,
    actor: User,
    action: str,
    previous_value: str | None = None,
    new_value: str | None = None,
) -> None:
    db.add(
        AssetHistory(
            tenant_id=asset.tenant_id,
            asset_id=asset.id,
            user_id=actor.id,
            actor_username=(actor.username or actor.email)[:50],
            action=action,
            previous_value=previous_value,
            new_value=new_value,
        )
    )


def add_notification(
    db: Session,
    recipient_id: int,
    actor_id: int,
    tenant_id: int,
    project_id: int | None,
    asset_id: int | None,
    kind: str,
    message: str,
) -> None:
    if recipient_id == actor_id:
        return
    db.add(Notification(
        user_id=recipient_id,
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=asset_id,
        kind=kind,
        message=message,
    ))


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "indie-dev-pipeline-api"}


@app.post("/api/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    email = payload.email.strip().lower()
    existing_user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.email) == email,
                func.lower(User.username) == username,
            )
        )
    )
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="El correo o nombre de usuario ya está registrado")

    user = User(username=username, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="El correo o nombre de usuario ya está registrado",
        ) from error
    return user


@app.post("/api/auth/token", response_model=Token)
def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    identifier = username.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier,
            )
        )
    )
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario/correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@app.get("/api/auth/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/api/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant = Tenant(name=payload.name, slug=payload.slug, owner_user_id=current_user.id)
    db.add(tenant)
    try:
        db.flush()
        db.add(Membership(tenant_id=tenant.id, user_id=current_user.id, role=MemberRole.OWNER))
        db.commit()
        db.refresh(tenant)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="El identificador del estudio ya existe") from error
    return tenant


@app.get("/api/tenants", response_model=list[TenantMembershipRead])
def list_my_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Tenant, Membership.role)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == current_user.id)
        .order_by(Tenant.name, Tenant.id)
    ).all()
    return [
        TenantMembershipRead.model_validate(
            {**TenantRead.model_validate(tenant).model_dump(), "role": role}
        )
        for tenant, role in rows
    ]


@app.get("/api/tenants/{tenant_id}", response_model=TenantRead)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")
    return tenant


def member_read(user: User, role: MemberRole) -> MemberRead:
    return MemberRead(id=user.id, username=user.username, email=user.email, role=role)


def get_member(db: Session, tenant_id: int, user_id: int) -> Membership:
    membership = db.scalar(
        select(Membership).where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Ese usuario no es integrante del estudio")
    return membership


@app.get("/api/tenants/{tenant_id}/members", response_model=list[MemberRead])
def list_tenant_members(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    rows = db.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(User.username, User.id)
    ).all()
    return [member_read(user, role) for user, role in rows]


@app.post(
    "/api/tenants/{tenant_id}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_tenant_member(
    tenant_id: int,
    payload: MemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = require_tenant_membership(db, tenant_id, current_user.id)
    require_can_manage_member(actor, None, payload.role)
    identifier = payload.identifier.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(func.lower(User.username) == identifier, func.lower(User.email) == identifier)
        )
    )
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una cuenta con ese usuario o correo. Pídele que se registre primero.",
        )
    exists = db.scalar(
        select(Membership).where(Membership.tenant_id == tenant_id, Membership.user_id == user.id)
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="Ese usuario ya es integrante del estudio")
    db.add(Membership(tenant_id=tenant_id, user_id=user.id, role=payload.role))
    db.commit()
    return member_read(user, payload.role)


@app.patch("/api/tenants/{tenant_id}/members/{user_id}", response_model=MemberRead)
def update_tenant_member(
    tenant_id: int,
    user_id: int,
    payload: MemberRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = require_tenant_membership(db, tenant_id, current_user.id)
    target = get_member(db, tenant_id, user_id)
    require_can_manage_member(actor, target, payload.role)
    target.role = payload.role
    db.commit()
    return member_read(db.get(User, user_id), payload.role)


@app.delete("/api/tenants/{tenant_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tenant_member(
    tenant_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = require_tenant_membership(db, tenant_id, current_user.id)
    target = get_member(db, tenant_id, user_id)
    require_can_manage_member(actor, target, None)
    tenant_asset_ids = select(Asset.id).where(Asset.tenant_id == tenant_id)
    # Quita sus asignaciones y libera los archivos que tenía bloqueados en este estudio.
    for assignment in db.scalars(
        select(AssetAssignment).where(
            AssetAssignment.user_id == user_id, AssetAssignment.asset_id.in_(tenant_asset_ids)
        )
    ).all():
        db.delete(assignment)
    for asset in db.scalars(
        select(Asset).where(Asset.tenant_id == tenant_id, Asset.locked_by_user_id == user_id)
    ).all():
        asset.locked_by_user_id = None
        asset.locked_at = None
    db.delete(target)
    db.commit()


@app.post(
    "/api/tenants/{tenant_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    tenant_id: int,
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "crear proyectos")
    if db.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")
    project = Project(tenant_id=tenant_id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/tenants/{tenant_id}/projects", response_model=list[ProjectRead])
def list_projects(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    if db.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")
    return db.scalars(select(Project).where(Project.tenant_id == tenant_id)).all()


@app.post(
    "/api/tenants/{tenant_id}/projects/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    tenant_id: int,
    project_id: int,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "crear tareas")
    get_project(db, tenant_id, project_id)
    task = Task(tenant_id=tenant_id, project_id=project_id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get(
    "/api/tenants/{tenant_id}/projects/{project_id}/tasks",
    response_model=list[TaskRead],
)
def list_tasks(
    tenant_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    get_project(db, tenant_id, project_id)
    return db.scalars(
        select(Task).where(Task.tenant_id == tenant_id, Task.project_id == project_id)
    ).all()


@app.post(
    "/api/tenants/{tenant_id}/projects/{project_id}/builds",
    response_model=BuildRead,
    status_code=status.HTTP_201_CREATED,
)
def create_build(
    tenant_id: int,
    project_id: int,
    payload: BuildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_build_role(membership)
    get_project(db, tenant_id, project_id)
    build = Build(tenant_id=tenant_id, project_id=project_id, **payload.model_dump())
    db.add(build)
    db.commit()
    db.refresh(build)
    return build


@app.get(
    "/api/tenants/{tenant_id}/projects/{project_id}/builds",
    response_model=list[BuildRead],
)
def list_builds(
    tenant_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    get_project(db, tenant_id, project_id)
    return db.scalars(
        select(Build).where(Build.tenant_id == tenant_id, Build.project_id == project_id)
    ).all()


@app.post(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_asset(
    tenant_id: int,
    project_id: int,
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "crear y asignar tareas")
    get_project(db, tenant_id, project_id)
    assigned_user_ids = list(dict.fromkeys(payload.assigned_user_ids))
    if payload.assignment_mode == AssetAssignmentMode.RESTRICTED and not assigned_user_ids:
        raise HTTPException(status_code=422, detail="El modo restringido requiere al menos un integrante asignado")
    for assigned_user_id in assigned_user_ids:
        require_tenant_membership(db, tenant_id, assigned_user_id)
    asset_fields = payload.model_dump(exclude={"assigned_user_ids"})
    # Aislamiento en el storage: la carpeta del tenant la impone el backend.
    asset_fields["storage_key"] = tenant_storage_key(tenant_id, project_id, payload.storage_key)
    provider_name = os.getenv("ASSET_STORAGE_PROVIDER", StorageProvider.FIREBASE.value).lower()
    try:
        storage_provider = StorageProvider(provider_name)
    except ValueError as error:
        raise HTTPException(status_code=500, detail="ASSET_STORAGE_PROVIDER no es válido") from error
    asset = Asset(
        tenant_id=tenant_id,
        project_id=project_id,
        created_by_user_id=current_user.id,
        storage_provider=storage_provider,
        **asset_fields,
    )
    asset.assignments.extend(AssetAssignment(user_id=user_id) for user_id in assigned_user_ids)
    db.add(asset)
    db.flush()
    record_asset_change(
        db,
        asset,
        current_user,
        "created",
        new_value=(
            f"category={asset.category}; status={asset.status}; "
            f"assignment_mode={asset.assignment_mode}"
        ),
    )
    if assigned_user_ids:
        users = db.scalars(select(User).where(User.id.in_(assigned_user_ids))).all()
        names = [user.username or user.email for user in users]
        record_asset_change(db, asset, current_user, "assigned", new_value=", ".join(names))
        for user in users:
            add_notification(
                db,
                user.id,
                current_user.id,
                tenant_id,
                project_id,
                asset.id,
                "assigned",
                f"{current_user.username or current_user.email} te asignó \"{asset.original_name}\"",
            )
    db.commit()
    db.refresh(asset)
    return asset


@app.get(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets",
    response_model=list[AssetRead],
)
def list_assets(
    tenant_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    get_project(db, tenant_id, project_id)
    return db.scalars(
        select(Asset).where(Asset.tenant_id == tenant_id, Asset.project_id == project_id)
    ).all()


@app.get(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}",
    response_model=AssetRead,
)
def get_asset(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.project_id == project_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    return asset


@app.patch(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}",
    response_model=AssetRead,
)
def update_asset(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.project_id == project_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")

    changes = payload.model_dump(exclude_unset=True)
    if any(field in changes for field in ("category", "assignment_mode", "assigned_user_ids")):
        require_manager(membership, "cambiar el tipo o los asignados de una tarea")
    if "status" in changes and changes["status"] is not None:
        require_can_move(membership, asset.category, asset.status, changes["status"].value)
        if (
            not is_manager(membership)
            and asset.assignment_mode == AssetAssignmentMode.RESTRICTED.value
            and current_user.id not in asset.assigned_user_ids
        ):
            raise HTTPException(status_code=403, detail="Solo los integrantes asignados pueden avanzar este asset")
    if "category" in changes:
        if changes["category"] is None:
            raise HTTPException(status_code=422, detail="La categoría no puede ser nula")
        new_category = changes["category"].value
        if new_category != asset.category:
            record_asset_change(db, asset, current_user, "category_changed", asset.category, new_category)
            asset.category = new_category
    if "status" in changes:
        if changes["status"] is None:
            raise HTTPException(status_code=422, detail="El estado no puede ser nulo")
        new_status = changes["status"].value
        if new_status != asset.status:
            record_asset_change(db, asset, current_user, "status_changed", asset.status, new_status)
            asset.status = new_status
    if "assignment_mode" in changes:
        if changes["assignment_mode"] is None:
            raise HTTPException(status_code=422, detail="El modo de asignación no puede ser nulo")
        new_mode = changes["assignment_mode"].value
        if new_mode != asset.assignment_mode:
            record_asset_change(
                db, asset, current_user, "assignment_mode_changed", asset.assignment_mode, new_mode
            )
            asset.assignment_mode = new_mode
    if "assigned_user_ids" in changes:
        new_ids = changes["assigned_user_ids"]
        if new_ids is None:
            raise HTTPException(status_code=422, detail="La lista de integrantes asignados no puede ser nula")
        new_ids = list(dict.fromkeys(new_ids))
        for assigned_user_id in new_ids:
            require_tenant_membership(db, tenant_id, assigned_user_id)
        old_ids = set(asset.assigned_user_ids)
        new_id_set = set(new_ids)
        if old_ids != new_id_set:
            all_ids = old_ids | new_id_set
            users = db.scalars(select(User).where(User.id.in_(all_ids))).all() if all_ids else []
            names = {user.id: user.username or user.email for user in users}
            added_names = [names[user_id] for user_id in new_id_set - old_ids]
            removed_names = [names[user_id] for user_id in old_ids - new_id_set]
            record_asset_change(
                db,
                asset,
                current_user,
                "assignments_changed",
                previous_value=", ".join(removed_names) or None,
                new_value=", ".join(added_names) or None,
            )
            asset.assignments.clear()
            asset.assignments.extend(AssetAssignment(user_id=user_id) for user_id in new_ids)
            for user_id in new_id_set - old_ids:
                add_notification(
                    db,
                    user_id,
                    current_user.id,
                    tenant_id,
                    project_id,
                    asset.id,
                    "assigned",
                    f"{current_user.username or current_user.email} te asignó \"{asset.original_name}\"",
                )
    if asset.assignment_mode == AssetAssignmentMode.RESTRICTED.value and not asset.assigned_user_ids:
        raise HTTPException(status_code=422, detail="El modo restringido requiere al menos un integrante asignado")

    if "status" in changes and changes["status"] is not None:
        new_status = changes["status"] if isinstance(changes["status"], str) else changes["status"].value
        if new_status == AssetStatus.REVIEW.value:
            tester_memberships = db.scalars(
                select(Membership).where(Membership.tenant_id == tenant_id, Membership.role == MemberRole.TESTER)
            ).all()
            for tester_membership in tester_memberships:
                add_notification(
                    db,
                    tester_membership.user_id,
                    current_user.id,
                    tenant_id,
                    project_id,
                    asset.id,
                    "review",
                    f"\"{asset.original_name}\" está listo para revisión",
                )

    db.commit()
    db.refresh(asset)
    return asset


@app.get(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/history",
    response_model=list[AssetHistoryRead],
)
def list_asset_history(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.project_id == project_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    return db.scalars(
        select(AssetHistory)
        .where(AssetHistory.tenant_id == tenant_id, AssetHistory.asset_id == asset_id)
        .order_by(AssetHistory.created_at.desc(), AssetHistory.id.desc())
    ).all()


@app.patch(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/lock",
    response_model=AssetRead,
)
def lock_asset(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    _: AssetLock,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.project_id == project_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    require_can_lock(membership, asset.category)
    if asset.locked_by_user_id is not None and asset.locked_by_user_id != current_user.id:
        raise HTTPException(status_code=409, detail="El asset ya está bloqueado")
    if asset.locked_by_user_id is None:
        record_asset_change(
            db,
            asset,
            current_user,
            "locked",
            new_value=current_user.username or current_user.email,
        )
        asset.locked_by_user_id = current_user.id
        asset.locked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(asset)
    return asset


@app.delete(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/lock",
    response_model=AssetRead,
)
def unlock_asset(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.project_id == project_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    if asset.locked_by_user_id is None:
        raise HTTPException(status_code=409, detail="El asset no está bloqueado")
    if asset.locked_by_user_id != current_user.id and not is_manager(membership):
        raise HTTPException(
            status_code=409,
            detail="Solo quien bloqueó el asset (o el dueño/admin) puede liberarlo",
        )
    locker = db.get(User, asset.locked_by_user_id)
    locker_id = asset.locked_by_user_id
    record_asset_change(
        db,
        asset,
        current_user,
        "unlocked",
        previous_value=(locker.username or locker.email) if locker else None,
    )
    add_notification(
        db,
        locker_id,
        current_user.id,
        tenant_id,
        project_id,
        asset.id,
        "unlocked",
        f"{current_user.username or current_user.email} liberó tu bloqueo de \"{asset.original_name}\"",
    )
    asset.locked_by_user_id = None
    asset.locked_at = None
    db.commit()
    db.refresh(asset)
    return asset


@app.post(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file",
    response_model=AssetRead,
)
async def upload_asset_file(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.project_id == project_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")

    require_can_lock(membership, asset.category)
    if asset.locked_by_user_id != current_user.id:
        raise HTTPException(
            status_code=409,
            detail="Bloquea el archivo antes de subir una nueva versión",
        )

    try:
        max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "200"))
    except ValueError as error:
        raise HTTPException(status_code=500, detail="MAX_UPLOAD_MB no es válido") from error
    max_upload_bytes = max_upload_mb * 1024 * 1024

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"El archivo supera el límite de {max_upload_mb} MB")

    content_type = file.content_type or "application/octet-stream"
    try:
        if asset.storage_provider == StorageProvider.LOCAL.value:
            save_local(asset.storage_key, file.file)
        elif asset.storage_provider == StorageProvider.S3.value:
            save_s3(asset.storage_key, file.file, content_type)
        elif asset.storage_provider == StorageProvider.FIREBASE.value:
            save_firebase(asset.storage_key, file.file, content_type)
        else:
            raise HTTPException(status_code=500, detail="Proveedor de almacenamiento no válido")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo") from error

    uploaded_at = datetime.now(timezone.utc)
    asset.file_size = file_size
    asset.content_type = content_type[:120]
    asset.file_uploaded_at = uploaded_at
    record_asset_change(
        db,
        asset,
        current_user,
        "file_uploaded",
        new_value=f"{file.filename or asset.original_name} ({format_file_size(file_size)})",
    )
    db.commit()
    db.refresh(asset)
    return asset


@app.get("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file")
def download_asset_file(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.project_id == project_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    if asset.file_uploaded_at is None or asset.file_size is None:
        raise HTTPException(status_code=404, detail="Este asset todavía no tiene archivo")

    try:
        if asset.storage_provider == StorageProvider.LOCAL.value:
            path = local_file(asset.storage_key)
            if path is None:
                raise HTTPException(status_code=404, detail="Este asset todavía no tiene archivo")
            return FileResponse(
                path,
                filename=asset.original_name,
                media_type=asset.content_type or "application/octet-stream",
            )
        if asset.storage_provider == StorageProvider.S3.value:
            return s3_download_url(asset.storage_key)
        if asset.storage_provider == StorageProvider.FIREBASE.value:
            result = firebase_download_url(asset.storage_key)
            if result is None:
                raise HTTPException(status_code=404, detail="Este asset todavía no tiene archivo")
            return result
        raise HTTPException(status_code=500, detail="Proveedor de almacenamiento no válido")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail="No se pudo descargar el archivo") from error


@app.post(
    "/api/tenants/{tenant_id}/projects/{project_id}/github",
    response_model=GithubConnectRead,
)
def connect_github(
    tenant_id: int,
    project_id: int,
    payload: GithubConnect,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "configurar GitHub")
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    webhook_secret = secrets.token_hex(32)
    project.github_repo = payload.github_repo.strip()
    project.github_webhook_secret = webhook_secret
    db.commit()
    public_base = os.getenv("PUBLIC_BACKEND_URL", str(request.base_url).rstrip("/"))
    return GithubConnectRead(
        github_repo=project.github_repo,
        webhook_url=f"{public_base}/api/webhooks/github/{project_id}",
        secret=webhook_secret,
    )


@app.post("/api/webhooks/github/{project_id}", status_code=204)
async def github_webhook(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None or not project.github_webhook_secret:
        raise HTTPException(status_code=401, detail="Webhook no configurado o firma inválida")

    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(project.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Webhook no configurado o firma inválida")

    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return Response(status_code=200)
    if event != "push":
        return Response(status_code=204)

    payload = await request.json()
    for commit in payload.get("commits", []):
        message = commit.get("message", "")
        for asset_id_text in re.findall(r"#(\d+)", message):
            asset = db.scalar(select(Asset).where(
                Asset.id == int(asset_id_text),
                Asset.tenant_id == project.tenant_id,
                Asset.project_id == project.id,
            ))
            if asset is None:
                continue
            sha = commit.get("id", "")[:40]
            if not sha or db.scalar(select(AssetCommit).where(AssetCommit.asset_id == asset.id, AssetCommit.sha == sha)):
                continue
            timestamp_text = commit.get("timestamp")
            try:
                committed_at = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                committed_at = datetime.now(timezone.utc)
            db.add(AssetCommit(
                tenant_id=project.tenant_id,
                asset_id=asset.id,
                sha=sha,
                message=message,
                author_name=(commit.get("author") or {}).get("name", "Desconocido")[:120],
                url=commit.get("url", "")[:500],
                committed_at=committed_at,
            ))
    db.commit()
    return Response(status_code=204)


@app.get("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/commits", response_model=list[AssetCommitRead])
def list_asset_commits(tenant_id: int, project_id: int, asset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id, Asset.project_id == project_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    return db.scalars(select(AssetCommit).where(AssetCommit.asset_id == asset_id).order_by(AssetCommit.committed_at.desc(), AssetCommit.id.desc())).all()


@app.get("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/comments", response_model=list[AssetCommentRead])
def list_asset_comments(tenant_id: int, project_id: int, asset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id, Asset.project_id == project_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    return db.scalars(select(AssetComment).where(AssetComment.asset_id == asset_id).order_by(AssetComment.created_at.asc(), AssetComment.id.asc())).all()


@app.post("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/comments", response_model=AssetCommentRead, status_code=201)
def create_asset_comment(tenant_id: int, project_id: int, asset_id: int, payload: AssetCommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id, Asset.project_id == project_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="El comentario no puede estar vacío")

    comment = AssetComment(tenant_id=tenant_id, asset_id=asset.id, user_id=current_user.id, body=body)
    db.add(comment)
    recipient_ids = set(asset.assigned_user_ids)
    if asset.created_by_user_id is not None:
        recipient_ids.add(asset.created_by_user_id)
    recipient_ids.discard(current_user.id)
    for recipient_id in recipient_ids:
        db.add(Notification(user_id=recipient_id, tenant_id=tenant_id, project_id=project_id, asset_id=asset.id, kind="comment", message=f"{current_user.username or current_user.email} comentó en \"{asset.original_name}\""))
    db.commit()
    db.refresh(comment)
    return comment


@app.delete("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/comments/{comment_id}", status_code=204)
def delete_asset_comment(tenant_id: int, project_id: int, asset_id: int, comment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    comment = db.scalar(select(AssetComment).where(AssetComment.id == comment_id, AssetComment.tenant_id == tenant_id, AssetComment.asset_id == asset_id))
    if comment is None:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if comment.user_id != current_user.id and not is_manager(membership):
        raise HTTPException(status_code=403, detail="Solo el autor o un dueño/admin puede eliminar el comentario")
    db.delete(comment)
    db.commit()
    return Response(status_code=204)


@app.get("/api/notifications", response_model=list[NotificationRead])
def list_notifications(limit: int = 30, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    limit = min(max(limit, 1), 100)
    notifications = db.scalars(select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)).all()
    return [{"id": item.id, "kind": item.kind, "message": item.message, "tenant_id": item.tenant_id, "project_id": item.project_id, "asset_id": item.asset_id, "read": item.read_at is not None, "created_at": item.created_at} for item in notifications]


@app.post("/api/notifications/read", status_code=204)
def mark_notifications_read(payload: NotificationReadUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if payload.all:
        notifications = db.scalars(query).all()
    else:
        if payload.ids is None:
            raise HTTPException(status_code=422, detail="Debe enviar ids o all=true")
        notifications = db.scalars(query.where(Notification.id.in_(payload.ids))).all()
    for notification in notifications:
        notification.read_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)
