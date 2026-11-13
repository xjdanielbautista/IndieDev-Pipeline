import os
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def normalize_database_url(url: str) -> str:
    """Ajusta la URL para usar los drivers instalados (psycopg 3 y PyMySQL).

    Render y otros proveedores entregan `postgres://...` o `postgresql://...`; SQLAlchemy
    no acepta el primero y con el segundo podría buscar psycopg2, que no está instalado.
    """
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    if url.startswith("mysql://"):
        return "mysql+pymysql://" + url[len("mysql://"):]
    return url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL") or "sqlite:///./indiedev.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# pool_pre_ping evita errores con conexiones que la nube cerró por inactividad.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    # SQLite ignora ON DELETE CASCADE si no se activa esta opción en cada conexión.
    # MySQL y PostgreSQL ya respetan las llaves foráneas por defecto.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()