import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserSession


SECRET_KEY = os.getenv("SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def _secret_key() -> str:
    if len(SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY must be set to a random value of at least 32 characters")
    return SECRET_KEY


def validate_secret_key() -> None:
    _secret_key()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str | None) -> bool:
    if hashed_password is None:
        return False
    return password_hash.verify(password, hashed_password)


# Cada cuánto se actualiza "última actividad" de una sesión (evita escribir en cada petición).
SESSION_TOUCH_SECONDS = 60


def create_access_token(user_id: int, session_key: str | None = None) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    claims = {"sub": str(user_id), "iat": issued_at.timestamp(), "exp": expires_at}
    if session_key is not None:
        claims["sid"] = session_key
    return jwt.encode(claims, _secret_key(), algorithm=JWT_ALGORITHM)


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # En Render el backend está detrás de un proxy: la IP real es la primera de X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    return request.client.host[:64] if request.client else None


def start_session(db: Session, user: User, request: Request | None = None) -> str:
    """Abre una sesión nueva y devuelve su token. Hace commit."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Limpieza: las sesiones vencidas o cerradas de este usuario ya no sirven.
    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        (UserSession.expires_at < now) | UserSession.revoked_at.is_not(None),
    ).delete(synchronize_session=False)
    session_key = secrets.token_hex(32)
    user_agent = request.headers.get("user-agent") if request is not None else None
    db.add(UserSession(
        user_id=user.id,
        session_key=session_key,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        user_agent=user_agent[:255] if user_agent else None,
        ip_address=_client_ip(request),
    ))
    db.commit()
    return create_access_token(user.id, session_key)


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[JWT_ALGORITHM])
        subject = payload.get("sub")
        user_id = int(subject)
    except (InvalidTokenError, TypeError, ValueError, RuntimeError) as error:
        raise credentials_error from error

    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    # Tras cambiar la contraseña, las sesiones abiertas antes de ese momento se cierran.
    if user.password_changed_at is not None:
        changed_at = user.password_changed_at.replace(tzinfo=timezone.utc).timestamp()
        issued_at = payload.get("iat")
        if not isinstance(issued_at, (int, float)) or issued_at < changed_at:
            raise credentials_error

    # Los tokens con "sid" pertenecen a una sesión que se puede cerrar. Los que no lo
    # tienen (emitidos antes de esta versión) siguen valiendo hasta que venzan.
    request.state.session_id = None
    session_key = payload.get("sid")
    if session_key is not None:
        session = db.query(UserSession).filter(UserSession.session_key == str(session_key)).first()
        if session is None or session.user_id != user.id or session.revoked_at is not None:
            raise credentials_error
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if (now - session.last_seen_at).total_seconds() > SESSION_TOUCH_SECONDS:
            session.last_seen_at = now
            db.commit()
        request.state.session_id = session.id
    return user
