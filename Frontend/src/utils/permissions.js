// Reglas de permisos por rol. Son una copia de Backend/app/permissions.py:
// aquí solo sirven para ocultar o desactivar botones; el backend es quien valida.

const MANAGERS = ["owner", "admin"];
const CATEGORY_BY_ROLE = { developer: "code", artist: "art" };
const TESTER_TRANSITIONS = [
  ["review", "done"],
  ["review", "in_progress"],
  ["done", "review"],
];

export const ROLE_INFO = {
  owner: { label: "Dueño", description: "Control total del estudio. Nombra admins." },
  admin: { label: "Admin", description: "Crea proyectos y tareas, asigna trabajo y administra integrantes." },
  developer: { label: "Developer", description: "Mueve y bloquea tareas de código. Registra builds." },
  artist: { label: "Artista", description: "Mueve y bloquea tareas de arte." },
  tester: { label: "Tester", description: "Aprueba tareas en Revisión o las regresa a En progreso." },
};

export const isManager = (role) => MANAGERS.includes(role);

export const canBuild = (role) => isManager(role) || role === "developer";

export function canMove(role, asset, toStatus, userId) {
  if (!role || asset.status === toStatus) return false;
  if (isManager(role)) return true;
  if (asset.assignment_mode === "restricted" && !asset.assigned_user_ids.includes(userId)) return false;
  if (role === "tester") return TESTER_TRANSITIONS.some(([from, to]) => from === asset.status && to === toStatus);
  return CATEGORY_BY_ROLE[role] === asset.category;
}

export const canLock = (role, category) => isManager(role) || CATEGORY_BY_ROLE[role] === category;

// Roles que `actorRole` puede asignar a otros integrantes.
export function assignableRoles(actorRole) {
  if (actorRole === "owner") return ["admin", "developer", "artist", "tester"];
  if (actorRole === "admin") return ["developer", "artist", "tester"];
  return [];
}

// ¿Puede `actorRole` cambiar o quitar a alguien con `targetRole`?
export function canManageMember(actorRole, targetRole) {
  if (!isManager(actorRole) || targetRole === "owner") return false;
  if (targetRole === "admin") return actorRole === "owner";
  return true;
}
