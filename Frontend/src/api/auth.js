import { API_BASE_URL } from "../config/api";
import { apiFetch, clearToken, getToken, setToken } from "./client";

// POST /api/auth/register  (JSON)
// { username, email, password } -> { id, username, email }
export function register({ username, email, password }) {
  return apiFetch("/api/auth/register", {
    method: "POST",
    auth: false,
    body: { username, email, password },
  });
}

// POST /api/auth/token  (formulario x-www-form-urlencoded, estándar OAuth2)
// En "username" puede ir el nombre de usuario o el correo.
// Respuesta: { access_token, token_type: "bearer" }  -> dura 30 min
export async function login(identifier, password) {
  const form = new URLSearchParams();
  form.append("username", identifier);
  form.append("password", password);

  const data = await apiFetch("/api/auth/token", {
    method: "POST",
    auth: false,
    body: form,
  });
  setToken(data.access_token);
  return data;
}

// GET /api/auth/me -> { id, username, email } del usuario del token
export function getCurrentUser() {
  return apiFetch("/api/auth/me");
}

// POST /api/auth/password-reset/request -> { detail }
// Responde lo mismo exista o no el correo.
export function requestPasswordReset(email) {
  return apiFetch("/api/auth/password-reset/request", {
    method: "POST",
    auth: false,
    body: { email },
  });
}

// POST /api/auth/password-reset/confirm -> 204
// El token llega en el enlace del correo (?reset_token=...).
export function confirmPasswordReset(token, newPassword) {
  return apiFetch("/api/auth/password-reset/confirm", {
    method: "POST",
    auth: false,
    body: { token, new_password: newPassword },
  });
}

// POST /api/auth/verify-email -> 204. El token llega en el enlace (?verify_token=...).
export function verifyEmail(token) {
  return apiFetch("/api/auth/verify-email", { method: "POST", auth: false, body: { token } });
}

// POST /api/auth/verify-email/code -> 204. Código de 6 dígitos que llega por correo.
export function verifyEmailCode(email, code) {
  return apiFetch("/api/auth/verify-email/code", { method: "POST", auth: false, body: { email, code } });
}

// POST /api/auth/verify-email/resend -> { detail }. Manda un código nuevo (y el enlace).
// Responde lo mismo exista o no la cuenta.
export function resendVerification(email) {
  return apiFetch("/api/auth/verify-email/resend", { method: "POST", auth: false, body: { email } });
}

// POST /api/auth/password -> { access_token }. Las demás sesiones se cierran;
// esta sigue abierta con el token nuevo.
export async function changePassword(currentPassword, newPassword) {
  const data = await apiFetch("/api/auth/password", {
    method: "POST",
    body: { current_password: currentPassword, new_password: newPassword },
  });
  setToken(data.access_token);
  return data;
}

// DELETE /api/auth/me -> 204
export async function deleteAccount(password) {
  await apiFetch("/api/auth/me", { method: "DELETE", body: { password } });
  clearToken();
}

// GET /api/auth/sessions -> [{ id, created_at, last_seen_at, expires_at, user_agent, ip_address, current }]
export function listSessions() {
  return apiFetch("/api/auth/sessions");
}

// DELETE /api/auth/sessions/{id} -> 204. Ese token deja de servir.
export function revokeSession(sessionId) {
  return apiFetch(`/api/auth/sessions/${sessionId}`, { method: "DELETE" });
}

// DELETE /api/auth/sessions -> 204. Cierra todas menos esta.
export function revokeOtherSessions() {
  return apiFetch("/api/auth/sessions", { method: "DELETE" });
}

// Borra el token local y avisa al backend (POST /api/auth/logout) para que deje de
// servir. No usa apiFetch: un 401 dispararía otra vez el cierre de sesión.
export function logout() {
  const token = getToken();
  clearToken();
  if (!token) return;
  fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    keepalive: true,
  }).catch(() => {
    // Si no hay conexión, el token vence solo.
  });
}
