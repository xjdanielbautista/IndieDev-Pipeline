import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Asset, Build, MemberRole, Membership, Project, Task, Tenant, User
from .schemas import (
    AssetCreate,
    AssetLock,
    AssetRead,
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
    asset = Asset(tenant_id=tenant_id, project_id=project_id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@app.patch(
    "/api/tenants/{tenant_id}/assets/{asset_id}/lock",
    response_model=AssetRead,
)
def lock_asset(
    tenant_id: int,
    asset_id: int,
    _: AssetLock,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    if asset.locked_by_user_id is not None and asset.locked_by_user_id != current_user.id:
        raise HTTPException(status_code=409, detail="El asset ya está bloqueado")
    asset.locked_by_user_id = current_user.id
    asset.locked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(asset)
    return asset


@app.delete("/api/tenants/{tenant_id}/assets/{asset_id}/lock", response_model=AssetRead)
def unlock_asset(
    tenant_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    if asset.locked_by_user_id != current_user.id:
        raise HTTPException(status_code=409, detail="Solo quien bloqueó el asset puede liberarlo")
    asset.locked_by_user_id = None
    asset.locked_at = None
    db.commit()
    db.refresh(asset)
    return asset
