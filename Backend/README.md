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
El backend permite solicitudes del frontend local en `http://localhost:5173` de forma predeterminada. Al cambiar el puerto local, define `FRONTEND_ORIGINS` con el origen exacto del frontend.

## MySQL

### Instalar e iniciar MySQL

Si MySQL no está instalado, actualiza los paquetes e instala el servidor:

```bash
sudo apt-get update
sudo apt-get install -y mysql-server
```

Inicia el servicio antes de ejecutar la API:

```bash
sudo service mysql start
```

### Crear la base de datos y el usuario

Abre la consola de MySQL:

```bash
sudo mysql
```

Dentro de la consola, crea la base de datos y un usuario con permisos sobre ella. Puedes cambiar la contraseña de ejemplo por una propia:

```sql
CREATE DATABASE indiedev;
CREATE USER 'user'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON indiedev.* TO 'user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Conectar la API a MySQL

Los datos del usuario, contraseña, host, puerto y base de datos se colocan en `DATABASE_URL`. En este ejemplo, `user` y `password` son los que se crearon arriba:

```bash
export DATABASE_URL='mysql+pymysql://user:password@localhost:3306/indiedev'
uvicorn app.main:app --reload
```

Las tablas se crean al iniciar la aplicación para este prototipo. Antes de un despliegue se deben agregar migraciones con Alembic.

### Configurar Render y Vercel

Como el backend está en la carpeta `Backend`, configura esa carpeta como **Root Directory** del servicio en Render y estas variables de entorno:

- `DATABASE_URL`: URL de conexión a la base de datos MySQL accesible desde Render.
- `FRONTEND_ORIGINS`: dominio del frontend publicado en Vercel, por ejemplo `https://mi-proyecto.vercel.app`. No agregues una ruta como `/dashboard`.

Si necesitas permitir más de un origen (por ejemplo, el dominio de producción y el de preview), sepáralos con comas en `FRONTEND_ORIGINS`. En Render, usa como comando de inicio:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

En Vercel, configura `VITE_API_BASE_URL` con la URL pública del servicio de Render, por ejemplo `https://mi-api.onrender.com`, sin agregar `/docs` ni una ruta de API. Vite incorpora esta variable al compilar el frontend, así que vuelve a desplegarlo después de cambiarla. Para desarrollo local, usa `VITE_API_BASE_URL=http://localhost:8000` en el entorno del frontend.

## Endpoints de avance

- `POST /api/tenants`: crea estudio y usuario propietario.
- `POST`, `GET /api/tenants/{tenant_id}/projects`: alta y consulta de proyectos.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/tasks`: alta y consulta de tareas.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/builds`: registro e historial de builds.
- `POST /api/tenants/{tenant_id}/projects/{project_id}/assets`: registra los metadatos de un asset.
- `PATCH /api/tenants/{tenant_id}/assets/{asset_id}/lock` y `DELETE .../lock`: bloquea y libera assets.

## Pendiente

Este avance no implementa autenticación, autorización efectiva por rol, migraciones, recepción/verificación de webhooks de GitHub ni la subida binaria a Firebase/S3. El bloqueo de assets y el filtrado multi-tenant son una base de dominio, no un control de seguridad suficiente para producción.
