import { apiFetch } from "./client";

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
