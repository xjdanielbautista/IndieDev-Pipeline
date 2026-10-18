# Backend: Indie Dev Pipeline

API REST inicial para la plataforma SaaS multi-tenant de gestión de estudios indie. Está construida con Python, FastAPI y SQLAlchemy; MySQL es la base de datos objetivo del proyecto. Para ejecutar una demostración local sin instalar MySQL, la aplicación usa SQLite cuando no se define `DATABASE_URL`.

## Alcance implementado

- Creación de estudios (tenants) y registro del propietario con rol `owner`.
- Registro de usuarios con nombre de usuario, correo y contraseña protegida mediante hash Argon2; inicio de sesión con token Bearer JWT.
- Proyectos y tareas Kanban, clasificadas por fase (preproducción, alpha, beta y testing) y área de trabajo.
- Registro de builds con versión, notas, estado y URL opcional.
- Registro de metadatos de assets y bloqueo/liberación para evitar ediciones simultáneas.
- Las rutas privadas requieren token y validan que el usuario pertenezca al tenant consultado.
- Documentación interactiva de endpoints en `/docs`.

## Ejecución local

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(openssl rand -hex 32)"
alembic upgrade head
uvicorn app.main:app --reload
```

La API estará disponible en `http://127.0.0.1:8000`; el chequeo básico está en `/health` y Swagger UI en `/docs`.
El backend permite solicitudes del frontend local en `http://localhost:5173` de forma predeterminada. Al cambiar el puerto local, define `FRONTEND_ORIGINS` con el origen exacto del frontend.
Conserva el mismo `SECRET_KEY` mientras quieras que los tokens emitidos sigan siendo válidos. En producción configúralo como variable secreta del servicio; no uses el `.env.example` como archivo de credenciales.

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
export SECRET_KEY="$(openssl rand -hex 32)"
alembic upgrade head
uvicorn app.main:app --reload
```

Ejecuta `alembic upgrade head` con la misma `DATABASE_URL` que usará la API. La migración agrega las columnas de autenticación a una tabla `users` existente. Las tablas que falten se crean al iniciar la aplicación.

### Autenticación

1. `POST /api/auth/register` crea una cuenta nueva. Envía `username`, `email` y `password`; la contraseña debe tener entre 8 y 128 caracteres. Se almacena un hash Argon2, nunca la contraseña original. No se permiten correos ni nombres de usuario repetidos.
2. `POST /api/auth/token` inicia sesión y devuelve un token JWT válido durante 30 minutos por defecto. El endpoint recibe `application/x-www-form-urlencoded` y solo pide `username` y `password`; en el campo `username` también puedes escribir el correo.
3. En `/docs`, pulsa **Authorize** e inicia sesión para enviar el token en las siguientes solicitudes. También puedes usar `Authorization: Bearer <token>` desde un cliente HTTP.
4. `GET /api/auth/me` devuelve el usuario del token. `POST /api/tenants` crea un estudio cuyo propietario es el usuario autenticado; ahora el body solo requiere `name` y `slug`.

Todas las rutas de tenants, proyectos, tareas, builds y assets requieren autenticación y una membresía en el tenant correspondiente. En las operaciones de bloqueo, el usuario se obtiene del token; el `user_id` enviado por el cliente no determina quién bloquea el asset.

Los usuarios que ya existían antes de agregar autenticación conservan sus datos, pero quedan sin nombre de usuario ni contraseña. Después de aplicar la migración, puedes asignarles credenciales desde una terminal con acceso a la misma base de datos:

```bash
python -m app.set_user_credentials
```

El comando pide correo, nombre de usuario y contraseña de forma interactiva, sin guardar la contraseña en el historial de la terminal. Para bases remotas, exporta primero la `DATABASE_URL` correcta.

### Configurar Render y Vercel

Como el backend está en la carpeta `Backend`, configura esa carpeta como **Root Directory** del servicio en Render y estas variables de entorno:

- `DATABASE_URL`: URL de conexión a la base de datos MySQL accesible desde Render.
- `FRONTEND_ORIGINS`: dominio del frontend publicado en Vercel, por ejemplo `https://mi-proyecto.vercel.app`. No agregues una ruta como `/dashboard`.
- `SECRET_KEY`: valor aleatorio generado con `openssl rand -hex 32`; guárdalo como secreto y no lo compartas.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: duración opcional del token en minutos (30 por defecto).

Si necesitas permitir más de un origen (por ejemplo, el dominio de producción y el de preview), sepáralos con comas en `FRONTEND_ORIGINS`. En Render, usa como comando de inicio:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Antes de arrancar la nueva versión contra una base de datos existente, ejecuta `alembic upgrade head` con la `DATABASE_URL` configurada en Render para agregar las columnas de autenticación.

En Vercel, configura `VITE_API_BASE_URL` con la URL pública del servicio de Render, por ejemplo `https://mi-api.onrender.com`, sin agregar `/docs` ni una ruta de API. Vite incorpora esta variable al compilar el frontend, así que vuelve a desplegarlo después de cambiarla. Para desarrollo local, usa `VITE_API_BASE_URL=http://localhost:8000` en el entorno del frontend.

## Endpoints de avance

- `POST /api/auth/register`, `POST /api/auth/token` y `GET /api/auth/me`: registro, inicio de sesión y consulta del usuario autenticado.
- `POST /api/tenants`: crea un estudio para el usuario autenticado; requiere `name` y `slug`.
- `GET /api/tenants/{tenant_id}`: consulta un estudio si el usuario pertenece a él.
- `POST`, `GET /api/tenants/{tenant_id}/projects`: alta y consulta de proyectos.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/tasks`: alta y consulta de tareas.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/builds`: registro e historial de builds.
- `POST /api/tenants/{tenant_id}/projects/{project_id}/assets`: registra los metadatos de un asset.
- `PATCH /api/tenants/{tenant_id}/assets/{asset_id}/lock` y `DELETE .../lock`: bloquea y libera assets.

## Pendiente

La autenticación base y la comprobación de membresía están implementadas. Aún falta aplicar permisos específicos según cada rol (RBAC), verificación de correo, recuperación de contraseña, revocación de tokens y límites contra intentos repetidos de inicio de sesión. La migración de Alembic incluida cubre las nuevas columnas de autenticación; todavía falta versionar con migraciones el esquema completo del proyecto. También faltan la recepción/verificación de webhooks de GitHub y la subida binaria a Firebase/S3.

El frontend todavía debe enviar las credenciales al endpoint de autenticación, conservar y adjuntar el token Bearer en las rutas privadas y dejar de usar IDs de usuario fijos para el bloqueo de assets.
