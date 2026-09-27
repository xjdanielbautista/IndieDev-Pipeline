# Backend: Indie Dev Pipeline

API REST inicial para la plataforma SaaS multi-tenant de gestión de estudios indie. Está construida con Python, FastAPI y SQLAlchemy; MySQL es la base de datos objetivo del proyecto. Para ejecutar una demostración local sin instalar MySQL, la aplicación usa SQLite cuando no se define `DATABASE_URL`.

## Alcance implementado

- Creación de estudios (tenants) y registro del propietario con rol `owner`.
- Proyectos y tareas Kanban, clasificadas por fase (preproducción, alpha, beta y testing) y área de trabajo.
- Registro de builds con versión, notas, estado y URL opcional.
- Registro de metadatos de assets y bloqueo/liberación para evitar ediciones simultáneas.
- Las consultas de proyectos, tareas, builds y assets se filtran por `tenant_id`.
- Documentación interactiva de endpoints en `/docs`.

## Ejecución local

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

La API estará disponible en `http://127.0.0.1:8000`; el chequeo básico está en `/health` y Swagger UI en `/docs`.

## MySQL

Crear una base de datos llamada `indiedev` y configurar la variable `DATABASE_URL`. El archivo `.env.example` muestra el formato esperado; exporta la variable en la terminal antes de iniciar Uvicorn:

```bash
export DATABASE_URL='mysql+pymysql://user:contraseña@localhost:3306/indiedev'
uvicorn app.main:app --reload
```

Las tablas se crean al iniciar la aplicación para este prototipo. Antes de un despliegue se deben agregar migraciones con Alembic.

## Endpoints de avance

- `POST /api/tenants`: crea estudio y usuario propietario.
- `POST`, `GET /api/tenants/{tenant_id}/projects`: alta y consulta de proyectos.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/tasks`: alta y consulta de tareas.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/builds`: registro e historial de builds.
- `POST /api/tenants/{tenant_id}/projects/{project_id}/assets`: registra los metadatos de un asset.
- `PATCH /api/tenants/{tenant_id}/assets/{asset_id}/lock` y `DELETE .../lock`: bloquea y libera assets.

## Pendiente

Este avance no implementa autenticación, autorización efectiva por rol, migraciones, recepción/verificación de webhooks de GitHub ni la subida binaria a Firebase/S3. El bloqueo de assets y el filtrado multi-tenant son una base de dominio, no un control de seguridad suficiente para producción.

