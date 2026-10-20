import { API_BASE_URL } from "../config/api";
import { ApiError, apiFetch, getToken } from "./client";

// Llamadas al backend para estudios, proyectos, tareas (assets) y builds.
// Todas usan el token de la sesión mediante apiFetch.

const base = (tenantId, projectId) => `/api/tenants/${tenantId}/projects/${projectId}`;

// ---- Estudios ----
export const listMyTenants = () => apiFetch("/api/tenants");
export const createTenant = (name, slug) =>
  apiFetch("/api/tenants", { method: "POST", body: { name, slug } });
export const listMembers = (tenantId) => apiFetch(`/api/tenants/${tenantId}/members`);

// ---- Proyectos ----
export const listProjects = (tenantId) => apiFetch(`/api/tenants/${tenantId}/projects`);
export const createProject = (tenantId, name, description) =>
  apiFetch(`/api/tenants/${tenantId}/projects`, {
    method: "POST",
    body: { name, description: description || null },
  });

// ---- Tareas del tablero (assets en el backend) ----
export const listAssets = (tenantId, projectId) => apiFetch(`${base(tenantId, projectId)}/assets`);

export const createAsset = (tenantId, projectId, data) =>
  apiFetch(`${base(tenantId, projectId)}/assets`, { method: "POST", body: data });

export const updateAsset = (tenantId, projectId, assetId, changes) =>
  apiFetch(`${base(tenantId, projectId)}/assets/${assetId}`, { method: "PATCH", body: changes });

export const lockAsset = (tenantId, projectId, assetId) =>
  apiFetch(`${base(tenantId, projectId)}/assets/${assetId}/lock`, { method: "PATCH", body: {} });

export const unlockAsset = (tenantId, projectId, assetId) =>
  apiFetch(`${base(tenantId, projectId)}/assets/${assetId}/lock`, { method: "DELETE" });

export const getAssetHistory = (tenantId, projectId, assetId) =>
  apiFetch(`${base(tenantId, projectId)}/assets/${assetId}/history`);

// ---- Builds ----
export const listBuilds = (tenantId, projectId) => apiFetch(`${base(tenantId, projectId)}/builds`);
export const createBuild = (tenantId, projectId, data) =>
  apiFetch(`${base(tenantId, projectId)}/builds`, { method: "POST", body: data });

// ---- Integrantes y roles (solo dueño/admin) ----
export const addMember = (tenantId, identifier, role) =>
  apiFetch(`/api/tenants/${tenantId}/members`, { method: "POST", body: { identifier, role } });
export const updateMemberRole = (tenantId, userId, role) =>
  apiFetch(`/api/tenants/${tenantId}/members/${userId}`, { method: "PATCH", body: { role } });
export const removeMember = (tenantId, userId) =>
  apiFetch(`/api/tenants/${tenantId}/members/${userId}`, { method: "DELETE" });

// ---- Funciones pendientes del backend (ver docs/PENDIENTES_BACKEND.md) ----
// Mientras no existan, responden 404 "Not Found" y la interfaz muestra "Próximamente".

const assetPath = (tenantId, projectId, assetId) => `${base(tenantId, projectId)}/assets/${assetId}`;

// Comentarios
export const listComments = (tenantId, projectId, assetId) =>
  apiFetch(`${assetPath(tenantId, projectId, assetId)}/comments`);
export const addComment = (tenantId, projectId, assetId, body) =>
  apiFetch(`${assetPath(tenantId, projectId, assetId)}/comments`, { method: "POST", body: { body } });
export const deleteComment = (tenantId, projectId, assetId, commentId) =>
  apiFetch(`${assetPath(tenantId, projectId, assetId)}/comments/${commentId}`, { method: "DELETE" });

// Commits de GitHub
export const listCommits = (tenantId, projectId, assetId) =>
  apiFetch(`${assetPath(tenantId, projectId, assetId)}/commits`);
export const connectGithub = (tenantId, projectId, githubRepo) =>
  apiFetch(`${base(tenantId, projectId)}/github`, { method: "POST", body: { github_repo: githubRepo } });

// Archivos
export function uploadAssetFile(tenantId, projectId, assetId, file) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch(`${assetPath(tenantId, projectId, assetId)}/file`, { method: "POST", body: form });
}

// Descarga: con Firebase/S3 el backend responde { url }; con el proveedor local, el archivo directo.
export async function downloadAssetFile(tenantId, projectId, assetId, fileName) {
  const token = getToken();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${assetPath(tenantId, projectId, assetId)}/file`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new ApiError("No se pudo conectar con el backend", 0);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(data?.detail || `Error ${response.status}`, response.status);
  }
  if ((response.headers.get("content-type") || "").includes("application/json")) {
    const { url } = await response.json();
    window.open(url, "_blank", "noopener");
    return;
  }
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(link.href);
}

// Notificaciones
export const listNotifications = () => apiFetch("/api/notifications?limit=30");
export const markNotificationsRead = (ids) =>
  apiFetch("/api/notifications/read", { method: "POST", body: ids === "all" ? { all: true } : { ids } });
