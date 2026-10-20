import { API_BASE_URL } from "../config/api";

// Cliente HTTP central del frontend.
// Guarda el token JWT que devuelve /api/auth/token y lo agrega como
// "Authorization: Bearer <token>" en cada petición a rutas privadas.

const TOKEN_KEY = "indiedev_token";

// Evento que se dispara cuando el token expira o el backend lo rechaza (401).
// App.jsx lo escucha para regresar a la pantalla de login.
export const AUTH_EXPIRED_EVENT = "indiedev:auth-expired";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Si el navegador bloquea localStorage, la sesión dura solo mientras la pestaña esté abierta.
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nada que limpiar.
  }
}

// Lee la fecha de expiración (campo "exp") del JWT, en milisegundos.
// Devuelve null si el token no se puede leer.
export function getTokenExpiration(token) {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(payload));
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

export function isTokenValid(token) {
  if (!token) return false;
  const exp = getTokenExpiration(token);
  return exp === null || exp > Date.now();
}

// Error con el mensaje que manda el backend en "detail".
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function detailToMessage(detail, status) {
  if (!detail) return `Error ${status}`;
  if (typeof detail === "string") return detail;
  // Errores de validación de FastAPI (422): lista de { loc, msg }
  if (Array.isArray(detail)) {
    return detail.map((d) => `${d.loc?.at(-1) ?? "campo"}: ${d.msg}`).join("\n");
  }
  return JSON.stringify(detail);
}

// fetch con el token incluido. Uso:
//   apiFetch("/api/tenants", { method: "POST", body: { name, slug } })
// - Si body es un objeto, se manda como JSON.
// - Si body es URLSearchParams/FormData, se manda tal cual.
// - Pasa auth: false para rutas públicas (registro, login).
export async function apiFetch(path, { method = "GET", body, auth = true, headers = {} } = {}) {
  const finalHeaders = { ...headers };
  let finalBody = body;

  if (body !== undefined && !(body instanceof URLSearchParams) && !(body instanceof FormData)) {
    finalHeaders["Content-Type"] = "application/json";
    finalBody = JSON.stringify(body);
  }

  if (auth) {
    const token = getToken();
    if (!isTokenValid(token)) {
      clearToken();
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
      throw new ApiError("Tu sesión expiró, vuelve a iniciar sesión", 401);
    }
    finalHeaders.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: finalBody,
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar con el backend. Revisa que uvicorn esté corriendo y si su terminal muestra un error (Traceback).",
      0,
    );
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401 && auth) {
      clearToken();
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(detailToMessage(data?.detail, response.status), response.status);
  }

  return data;
}

// true si el error significa que la ruta todavía no existe en el backend
// (FastAPI responde 404 "Not Found" o 405 para rutas no implementadas).
// Ver docs/PENDIENTES_BACKEND.md.
export function isNotImplemented(error) {
  return error?.status === 405 || (error?.status === 404 && error?.message === "Not Found");
}
