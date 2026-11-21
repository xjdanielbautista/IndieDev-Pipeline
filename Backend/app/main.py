import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import (
    Asset,
    AssetAssignment,
    AssetAssignmentMode,
    AssetCommit,
    AssetComment,
    AssetFileVersion,
    AssetHistory,
    AssetStatus,
    Build,
    EmailVerificationToken,
    MemberRole,
    LoginThrottle,
    UserSession,
    Membership,
    Notification,
    PasswordResetToken,
    Project,
    StorageProvider,
    Task,
    Tenant,
    TenantActivity,
    User,
)
from .schemas import (
    SessionRead,
    AssetCommitRead,
    AssetCommentCreate,
    AssetCommentRead,
    AssetCreate,
    AssetFileVersionRead,
    AssetHistoryRead,
    AssetLock,
    AssetRead,
    AssetUpdate,
    AccountDelete,
    AdminTenantRead,
    AdminUserRead,
    BuildCreate,
    CurrentUserRead,
    EmailVerificationConfirm,
    BuildRead,
    MemberAdd,
    MemberRead,
    GithubConnect,
    GithubConnectRead,
    MemberRoleUpdate,
    NotificationRead,
    NotificationReadUpdate,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    TaskCreate,
    TaskRead,
    TenantActivityRead,
    TenantCreate,
    TenantMembershipRead,
    TenantRead,
    TenantUpdate,
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
    get_current_user,
    hash_password,
    start_session,
    validate_secret_key,
    verify_password,
)
from .mailer import send_email
from .storage import (
    delete_stored_file,
    tenant_storage_key,
    firebase_download_url,
    format_file_size,
    local_file,
    read_stored_file,
    s3_download_url,
    save_firebase,
    save_local,
    save_s3,
    version_storage_key,
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
    # Permite al frontend distinguir una descarga directa de una URL firmada.
    expose_headers=["Content-Disposition"],
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


# ---------- Protección contra fuerza bruta en el login ----------
# Tras MAX_FAILED_LOGINS intentos fallidos dentro de LOGIN_WINDOW_MINUTES, el usuario/correo
# queda bloqueado LOGIN_LOCK_MINUTES. Se guarda en la base para que sobreviva reinicios.
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))
LOGIN_WINDOW_MINUTES = int(os.getenv("LOGIN_WINDOW_MINUTES", "15"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))


def utcnow() -> datetime:
    """Hora UTC sin zona (así la guardan igual SQLite, MySQL y PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def too_many_attempts(locked_until: datetime, now: datetime) -> HTTPException:
    seconds = max(int((locked_until - now).total_seconds()), 1)
    minutes = -(-seconds // 60)
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Demasiados intentos fallidos. Intenta de nuevo en {minutes} minuto(s).",
        headers={"Retry-After": str(seconds)},
    )


def register_failed_login(
    db: Session, throttle: LoginThrottle | None, identifier: str, now: datetime
) -> datetime | None:
    """Cuenta un intento fallido. Devuelve la hora de desbloqueo si con este se bloquea."""
    window_start = now - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    if throttle is None:
        # Limpieza de registros viejos para que la tabla no crezca sin límite.
        db.execute(
            delete(LoginThrottle).where(
                LoginThrottle.first_failed_at < now - timedelta(days=1),
                or_(LoginThrottle.locked_until.is_(None), LoginThrottle.locked_until < now),
            )
        )
        throttle = LoginThrottle(identifier=identifier, failed_count=0, first_failed_at=now)
        db.add(throttle)
    elif throttle.first_failed_at < window_start or throttle.locked_until is not None:
        throttle.failed_count = 0
        throttle.first_failed_at = now
        throttle.locked_until = None

    throttle.failed_count += 1
    if throttle.failed_count >= MAX_FAILED_LOGINS:
        throttle.locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
    try:
        db.commit()
    except IntegrityError:
        # Dos intentos simultáneos crearon el mismo registro; basta con uno.
        db.rollback()
        return None
    return throttle.locked_until


# ---------- Bitácora del estudio ----------
def log_activity(db: Session, tenant_id: int, actor: User, action: str, summary: str) -> None:
    """Agrega una entrada a la bitácora; se guarda con el commit de la acción."""
    db.add(
        TenantActivity(
            tenant_id=tenant_id,
            user_id=actor.id,
            actor_username=(actor.username or actor.email)[:50],
            action=action,
            summary=summary[:300],
        )
    )


def stored_files(db: Session, *conditions) -> list[tuple[str, str]]:
    """(proveedor, ruta) de todos los archivos guardados de los assets que cumplen `conditions`.

    Incluye cada versión y la ruta original (archivos de antes de las versiones).
    Restaurar reutiliza rutas, por eso se quitan los repetidos.
    """
    rows = db.execute(
        select(Asset.storage_provider, Asset.storage_key).where(
            Asset.file_uploaded_at.is_not(None), *conditions
        )
    ).all()
    files = {(getattr(provider, "value", provider), key) for provider, key in rows}
    version_rows = db.execute(
        select(AssetFileVersion.storage_provider, AssetFileVersion.storage_key)
        .join(Asset, Asset.id == AssetFileVersion.asset_id)
        .where(*conditions)
    ).all()
    files.update((provider, key) for provider, key in version_rows)
    return sorted(files)


def remove_stored_files(files: list[tuple[str, str]]) -> None:
    """Borra los archivos del almacenamiento después de borrar sus registros.

    Si el proveedor falla, solo se registra el error: los datos ya se eliminaron
    y no tiene sentido devolverle un error al usuario por un archivo huérfano.
    """
    for provider, storage_key in files:
        try:
            delete_stored_file(provider, storage_key)
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo borrar el archivo %s (%s)", storage_key, provider)


def superadmin_emails() -> set[str]:
    return {email.strip().lower() for email in os.getenv("SUPERADMIN_EMAILS", "").split(",") if email.strip()}


def is_superadmin(user: User) -> bool:
    """Superadmin de toda la plataforma, definido por SUPERADMIN_EMAILS.

    Exige el correo confirmado: si no, alguien podría registrarse con ese correo
    antes que su dueño y quedarse con el acceso.
    """
    return user.email_verified_at is not None and user.email.lower() in superadmin_emails()


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Solo el administrador de la plataforma puede hacer esto")
    return current_user


def display_name(user: User | None) -> str:
    if user is None:
        return "usuario eliminado"
    return user.username or user.email


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "indie-dev-pipeline-api"}


@app.post("/api/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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
    queue_verification_email(db, user, background_tasks)
    return user


@app.post("/api/auth/token", response_model=Token)
def login_for_access_token(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    identifier = username.strip().lower()
    now = utcnow()
    throttle = db.scalar(select(LoginThrottle).where(LoginThrottle.identifier == identifier[:255]))
    if throttle is not None and throttle.locked_until is not None and throttle.locked_until > now:
        raise too_many_attempts(throttle.locked_until, now)

    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier,
            )
        )
    )
    if user is None or not verify_password(password, user.password_hash):
        locked_until = register_failed_login(db, throttle, identifier[:255], now)
        if locked_until is not None:
            raise too_many_attempts(locked_until, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario/correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if throttle is not None:
        db.delete(throttle)
        db.commit()
    if email_verification_required() and user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirma tu correo para entrar. Revisa tu bandeja o pide un enlace nuevo.",
        )
    return Token(access_token=start_session(db, user, request))


def current_user_read(user: User) -> CurrentUserRead:
    return CurrentUserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        is_superadmin=is_superadmin(user),
    )


@app.get("/api/auth/me", response_model=CurrentUserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user_read(current_user)


# ---------- Recuperación de contraseña ----------
PASSWORD_RESET_MINUTES = int(os.getenv("PASSWORD_RESET_MINUTES", "30"))
MAX_RESET_REQUESTS = 3  # por usuario cada 15 minutos
RESET_REQUESTED_MESSAGE = (
    "Si el correo está registrado, te enviamos un enlace para restablecer tu contraseña."
)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def frontend_url() -> str:
    return os.getenv("FRONTEND_URL", allowed_origins[0] if allowed_origins else "").rstrip("/")


@app.post("/api/auth/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Envía un enlace de recuperación. Responde lo mismo exista o no el correo."""
    now = utcnow()
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None:
        # Limpieza de enlaces viejos para que la tabla no crezca sin límite.
        db.execute(delete(PasswordResetToken).where(PasswordResetToken.expires_at < now - timedelta(days=1)))
        recent = db.scalar(
            select(func.count(PasswordResetToken.id)).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at > now - timedelta(minutes=15),
            )
        )
        if recent < MAX_RESET_REQUESTS:
            # Solo el enlace más reciente sirve.
            for previous in db.scalars(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
                )
            ).all():
                previous.used_at = now
            token = secrets.token_urlsafe(32)
            db.add(PasswordResetToken(
                user_id=user.id,
                token_hash=hash_reset_token(token),
                created_at=now,
                expires_at=now + timedelta(minutes=PASSWORD_RESET_MINUTES),
            ))
            db.commit()
            link = f"{frontend_url()}/?reset_token={token}"
            background_tasks.add_task(
                send_email,
                user.email,
                "Restablece tu contraseña de IndieDev Pipeline",
                f"Hola {display_name(user)}:\n\n"
                f"Recibimos una solicitud para restablecer tu contraseña. Abre este enlace "
                f"(vence en {PASSWORD_RESET_MINUTES} minutos y solo se puede usar una vez):\n\n"
                f"{link}\n\n"
                "Si no lo pediste, ignora este correo: tu contraseña no cambiará.",
            )
        else:
            db.commit()
    return {"detail": RESET_REQUESTED_MESSAGE}


@app.post("/api/auth/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    now = utcnow()
    reset = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(payload.token))
    )
    if reset is None or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(
            status_code=400,
            detail="El enlace no es válido o ya expiró. Solicita uno nuevo.",
        )
    user = db.get(User, reset.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="El enlace no es válido o ya expiró. Solicita uno nuevo.")
    # Marcar el enlace como usado de forma atómica: si dos peticiones llegan a la
    # vez con el mismo enlace, solo una actualiza la fila y la otra se rechaza.
    claimed = db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == reset.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="El enlace no es válido o ya expiró. Solicita uno nuevo.",
        )
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    revoke_sessions(db, user.id)
    # Abrir el enlace del correo también demuestra que el correo es suyo.
    if user.email_verified_at is None:
        user.email_verified_at = now
    # Quien recupera su cuenta no debe seguir bloqueado por intentos fallidos.
    identifiers = [value.lower() for value in (user.username, user.email) if value]
    db.execute(delete(LoginThrottle).where(LoginThrottle.identifier.in_(identifiers)))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Confirmación de correo ----------
EMAIL_VERIFICATION_HOURS = int(os.getenv("EMAIL_VERIFICATION_HOURS", "48"))
MAX_VERIFICATION_EMAILS = 3  # por usuario cada 15 minutos
VERIFICATION_SENT_MESSAGE = "Si la cuenta existe y no está confirmada, te enviamos un enlace nuevo."
INVALID_VERIFICATION = "El enlace de confirmación no es válido o ya expiró. Pide uno nuevo."


def email_verification_required() -> bool:
    """Con REQUIRE_EMAIL_VERIFICATION=true no se puede entrar sin confirmar el correo."""
    return os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").strip().lower() in ("1", "true", "yes", "si", "sí")


def queue_verification_email(db: Session, user: User, background_tasks: BackgroundTasks) -> None:
    """Crea un enlace de confirmación y programa el correo (con límite de envíos)."""
    if user.email_verified_at is not None:
        return
    now = utcnow()
    db.execute(delete(EmailVerificationToken).where(EmailVerificationToken.expires_at < now - timedelta(days=1)))
    recent = db.scalar(
        select(func.count(EmailVerificationToken.id)).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.created_at > now - timedelta(minutes=15),
        )
    )
    if recent >= MAX_VERIFICATION_EMAILS:
        db.commit()
        return
    token = secrets.token_urlsafe(32)
    db.add(EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_reset_token(token),
        created_at=now,
        expires_at=now + timedelta(hours=EMAIL_VERIFICATION_HOURS),
    ))
    db.commit()
    link = f"{frontend_url()}/?verify_token={token}"
    background_tasks.add_task(
        send_email,
        user.email,
        "Confirma tu correo de IndieDev Pipeline",
        f"Hola {display_name(user)}:\n\n"
        f"Abre este enlace para confirmar tu correo (vence en {EMAIL_VERIFICATION_HOURS} horas):\n\n"
        f"{link}\n\n"
        "Si no creaste una cuenta en IndieDev Pipeline, ignora este correo.",
    )


@app.post("/api/auth/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def confirm_email(payload: EmailVerificationConfirm, db: Session = Depends(get_db)):
    now = utcnow()
    record = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_reset_token(payload.token))
    )
    if record is None or record.used_at is not None or record.expires_at <= now:
        raise HTTPException(status_code=400, detail=INVALID_VERIFICATION)
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail=INVALID_VERIFICATION)
    claimed = db.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.id == record.id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=now)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail=INVALID_VERIFICATION)
    if user.email_verified_at is None:
        user.email_verified_at = now
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/auth/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
def resend_verification_email(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Reenvía el enlace. Responde lo mismo exista o no la cuenta."""
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None:
        queue_verification_email(db, user, background_tasks)
    return {"detail": VERIFICATION_SENT_MESSAGE}


# ---------- Mi cuenta ----------
@app.post("/api/auth/password", response_model=Token)
def change_password(
    payload: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cambia la contraseña. Cierra las demás sesiones y devuelve un token nuevo para esta."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="La contraseña nueva debe ser distinta a la actual")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.password_changed_at = utcnow()
    revoke_sessions(db, current_user.id)
    db.commit()
    return Token(access_token=start_session(db, current_user, request))


# ---------- Sesiones ----------
def revoke_sessions(db: Session, user_id: int, keep_id: int | None = None) -> None:
    """Cierra las sesiones abiertas del usuario (menos `keep_id`). No hace commit."""
    query = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if keep_id is not None:
        query = query.where(UserSession.id != keep_id)
    db.execute(query.values(revoked_at=utcnow()))


@app.get("/api/auth/sessions", response_model=list[SessionRead])
def list_my_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sesiones abiertas del usuario, la más reciente primero. `current` marca esta."""
    sessions = db.scalars(
        select(UserSession)
        .where(
            UserSession.user_id == current_user.id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utcnow(),
        )
        .order_by(UserSession.last_seen_at.desc(), UserSession.id.desc())
    ).all()
    current_id = getattr(request.state, "session_id", None)
    return [
        SessionRead(
            id=item.id,
            created_at=item.created_at,
            last_seen_at=item.last_seen_at,
            expires_at=item.expires_at,
            user_agent=item.user_agent,
            ip_address=item.ip_address,
            current=item.id == current_id,
        )
        for item in sessions
    ]


@app.delete("/api/auth/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_my_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    closed = db.execute(
        update(UserSession)
        .where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    ).rowcount
    if closed != 1:
        db.rollback()
        raise HTTPException(status_code=404, detail="La sesión no existe o ya se cerró")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.delete("/api/auth/sessions", status_code=status.HTTP_204_NO_CONTENT)
def revoke_other_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cierra todas las sesiones menos la actual."""
    revoke_sessions(db, current_user.id, keep_id=getattr(request.state, "session_id", None))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cierra la sesión de este token. El token deja de servir aunque no haya vencido."""
    session_id = getattr(request.state, "session_id", None)
    if session_id is not None:
        db.execute(
            update(UserSession)
            .where(UserSession.id == session_id, UserSession.user_id == current_user.id)
            .values(revoked_at=utcnow())
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def delete_user_account(db: Session, user: User) -> None:
    """Elimina al usuario y lo quita de todo. No borra estudios: si es dueño de alguno, falla.

    Lo que hizo (historial, comentarios, versiones subidas) se conserva sin autor.
    """
    owned = db.scalars(select(Tenant.name).where(Tenant.owner_user_id == user.id).order_by(Tenant.name)).all()
    if owned:
        raise HTTPException(
            status_code=409,
            detail="Primero elimina los estudios de los que es dueño: " + ", ".join(owned),
        )
    name = display_name(user)
    for tenant_id in db.scalars(select(Membership.tenant_id).where(Membership.user_id == user.id)).all():
        db.add(TenantActivity(
            tenant_id=tenant_id, user_id=None, actor_username=name[:50],
            action="account_deleted", summary=f"La cuenta de {name} fue eliminada",
        ))
    db.execute(update(Asset).where(Asset.created_by_user_id == user.id).values(created_by_user_id=None))
    db.execute(
        update(Asset).where(Asset.locked_by_user_id == user.id).values(locked_by_user_id=None, locked_at=None)
    )
    for model in (AssetHistory, AssetComment, TenantActivity):
        db.execute(update(model).where(model.user_id == user.id).values(user_id=None))
    db.execute(
        update(AssetFileVersion)
        .where(AssetFileVersion.uploaded_by_user_id == user.id)
        .values(uploaded_by_user_id=None)
    )
    for model in (AssetAssignment, Membership, Notification, PasswordResetToken, EmailVerificationToken, UserSession):
        db.execute(delete(model).where(model.user_id == user.id))
    identifiers = [value.lower() for value in (user.username, user.email) if value]
    db.execute(delete(LoginThrottle).where(LoginThrottle.identifier.in_(identifiers)))
    db.delete(user)
    db.commit()


@app.delete("/api/auth/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    payload: AccountDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña no es correcta")
    delete_user_account(db, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        log_activity(db, tenant.id, current_user, "tenant_created", f"Creó el estudio \"{tenant.name}\"")
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
    log_activity(
        db, tenant_id, current_user, "member_added",
        f"Agregó a {display_name(user)} como {payload.role.value}",
    )
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
    previous_role = target.role
    target.role = payload.role
    if previous_role != payload.role:
        log_activity(
            db, tenant_id, current_user, "member_role_changed",
            f"Cambió el rol de {display_name(db.get(User, user_id))}: "
            f"{previous_role.value} → {payload.role.value}",
        )
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
    log_activity(
        db, tenant_id, current_user, "member_removed",
        f"Quitó a {display_name(db.get(User, user_id))} del estudio",
    )
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
    log_activity(db, tenant_id, current_user, "project_created", f"Creó el proyecto \"{project.name}\"")
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
    log_activity(db, tenant_id, current_user, "asset_created", f"Creó la tarea \"{asset.original_name}\"")
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
    previous_status = asset.status
    if any(field in changes for field in ("category", "assignment_mode", "assigned_user_ids")):
        require_manager(membership, "cambiar el tipo o los asignados de una tarea")
    if "status" in changes and changes["status"] is not None:
        require_can_move(membership, asset.category, asset.status, changes["status"].value)
        # El tester revisa todas las tareas aunque no esté asignado; sus movimientos
        # ya quedan limitados por TESTER_TRANSITIONS en require_can_move.
        if (
            not is_manager(membership)
            and membership.role != MemberRole.TESTER
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

    # Solo avisa a los testers cuando la tarea realmente entra a revisión
    # (no si ya estaba en "review" y se reenvía el mismo estado).
    if asset.status != previous_status and asset.status == AssetStatus.REVIEW.value:
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


# ---------- Archivos y versiones ----------
# Vista previa: el backend lee el archivo y lo entrega directo. Así funciona con
# cualquier proveedor sin configurar CORS en el bucket.
PREVIEW_MAX_BYTES = int(os.getenv("PREVIEW_MAX_MB", "5")) * 1024 * 1024


def get_tenant_asset(db: Session, tenant_id: int, project_id: int, asset_id: int) -> Asset:
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


def latest_version(db: Session, asset: Asset) -> AssetFileVersion | None:
    return db.scalar(
        select(AssetFileVersion)
        .where(AssetFileVersion.asset_id == asset.id)
        .order_by(AssetFileVersion.version.desc())
        .limit(1)
    )


def get_version(db: Session, asset: Asset, version_id: int) -> AssetFileVersion:
    version = db.scalar(
        select(AssetFileVersion).where(
            AssetFileVersion.id == version_id, AssetFileVersion.asset_id == asset.id
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    return version


def current_file(db: Session, asset: Asset) -> tuple[str, str, str, str]:
    """(proveedor, ruta, nombre, tipo) del archivo actual del asset."""
    if asset.file_uploaded_at is None or asset.file_size is None:
        raise HTTPException(status_code=404, detail="Este asset todavía no tiene archivo")
    version = latest_version(db, asset)
    if version is not None:
        return version.storage_provider, version.storage_key, version.file_name, version.content_type
    # Asset con archivo de antes de que existieran las versiones.
    provider = getattr(asset.storage_provider, "value", asset.storage_provider)
    return provider, asset.storage_key, asset.original_name, asset.content_type or "application/octet-stream"


def serve_stored_file(provider: str, storage_key: str, file_name: str, content_type: str):
    """Descarga: archivo directo (local) o { url, expires_at } firmada (S3/Firebase)."""
    try:
        if provider == StorageProvider.LOCAL.value:
            path = local_file(storage_key)
            if path is None:
                raise HTTPException(status_code=404, detail="Este asset todavía no tiene archivo")
            return FileResponse(path, filename=file_name, media_type=content_type)
        if provider == StorageProvider.S3.value:
            return s3_download_url(storage_key)
        if provider == StorageProvider.FIREBASE.value:
            result = firebase_download_url(storage_key)
            if result is None:
                raise HTTPException(status_code=404, detail="Este asset todavía no tiene archivo")
            return result
        raise HTTPException(status_code=500, detail="Proveedor de almacenamiento no válido")
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("No se pudo descargar el archivo %s de %s", storage_key, provider)
        raise HTTPException(status_code=500, detail="No se pudo descargar el archivo") from error


def preview_stored_file(
    provider: str, storage_key: str, file_size: int, content_type: str, immutable: bool = False
) -> Response:
    """Contenido para la vista previa.

    La URL del archivo actual no cambia al subir otra versión, así que no se guarda
    en caché; la de una versión concreta nunca cambia y sí se puede guardar.
    """
    if file_size > PREVIEW_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo es muy grande para la vista previa (máximo {PREVIEW_MAX_BYTES // (1024 * 1024)} MB)",
        )
    try:
        content = read_stored_file(provider, storage_key, PREVIEW_MAX_BYTES)
    except Exception as error:
        logger.exception("No se pudo leer el archivo %s de %s", storage_key, provider)
        raise HTTPException(status_code=500, detail="No se pudo leer el archivo") from error
    if content is None:
        raise HTTPException(status_code=404, detail="Este asset todavía no tiene archivo")
    return Response(
        content=content,
        media_type=content_type,
        # nosniff + sandbox: un .html o .svg subido no puede ejecutar código en el dominio de la API.
        headers={
            "Cache-Control": "private, max-age=86400, immutable" if immutable else "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'",
        },
    )


def save_to_provider(provider: str, storage_key: str, file, content_type: str) -> None:
    if provider == StorageProvider.LOCAL.value:
        save_local(storage_key, file)
    elif provider == StorageProvider.S3.value:
        save_s3(storage_key, file, content_type)
    elif provider == StorageProvider.FIREBASE.value:
        save_firebase(storage_key, file, content_type)
    else:
        raise HTTPException(status_code=500, detail="Proveedor de almacenamiento no válido")


def require_lock_for_file_change(membership: Membership, asset: Asset, user: User, action: str) -> None:
    require_can_lock(membership, asset.category)
    if asset.locked_by_user_id != user.id:
        raise HTTPException(status_code=409, detail=f"Bloquea el archivo antes de {action}")


def apply_version_to_asset(asset: Asset, version: AssetFileVersion) -> None:
    asset.file_size = version.file_size
    asset.content_type = version.content_type[:120]
    asset.file_uploaded_at = version.uploaded_at


@app.post(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file",
    response_model=AssetRead,
)
def upload_asset_file(  # sin async: la subida a S3/Firebase es bloqueante y así corre en un hilo aparte
    tenant_id: int,
    project_id: int,
    asset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    asset = get_tenant_asset(db, tenant_id, project_id, asset_id)
    require_lock_for_file_change(membership, asset, current_user, "subir una nueva versión")

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

    content_type = (file.content_type or "application/octet-stream")[:120]
    file_name = (file.filename or asset.original_name)[:255]
    previous = latest_version(db, asset)
    number = previous.version + 1 if previous else 1
    provider = getattr(asset.storage_provider, "value", asset.storage_provider)
    storage_key = version_storage_key(asset.storage_key, number)
    try:
        save_to_provider(provider, storage_key, file.file, content_type)
    except HTTPException:
        raise
    except Exception as error:
        # Sin este log el 500 no dice nada: casi siempre es configuración del proveedor
        # (ASSET_STORAGE_PROVIDER, credenciales o bucket) y la causa real queda en los logs.
        logger.exception("No se pudo guardar el archivo %s en %s", storage_key, provider)
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo") from error

    version = AssetFileVersion(
        tenant_id=tenant_id,
        asset_id=asset.id,
        version=number,
        storage_key=storage_key,
        storage_provider=provider,
        file_name=file_name,
        file_size=file_size,
        content_type=content_type,
        uploaded_by_user_id=current_user.id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(version)
    apply_version_to_asset(asset, version)
    record_asset_change(
        db,
        asset,
        current_user,
        "file_uploaded",
        new_value=f"v{number}: {file_name} ({format_file_size(file_size)})",
    )
    try:
        db.commit()
    except IntegrityError as error:
        # Dos subidas simultáneas calcularon el mismo número de versión.
        db.rollback()
        remove_stored_files([(provider, storage_key)])
        raise HTTPException(status_code=409, detail="Otra subida terminó al mismo tiempo; intenta de nuevo") from error
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
    asset = get_tenant_asset(db, tenant_id, project_id, asset_id)
    return serve_stored_file(*current_file(db, asset))


@app.get("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file/preview")
def preview_asset_file(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = get_tenant_asset(db, tenant_id, project_id, asset_id)
    provider, storage_key, _, content_type = current_file(db, asset)
    return preview_stored_file(provider, storage_key, asset.file_size, content_type)


@app.get(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/versions",
    response_model=list[AssetFileVersionRead],
)
def list_asset_versions(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = get_tenant_asset(db, tenant_id, project_id, asset_id)
    return db.scalars(
        select(AssetFileVersion)
        .where(AssetFileVersion.asset_id == asset.id)
        .order_by(AssetFileVersion.version.desc())
    ).all()


@app.get("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/versions/{version_id}/file")
def download_asset_version(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = get_tenant_asset(db, tenant_id, project_id, asset_id)
    version = get_version(db, asset, version_id)
    return serve_stored_file(version.storage_provider, version.storage_key, version.file_name, version.content_type)


@app.get("/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/versions/{version_id}/preview")
def preview_asset_version(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant_membership(db, tenant_id, current_user.id)
    asset = get_tenant_asset(db, tenant_id, project_id, asset_id)
    version = get_version(db, asset, version_id)
    return preview_stored_file(
        version.storage_provider, version.storage_key, version.file_size, version.content_type, immutable=True
    )


@app.post(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/versions/{version_id}/restore",
    response_model=AssetRead,
)
def restore_asset_version(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Vuelve a una versión anterior creando una versión nueva con el mismo archivo."""
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    asset = get_tenant_asset(db, tenant_id, project_id, asset_id)
    require_lock_for_file_change(membership, asset, current_user, "restaurar una versión")
    source = get_version(db, asset, version_id)
    previous = latest_version(db, asset)
    if previous is not None and previous.id == source.id:
        raise HTTPException(status_code=409, detail="Esa ya es la versión actual")
    number = previous.version + 1
    version = AssetFileVersion(
        tenant_id=tenant_id,
        asset_id=asset.id,
        version=number,
        storage_key=source.storage_key,
        storage_provider=source.storage_provider,
        file_name=source.file_name,
        file_size=source.file_size,
        content_type=source.content_type,
        uploaded_by_user_id=current_user.id,
        restored_from_version=source.version,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(version)
    apply_version_to_asset(asset, version)
    record_asset_change(
        db, asset, current_user, "file_restored",
        previous_value=f"v{previous.version}", new_value=f"v{number} (copia de v{source.version})",
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Otra subida terminó al mismo tiempo; intenta de nuevo") from error
    db.refresh(asset)
    return asset


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
    log_activity(
        db, tenant_id, current_user, "github_connected",
        f"Conectó el proyecto \"{project.name}\" con GitHub ({project.github_repo})",
    )
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

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="El cuerpo del webhook no es JSON válido")
    commits = payload.get("commits") if isinstance(payload, dict) else None
    saved: set[tuple[int, str]] = set()
    for commit in commits if isinstance(commits, list) else []:
        if not isinstance(commit, dict):
            continue
        message = commit.get("message") or ""
        sha = str(commit.get("id") or "")[:40]
        if not sha:
            continue
        # Un mensaje puede mencionar la misma tarea varias veces ("#12 ... #12").
        for asset_id in dict.fromkeys(int(number) for number in re.findall(r"#(\d+)", message)):
            if (asset_id, sha) in saved:
                continue
            asset = db.scalar(select(Asset).where(
                Asset.id == asset_id,
                Asset.tenant_id == project.tenant_id,
                Asset.project_id == project.id,
            ))
            if asset is None:
                continue
            # GitHub reintenta entregas; un commit ya guardado no se vuelve a insertar.
            if db.scalar(select(AssetCommit.id).where(AssetCommit.asset_id == asset.id, AssetCommit.sha == sha)):
                continue
            timestamp_text = commit.get("timestamp")
            try:
                committed_at = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                committed_at = datetime.now(timezone.utc)
            author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
            db.add(AssetCommit(
                tenant_id=project.tenant_id,
                asset_id=asset.id,
                sha=sha,
                message=message,
                author_name=str(author.get("name") or author.get("username") or "Desconocido")[:120],
                url=str(commit.get("url") or "")[:500],
                committed_at=committed_at,
            ))
            saved.add((asset_id, sha))
    try:
        db.commit()
    except IntegrityError:
        # Dos entregas simultáneas del mismo push: la otra ya guardó los commits.
        db.rollback()
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
    comment = db.scalar(
        select(AssetComment)
        .join(Asset, Asset.id == AssetComment.asset_id)
        .where(
            AssetComment.id == comment_id,
            AssetComment.tenant_id == tenant_id,
            AssetComment.asset_id == asset_id,
            Asset.project_id == project_id,
        )
    )
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


# =====================================================================
# Administración del estudio: editar/eliminar estudio, proyectos y tareas,
# y bitácora de actividad. Solo dueño/admin (y borrar el estudio, solo el dueño).
# =====================================================================


@app.patch("/api/tenants/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "editar el estudio")
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")

    changes = []
    if payload.name is not None and payload.name.strip() and payload.name.strip() != tenant.name:
        changes.append(f"nombre \"{tenant.name}\" → \"{payload.name.strip()}\"")
        tenant.name = payload.name.strip()
    if payload.slug is not None and payload.slug != tenant.slug:
        changes.append(f"identificador {tenant.slug} → {payload.slug}")
        tenant.slug = payload.slug
    if changes:
        log_activity(db, tenant_id, current_user, "tenant_updated", "Cambió " + " y ".join(changes))
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ese identificador ya lo usa otro estudio") from error
    db.refresh(tenant)
    return tenant


@app.delete("/api/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: int,
    confirm: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Elimina el estudio y, por la cascada de llaves foráneas, todos sus datos.

    Por seguridad exige `?confirm=<identificador del estudio>`.
    """
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    if membership.role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Solo el dueño puede eliminar el estudio")
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")
    if confirm != tenant.slug:
        raise HTTPException(
            status_code=400,
            detail="Para confirmar, escribe exactamente el identificador del estudio",
        )
    files = stored_files(db, Asset.tenant_id == tenant_id)
    db.delete(tenant)
    db.commit()
    remove_stored_files(files)


@app.get("/api/tenants/{tenant_id}/activity", response_model=list[TenantActivityRead])
def list_tenant_activity(
    tenant_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "ver la bitácora del estudio")
    limit = min(max(limit, 1), 200)
    return db.scalars(
        select(TenantActivity)
        .where(TenantActivity.tenant_id == tenant_id)
        .order_by(TenantActivity.created_at.desc(), TenantActivity.id.desc())
        .limit(limit)
    ).all()


@app.patch("/api/tenants/{tenant_id}/projects/{project_id}", response_model=ProjectRead)
def update_project(
    tenant_id: int,
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "editar proyectos")
    project = get_project(db, tenant_id, project_id)
    previous_name = project.name
    fields = payload.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        project.name = fields["name"].strip()
    if "description" in fields:
        project.description = (fields["description"] or "").strip() or None
    summary = (
        f"Renombró el proyecto \"{previous_name}\" a \"{project.name}\""
        if project.name != previous_name
        else f"Editó el proyecto \"{project.name}\""
    )
    log_activity(db, tenant_id, current_user, "project_updated", summary)
    db.commit()
    db.refresh(project)
    return project


@app.delete("/api/tenants/{tenant_id}/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    tenant_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "eliminar proyectos")
    project = get_project(db, tenant_id, project_id)
    files = stored_files(db, Asset.tenant_id == tenant_id, Asset.project_id == project_id)
    log_activity(
        db, tenant_id, current_user, "project_deleted",
        f"Eliminó el proyecto \"{project.name}\" con todas sus tareas y builds",
    )
    db.delete(project)
    db.commit()
    remove_stored_files(files)


@app.delete(
    "/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_asset(
    tenant_id: int,
    project_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = require_tenant_membership(db, tenant_id, current_user.id)
    require_manager(membership, "eliminar tareas")
    get_project(db, tenant_id, project_id)
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id, Asset.tenant_id == tenant_id, Asset.project_id == project_id
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    files = stored_files(db, Asset.id == asset.id)
    log_activity(db, tenant_id, current_user, "asset_deleted", f"Eliminó la tarea \"{asset.original_name}\"")
    db.delete(asset)
    db.commit()
    remove_stored_files(files)


# =====================================================================
# Panel de administración de la plataforma (SUPERADMIN_EMAILS).
# =====================================================================


@app.get("/api/admin/users", response_model=list[AdminUserRead])
def admin_list_users(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    users = db.scalars(select(User).order_by(User.id)).all()
    rows = db.execute(
        select(Membership.user_id, Tenant.name, Tenant.owner_user_id)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .order_by(Tenant.name)
    ).all()
    studios: dict[int, list[str]] = {}
    owned: dict[int, list[str]] = {}
    for user_id, tenant_name, owner_id in rows:
        studios.setdefault(user_id, []).append(tenant_name)
        if owner_id == user_id:
            owned.setdefault(user_id, []).append(tenant_name)
    return [
        AdminUserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            email_verified=user.email_verified_at is not None,
            is_superadmin=is_superadmin(user),
            studios=studios.get(user.id, []),
            owned_studios=owned.get(user.id, []),
        )
        for user in users
    ]


@app.get("/api/admin/tenants", response_model=list[AdminTenantRead])
def admin_list_tenants(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    def counts(column):
        return dict(db.execute(select(column, func.count()).group_by(column)).all())

    members = counts(Membership.tenant_id)
    projects = counts(Project.tenant_id)
    assets = counts(Asset.tenant_id)
    owners = dict(db.execute(select(User.id, User.username)).all())
    return [
        AdminTenantRead(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            owner_username=owners.get(tenant.owner_user_id),
            member_count=members.get(tenant.id, 0),
            project_count=projects.get(tenant.id, 0),
            asset_count=assets.get(tenant.id, 0),
            created_at=tenant.created_at,
        )
        for tenant in db.scalars(select(Tenant).order_by(Tenant.id)).all()
    ]


@app.delete("/api/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_superadmin)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Para eliminar tu propia cuenta usa Mi cuenta")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    delete_user_account(db, user)
    logger.warning("Superadmin %s eliminó al usuario %s (id %s)", admin.email, user.email, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.delete("/api/admin/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_tenant(
    tenant_id: int, db: Session = Depends(get_db), admin: User = Depends(require_superadmin)
):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Estudio no encontrado")
    files = stored_files(db, Asset.tenant_id == tenant_id)
    db.delete(tenant)
    db.commit()
    remove_stored_files(files)
    logger.warning("Superadmin %s eliminó el estudio %s (id %s)", admin.email, tenant.slug, tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
