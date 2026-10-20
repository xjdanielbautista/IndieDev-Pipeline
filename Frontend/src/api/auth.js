import { apiFetch, clearToken, setToken } from "./client";

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

export function logout() {
  clearToken();
}
