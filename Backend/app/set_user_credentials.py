import re
from getpass import getpass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .database import SessionLocal
from .models import User
from .security import hash_password


USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,50}$")


def main() -> None:
    email = input("Correo del usuario existente: ").strip().lower()
    username = input("Nuevo nombre de usuario: ").strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise SystemExit("El nombre debe tener 3-50 caracteres: letras, números, punto, guion o guion bajo.")

    password = getpass("Nueva contraseña (mínimo 8 caracteres): ")
    confirmation = getpass("Confirma la contraseña: ")
    if len(password) < 8 or len(password) > 128:
        raise SystemExit("La contraseña debe tener entre 8 y 128 caracteres.")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            raise SystemExit("No existe un usuario con ese correo.")
        if user.password_hash is not None:
            raise SystemExit("Ese usuario ya tiene credenciales configuradas.")
        username_taken = db.scalar(
            select(User.id).where(func.lower(User.username) == username)
        )
        if username_taken is not None:
            raise SystemExit("Ese nombre de usuario ya está en uso.")

        user.username = username
        user.password_hash = hash_password(password)
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise SystemExit("El correo o nombre de usuario ya está registrado.") from error

    print("Credenciales configuradas. Ya puedes iniciar sesión con el nombre o correo.")


if __name__ == "__main__":
    main()
