"""Permisos por rol (RBAC) dentro de un estudio.

Resumen:
- owner (dueño) y admin: administran el estudio. Crean proyectos y tareas,
  asignan integrantes, cambian cualquier campo y mueven cualquier tarea.
  Solo el dueño puede nombrar o quitar admins.
- developer: mueve y bloquea tareas de código; registra builds.
- artist: mueve y bloquea tareas de arte.
- tester: revisa. Solo puede pasar tareas de Revisión a Terminado,
  regresarlas de Revisión a En progreso o reabrir una terminada a Revisión.

El frontend replica estas reglas en Frontend/src/utils/permissions.js
para ocultar botones; la validación real es esta.
"""

from fastapi import HTTPException, status

from .models import AssetCategory, AssetStatus, MemberRole, Membership

MANAGERS = {MemberRole.OWNER, MemberRole.ADMIN}
CATEGORY_BY_ROLE = {
    MemberRole.DEVELOPER: AssetCategory.CODE.value,
    MemberRole.ARTIST: AssetCategory.ART.value,
}
TESTER_TRANSITIONS = {
    (AssetStatus.REVIEW.value, AssetStatus.DONE.value),
    (AssetStatus.REVIEW.value, AssetStatus.IN_PROGRESS.value),
    (AssetStatus.DONE.value, AssetStatus.REVIEW.value),
}
BUILD_ROLES = MANAGERS | {MemberRole.DEVELOPER}


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def is_manager(membership: Membership) -> bool:
    return membership.role in MANAGERS


def require_manager(membership: Membership, action: str = "hacer esto") -> None:
    if not is_manager(membership):
        raise _forbidden(f"Solo el dueño o un admin pueden {action}")


def require_build_role(membership: Membership) -> None:
    if membership.role not in BUILD_ROLES:
        raise _forbidden("Solo dueño, admin o developers pueden registrar builds")


def require_can_move(membership: Membership, category: str, old_status: str, new_status: str) -> None:
    role = membership.role
    if role in MANAGERS:
        return
    if role == MemberRole.TESTER:
        if (old_status, new_status) not in TESTER_TRANSITIONS:
            raise _forbidden(
                "Como tester solo puedes aprobar (Revisión → Terminado), regresar a En progreso "
                "o reabrir una tarea terminada"
            )
        return
    if CATEGORY_BY_ROLE.get(role) != category:
        raise _forbidden(f"Tu rol ({role.value}) no puede mover tareas de tipo {category}")


def require_can_lock(membership: Membership, category: str) -> None:
    role = membership.role
    if role in MANAGERS or CATEGORY_BY_ROLE.get(role) == category:
        return
    raise _forbidden(f"Tu rol ({role.value}) no puede bloquear archivos de tipo {category}")


def require_can_manage_member(actor: Membership, target: Membership | None, new_role: MemberRole | None) -> None:
    """Valida que `actor` pueda agregar/cambiar/quitar a `target` (None = alta nueva)."""
    require_manager(actor, "administrar integrantes")
    if new_role == MemberRole.OWNER:
        raise _forbidden("El estudio solo tiene un dueño; no se puede asignar ese rol")
    if target is not None and target.role == MemberRole.OWNER:
        raise _forbidden("No se puede cambiar ni quitar al dueño del estudio")
    touches_admin = new_role == MemberRole.ADMIN or (target is not None and target.role == MemberRole.ADMIN)
    if touches_admin and actor.role != MemberRole.OWNER:
        raise _forbidden("Solo el dueño puede nombrar o quitar admins")
