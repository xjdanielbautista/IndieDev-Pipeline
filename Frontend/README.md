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

El estudio y el proyecto ya no se configuran con variables: se eligen (o se crean) desde la página.

## Qué hace la aplicación

- **Primeros pasos:** si tu cuenta no tiene estudio, te pide crear uno (quedas como dueño) y luego tu primer proyecto.
- **Selector de estudio y proyecto** en el encabezado, con opción de crear nuevos. Se recuerda la última selección.
- **Tablero Kanban** conectado al backend (cada tarjeta es un asset): Backlog, En progreso, Revisión y Terminado. Se mueven con las flechas o arrastrando, y el tablero se recarga solo cada 30 segundos.
- **Nueva tarea:** nombre, tipo (código/arte), columna, integrantes asignados y opción de que solo ellos puedan moverla.
- **Panel de detalle** (clic en una tarjeta): cambiar columna, tipo y asignados; bloquear/liberar el archivo; historial con quién hizo cada cambio y a qué hora; botón **Restaurar** en los últimos 3 cambios para volver al valor anterior.
- **Filtros:** búsqueda por nombre o `#id`, por tipo y "Mis tareas".
- **Asset Vault:** tabla con todas las tareas, su estado, asignados y bloqueo.
- **Build History:** registro de versiones con estado, notas y URL; la última aparece en el encabezado.
- **Equipo:** integrantes con su rol y sus tareas pendientes; agregar, cambiar rol o quitar (dueño/admin).

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
- `src/api/studio.js`: llamadas de estudios, proyectos, integrantes, assets, historial y builds.
- `src/utils/labels.js`: etiquetas en español, formato de fechas (el backend guarda UTC; se muestran en hora local).
- `src/components/LoginScreen.jsx`: inicio de sesión y registro.
- `src/components/Workspace.jsx`: encabezado, primeros pasos, filtros y pestañas.
- `src/components/KanbanBoard.jsx`, `TaskDetail.jsx`, `AssetVault.jsx`, `BuildHistory.jsx`, `TeamPanel.jsx`, `forms.jsx`, `ui.jsx`.
- `src/utils/permissions.js`: reglas por rol para la interfaz.

## Roles y permisos

En la pestaña **Equipo**, el dueño o un admin agregan integrantes (por usuario o correo; deben tener cuenta) y eligen su rol. La interfaz oculta o desactiva lo que cada rol no puede hacer, con las mismas reglas que valida el backend (`src/utils/permissions.js` es copia de `Backend/app/permissions.py`):

| Rol | Puede |
| --- | --- |
| Dueño | Todo. Es el único que nombra o quita admins. |
| Admin | Crear proyectos y tareas, asignar, cambiar cualquier campo, mover cualquier tarea, liberar bloqueos ajenos, administrar developers/artistas/testers. |
| Developer | Mover y bloquear tareas de código; registrar builds. |
| Artista | Mover y bloquear tareas de arte. |
| Tester | Aprobar (Revisión → Terminado), regresar a En progreso o reabrir una terminada. |

En modo restringido, solo los asignados pueden mover la tarea; dueño y admin siempre pueden.

## Despliegue (Vercel)

Configura `VITE_API_BASE_URL` en las variables de entorno del proyecto en Vercel y vuelve a desplegar: Vite incluye estas variables al compilar. El dominio de Vercel debe estar en `FRONTEND_ORIGINS` del backend.
