from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
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
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Indie Dev Pipeline API",
    description="API inicial para la gestión multi-tenant de estudios indie.",
    version="0.1.0",
    lifespan=lifespan,
)


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


@app.post("/api/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.owner_email.lower()))
    if user is None:
        user = User(email=payload.owner_email.lower())
        db.add(user)
        db.flush()
    tenant = Tenant(name=payload.name, slug=payload.slug, owner_user_id=user.id)
    db.add(tenant)
    try:
        db.flush()
        db.add(Membership(tenant_id=tenant.id, user_id=user.id, role=MemberRole.OWNER))
        db.commit()
        db.refresh(tenant)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="El identificador del estudio ya existe") from error
    return tenant

@app.get("/api/tenants/{tenant_id}", response_model=TenantRead)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")
    return tenant

@app.post(
    "/api/tenants/{tenant_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(tenant_id: int, payload: ProjectCreate, db: Session = Depends(get_db)):
    if db.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")
    project = Project(tenant_id=tenant_id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/tenants/{tenant_id}/projects", response_model=list[ProjectRead])
def list_projects(tenant_id: int, db: Session = Depends(get_db)):
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
):
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
def list_tasks(tenant_id: int, project_id: int, db: Session = Depends(get_db)):
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
):
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
def list_builds(tenant_id: int, project_id: int, db: Session = Depends(get_db)):
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
):
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
def lock_asset(tenant_id: int, asset_id: int, payload: AssetLock, db: Session = Depends(get_db)):
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    membership = db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == payload.user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="El usuario no pertenece a este estudio")
    if asset.locked_by_user_id is not None and asset.locked_by_user_id != payload.user_id:
        raise HTTPException(status_code=409, detail="El asset ya está bloqueado")
    asset.locked_by_user_id = payload.user_id
    asset.locked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(asset)
    return asset


@app.delete("/api/tenants/{tenant_id}/assets/{asset_id}/lock", response_model=AssetRead)
def unlock_asset(tenant_id: int, asset_id: int, user_id: int, db: Session = Depends(get_db)):
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    if asset.locked_by_user_id != user_id:
        raise HTTPException(status_code=409, detail="Solo quien bloqueó el asset puede liberarlo")
    membership = db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="El usuario no pertenece a este estudio")
    asset.locked_by_user_id = None
    asset.locked_at = None
    db.commit()
    db.refresh(asset)
    return asset