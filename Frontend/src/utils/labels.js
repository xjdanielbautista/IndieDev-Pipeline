// Etiquetas en español y utilidades de formato compartidas por la interfaz.

export const STATUSES = [
  { id: "backlog", label: "Backlog", color: "text-gray-400", dot: "bg-gray-400" },
  { id: "in_progress", label: "En progreso", color: "text-[#00F0FF]", dot: "bg-[#00F0FF]" },
  { id: "review", label: "Revisión", color: "text-yellow-400", dot: "bg-yellow-400" },
  { id: "done", label: "Terminado", color: "text-[#00FF66]", dot: "bg-[#00FF66]" },
];

export const CATEGORIES = {
  code: { label: "Código", color: "#00F0FF" },
  art: { label: "Arte", color: "#FF0055" },
};

export const ROLES = {
  owner: "Dueño",
  admin: "Admin",
  developer: "Developer",
  artist: "Artista",
  tester: "Tester",
};

export const BUILD_STATUSES = {
  pending: { label: "Pendiente", classes: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" },
  success: { label: "Exitoso", classes: "bg-[#00FF66]/15 text-[#00FF66] border-[#00FF66]/30" },
  failed: { label: "Fallido", classes: "bg-[#FF3D00]/15 text-[#FF3D00] border-[#FF3D00]/30" },
};

const ASSIGNMENT_MODES = { open: "Abierta", restricted: "Restringida" };

export function statusLabel(id) {
  return STATUSES.find((s) => s.id === id)?.label ?? id;
}

// Traduce un valor guardado en el historial según el campo que cambió.
function valueLabel(action, value) {
  if (value === null || value === undefined || value === "") return "—";
  if (action === "status_changed") return statusLabel(value);
  if (action === "category_changed") return CATEGORIES[value]?.label ?? value;
  if (action === "assignment_mode_changed") return ASSIGNMENT_MODES[value] ?? value;
  return value;
}

// Convierte una entrada del historial del backend en una frase legible.
export function describeChange(entry) {
  const prev = valueLabel(entry.action, entry.previous_value);
  const next = valueLabel(entry.action, entry.new_value);
  switch (entry.action) {
    case "created":
      return "creó la tarea";
    case "assigned":
      return `asignó a ${entry.new_value}`;
    case "status_changed":
      return `movió de ${prev} a ${next}`;
    case "category_changed":
      return `cambió el tipo de ${prev} a ${next}`;
    case "assignment_mode_changed":
      return `cambió la asignación de ${prev} a ${next}`;
    case "assignments_changed": {
      const parts = [];
      if (entry.new_value) parts.push(`agregó a ${entry.new_value}`);
      if (entry.previous_value) parts.push(`quitó a ${entry.previous_value}`);
      return parts.join(" y ") || "cambió los asignados";
    }
    case "locked":
      return "bloqueó el archivo";
    case "unlocked":
      return entry.previous_value && entry.previous_value !== entry.actor_username
        ? `liberó el bloqueo de ${entry.previous_value}`
        : "liberó el archivo";
    case "file_uploaded":
      return `subió una nueva versión${entry.new_value ? `: ${entry.new_value}` : ""}`;
    default:
      return entry.action;
  }
}

// El backend guarda fechas sin zona horaria (en UTC). Las interpretamos como UTC
// y las mostramos en la hora local del navegador.
export function parseDate(value) {
  if (!value) return null;
  const hasZone = /[zZ]|[+-]\d\d:?\d\d$/.test(value);
  return new Date(hasZone ? value : `${value.replace(" ", "T")}Z`);
}

export function formatDateTime(value) {
  const date = parseDate(value);
  if (!date) return "";
  return date.toLocaleString("es-MX", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeAgo(value) {
  const date = parseDate(value);
  if (!date) return "";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "hace un momento";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.round(hours / 24);
  return `hace ${days} d`;
}

export function slugify(text) {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export function initials(name = "") {
  return (
    name
      .split(/[\s_.-]+/)
      .filter(Boolean)
      .map((w) => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "?"
  );
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}
