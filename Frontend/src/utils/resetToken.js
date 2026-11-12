// Token del enlace de recuperación (?reset_token=...), si se abrió desde el correo.
export function getResetTokenFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get("reset_token") || "";
  } catch {
    return "";
  }
}

// Quita el token de la barra de direcciones para que no quede en el historial.
export function clearResetTokenFromUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("reset_token");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
}
