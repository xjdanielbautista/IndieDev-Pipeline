# Frontend: IndieDev Pipeline

React + Vite + Tailwind CSS v4. Se conecta al backend FastAPI de la carpeta `Backend`.

## Ejecución local

```bash
cd Frontend
cp .env.example .env
npm install
npm run dev
```

Abre `http://localhost:5173`. El backend debe estar corriendo en `http://localhost:8000` (ver `Backend/README.md`).

## Variables de entorno (`Frontend/.env`)

| Variable | Para qué sirve |
| --- | --- |
| `VITE_API_BASE_URL` | URL del backend. Local: `http://localhost:8000`. En Vercel: la URL pública de Render. |
| `VITE_TENANT_ID` | ID del estudio que se muestra en el encabezado. |
| `VITE_PROJECT_ID` | ID del proyecto del asset de prueba. |
| `VITE_ASSET_ID` | ID del asset conectado a la tarjeta ART-105 (bloqueo/liberación). |

El usuario ya no se configura con una variable: el backend lo obtiene del token de la sesión.

## Autenticación

- **Crear cuenta** → `POST /api/auth/register` con JSON `{ username, email, password }` (contraseña de 8 a 128 caracteres). Al registrarse, el frontend inicia sesión automáticamente.
- **Iniciar sesión** → `POST /api/auth/token` como formulario `application/x-www-form-urlencoded` con los campos `username` y `password`. En `username` se puede escribir el nombre de usuario **o** el correo. Responde `{ access_token, token_type: "bearer" }`.
- El token se guarda en `localStorage` (`indiedev_token`), así que la sesión se mantiene al recargar la página.
- El token dura 30 minutos. Cuando vence, o si el backend responde `401`, el frontend borra el token y regresa al login con un aviso.

### Hacer peticiones autenticadas

Usa `apiFetch` de `src/api/client.js`; agrega solo el header `Authorization: Bearer <token>` y convierte el body a JSON:

```js
import { apiFetch } from "./api/client";

// GET
const proyectos = await apiFetch(`/api/tenants/${tenantId}/projects`);

// POST
const estudio = await apiFetch("/api/tenants", {
  method: "POST",
  body: { name: "Mi estudio", slug: "mi-estudio" },
});
```

Si la petición falla, lanza un error con el mensaje que manda el backend en `detail` (`error.message`) y el código HTTP (`error.status`).

## Estructura relevante

- `src/api/client.js`: manejo del token y `apiFetch`.
- `src/api/auth.js`: `register`, `login`, `getCurrentUser`, `logout`.
- `src/components/LoginScreen.jsx`: pantalla de inicio de sesión y registro.
- `src/App.jsx`: tablero Kanban. El encabezado muestra el usuario (`/api/auth/me`) y el estudio (`/api/tenants/{id}`). La tarjeta ART-105 está conectada al asset real; el resto de tareas sigue con datos de ejemplo.

## Probar el bloqueo de ART-105

El asset debe existir y tu usuario debe pertenecer al estudio. Después de crear tu cuenta, en `http://localhost:8000/docs` pulsa **Authorize**, inicia sesión y crea en orden: un estudio (`POST /api/tenants`), un proyecto y un asset. Pon esos IDs en `Frontend/.env` y reinicia `npm run dev`.

## Despliegue (Vercel)

Configura `VITE_API_BASE_URL` (y los IDs) en las variables de entorno del proyecto en Vercel y vuelve a desplegar: Vite incluye estas variables al compilar. El dominio de Vercel debe estar en `FRONTEND_ORIGINS` del backend.
