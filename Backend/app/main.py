import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import (
    Asset,
    AssetAssignment,
    AssetAssignmentMode,
    AssetHistory,
    Build,
    MemberRole,
    Membership,
    Project,
    StorageProvider,
    Task,
    Tenant,
    User,
)
from .schemas import (
    AssetCreate,
    AssetHistoryRead,
    AssetLock,
    AssetRead,
    AssetUpdate,
    BuildCreate,
    BuildRead,
    ProjectCreate,
    ProjectRead,
    TaskCreate,
    TaskRead,
    TenantCreate,
    TenantRead,
    Token,
    UserRead,
    UserRegister,
    UserSummary,
)
from .security import (
    create_access_token,
    get_current_user,
    hash_password,
    validate_secret_key,
    verify_password,
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


@app.get("/api/tenants/{tenant_id}/members", response_model=list[UserSummary])
def list_tenant_members(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    return db.scalars(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(User.username, User.id)
    ).all()


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
    require_tenant_membership(db, tenant_id, current_user.id)
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
    require_tenant_membership(db, tenant_id, current_user.id)
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
    require_tenant_membership(db, tenant_id, current_user.id)
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
    require_tenant_membership(db, tenant_id, current_user.id)
    get_project(db, tenant_id, project_id)
    assigned_user_ids = list(dict.fromkeys(payload.assigned_user_ids))
    if payload.assignment_mode == AssetAssignmentMode.RESTRICTED and not assigned_user_ids:
        raise HTTPException(status_code=422, detail="El modo restringido requiere al menos un integrante asignado")
    for assigned_user_id in assigned_user_ids:
        require_tenant_membership(db, tenant_id, assigned_user_id)
    asset_fields = payload.model_dump(exclude={"assigned_user_ids"})
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

    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        if (
            asset.assignment_mode == AssetAssignmentMode.RESTRICTED.value
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
    if asset.assignment_mode == AssetAssignmentMode.RESTRICTED.value and not asset.assigned_user_ids:
        raise HTTPException(status_code=422, detail="El modo restringido requiere al menos un integrante asignado")

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
    if asset.locked_by_user_id != current_user.id:
        raise HTTPException(status_code=409, detail="Solo quien bloqueó el asset puede liberarlo")
    record_asset_change(
        db,
        asset,
        current_user,
        "unlocked",
        previous_value=current_user.username or current_user.email,
    )
    asset.locked_by_user_id = None
    asset.locked_at = None
    db.commit()
    db.refresh(asset)
    return asset
