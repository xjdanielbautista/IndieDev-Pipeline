# Backend: Indie Dev Pipeline

API REST inicial para la plataforma SaaS multi-tenant de gestión de estudios indie. Está construida con Python, FastAPI y SQLAlchemy; MySQL es la base de datos objetivo del proyecto. Para ejecutar una demostración local sin instalar MySQL, la aplicación usa SQLite cuando no se define `DATABASE_URL`.

## Alcance implementado

- Creación de estudios (tenants) y registro del propietario con rol `owner`.
- Registro de usuarios con nombre de usuario, correo y contraseña protegida mediante hash Argon2; inicio de sesión con token Bearer JWT.
- Proyectos y tareas Kanban, clasificadas por fase (preproducción, alpha, beta y testing) y área de trabajo.
- Registro de builds con versión, notas, estado y URL opcional.
- Assets clasificados como `code` (Código) o `art` (Arte), con estados Kanban, asignación abierta o restringida a varios integrantes, bloqueo e historial de cambios.
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

Ejecuta `alembic upgrade head` con la misma `DATABASE_URL` que usará la API. Las migraciones agregan los campos de autenticación y de gestión de assets a las tablas existentes. Las tablas que falten se crean al iniciar la aplicación.

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
- `ASSET_STORAGE_PROVIDER`: proveedor que configura el backend (`firebase`, `s3` o `local`); no lo elige ni lo envía el usuario de la página.
- `MAX_UPLOAD_MB`: tamaño máximo de cada archivo, 200 MB por defecto si no se define.
- `LOCAL_UPLOAD_DIR`: carpeta local para `ASSET_STORAGE_PROVIDER=local`.
- Firebase: `FIREBASE_CREDENTIALS` con la ruta al JSON de la cuenta de servicio y `FIREBASE_BUCKET` con el nombre del bucket.
- S3: `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`.- Para Supabase Storage: `S3_ENDPOINT_URL`, además de las variables S3 anteriores.
### Configurar almacenamiento local

Esta opción sirve para desarrollo y no necesita credenciales de Firebase ni AWS:

```bash
export ASSET_STORAGE_PROVIDER=local
export LOCAL_UPLOAD_DIR=./uploads
export MAX_UPLOAD_MB=200
```

Los archivos se guardan dentro de `Backend/uploads`. Agrega esta carpeta al `.gitignore` si quieres evitar subir archivos binarios al repositorio.

### Configurar Firebase Storage

1. Abre Firebase Console y entra en **Project Settings → Service accounts**.
2. Selecciona Node.js y pulsa **Generate new private key**.
3. Guarda el JSON fuera del repositorio, por ejemplo como `~/keys/indiedev-firebase.json`.
4. Configura el bucket en Firebase Storage y obtén su nombre.
5. Exporta las variables antes de iniciar Uvicorn:

```bash
export ASSET_STORAGE_PROVIDER=firebase
export FIREBASE_CREDENTIALS=/ruta/indiedev-firebase.json
export FIREBASE_BUCKET=tu-proyecto.appspot.com
export MAX_UPLOAD_MB=200
```

`FIREBASE_CREDENTIALS` contiene una clave privada. No la agregues al repositorio, al README, ni la publiques en una captura o imagen.

### Configurar S3

1. Crea un bucket en AWS S3.
2. Crea un usuario IAM destinado al backend con permisos para subir, consultar y generar URLs firmadas de objetos en ese bucket.
3. Genera una Access Key para ese usuario.
4. Exporta las credenciales solo en la terminal o en secretos del servicio:

```bash
export ASSET_STORAGE_PROVIDER=s3
export S3_BUCKET=mi-bucket
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=tu-access-key-id
export AWS_SECRET_ACCESS_KEY=tu-secret-access-key
export MAX_UPLOAD_MB=200
```

No uses credenciales personales ni compartas `AWS_SECRET_ACCESS_KEY`. En Render configura esos valores como secretos del servicio y evita escribirlos directamente en el repositorio. La aplicación entrega URLs firmadas válidas durante 10 minutos.

Para Supabase Storage, conserva las variables S3 y agrega el endpoint S3 mostrado en Supabase. No uses la `anon key` ni la `service role key` como credenciales AWS:

```bash
export ASSET_STORAGE_PROVIDER=s3
export S3_BUCKET=nombre-del-bucket
export S3_ENDPOINT_URL=https://<project-ref>.storage.supabase.co/storage/v1/s3
export AWS_REGION=<region>
export AWS_ACCESS_KEY_ID=<s3-access-key>
export AWS_SECRET_ACCESS_KEY=<s3-secret-key>
export MAX_UPLOAD_MB=50
```

El backend detecta `S3_ENDPOINT_URL` y configura automáticamente firma SigV4 y direccionamiento por ruta, compatible con el endpoint S3 de Supabase. Reinicia Uvicorn después de exportar las variables.

### Variables generales para reiniciar el backend

Después de cambiar las variables, reinicia Uvicorn. Las variables exportadas solo existen en la terminal donde las ejecutaste:

```bash
export SECRET_KEY="$(openssl rand -hex 32)"
export DATABASE_URL='mysql+pymysql://usuario:password@localhost:3306/indiedev'
alembic upgrade head
uvicorn app.main:app --reload

### Guardar las variables en un archivo local

Dentro de `Backend` puedes copiar el archivo de ejemplo y completar los datos:

```bash
cp .env.example .env.local
```

Luego carga todas las variables en la terminal actual sin exportarlas una por una:

```bash
source ./load-env.sh
```

`.env.local` y cualquier archivo `.env` deben ignorarse en Git; `.env.example` sí puede publicarse siempre que no contenga secretos reales. El script `load-env.sh` conserva variables de la terminal que ya tengan un valor y solo las reemplaza con las que estén definidas en `.env.local`.
```

Si trabajas con SQLite local y MySQL ya no tiene prioridad, puedes omitir `DATABASE_URL`. Usa `ASSET_STORAGE_PROVIDER=local` mientras desarrollas si no quieres configurar Firebase o S3.

Si necesitas permitir más de un origen (por ejemplo, el dominio de producción y el de preview), sepáralos con comas en `FRONTEND_ORIGINS`. En Render, usa como comando de inicio:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Antes de arrancar la nueva versión contra una base de datos existente, ejecuta `alembic upgrade head` con la `DATABASE_URL` configurada en Render para aplicar las migraciones pendientes de autenticación y assets.

En Vercel, configura `VITE_API_BASE_URL` con la URL pública del servicio de Render, por ejemplo `https://mi-api.onrender.com`, sin agregar `/docs` ni una ruta de API. Vite incorpora esta variable al compilar el frontend, así que vuelve a desplegarlo después de cambiarla. Para desarrollo local, usa `VITE_API_BASE_URL=http://localhost:8000` en el entorno del frontend.

## Endpoints de avance

- `POST /api/auth/register`, `POST /api/auth/token` y `GET /api/auth/me`: registro, inicio de sesión y consulta del usuario autenticado.
- `POST /api/tenants`: crea un estudio para el usuario autenticado; requiere `name` y `slug`.
- `GET /api/tenants/{tenant_id}`: consulta un estudio si el usuario pertenece a él.
- `GET /api/tenants`: lista los estudios del usuario autenticado con su rol en cada uno.
- `GET /api/tenants/{tenant_id}/members`: lista integrantes con `id`, `username`, `email` y `role`.
- `POST /api/tenants/{tenant_id}/members`: agrega un integrante con `{ "identifier": "<usuario o correo>", "role": "developer" }`. La cuenta debe existir.
- `PATCH /api/tenants/{tenant_id}/members/{user_id}`: cambia el rol con `{ "role": "artist" }`.
- `DELETE /api/tenants/{tenant_id}/members/{user_id}`: quita al integrante, sus asignaciones y los bloqueos que tenía en el estudio.
- `POST`, `GET /api/tenants/{tenant_id}/projects`: alta y consulta de proyectos.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/tasks`: alta y consulta de tareas.
- `POST`, `GET /api/tenants/{tenant_id}/projects/{project_id}/builds`: registro e historial de builds.
- `POST /api/tenants/{tenant_id}/projects/{project_id}/assets`: registra metadatos y permite enviar `category`, `status`, `assignment_mode` y `assigned_user_ids`. `storage_provider` se configura en el backend y no forma parte de la solicitud. Por defecto, categoría `art`, estado `backlog`, modo `open` y sin lista de asignados.
- `GET /api/tenants/{tenant_id}/projects/{project_id}/assets`: lista los assets de un proyecto.
- `GET /api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}`: consulta un asset por ID; devuelve categoría, estado, creador, integrante asignado y datos del bloqueo.
- `PATCH /api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}`: actualiza `category`, `status`, `assignment_mode` o la lista `assigned_user_ids`.
- `GET /api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/history`: devuelve los eventos con acción, usuario y fecha.
- `PATCH /api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/lock` y `DELETE .../lock`: bloquea y libera assets; el bloqueo queda registrado en el historial.
- `POST .../assets/{asset_id}/file`: recibe `multipart/form-data` con el campo `file`; requiere bloqueo propio y permiso del rol.
- `GET .../assets/{asset_id}/file`: descarga desde el proveedor local o devuelve una URL firmada para S3/Firebase.

Los valores permitidos para `category` son `code` (Código) y `art` (Arte). Los valores de `status` son `backlog` (Backlog), `in_progress` (En proceso), `review` (Revisión) y `done` (Terminado). `assignment_mode` acepta `open` o `restricted`: en modo abierto cualquier integrante del estudio puede cambiar el estado; en modo restringido solo pueden hacerlo los usuarios incluidos en `assigned_user_ids`. Esa lista puede contener varios IDs y cada usuario debe pertenecer al mismo estudio. La base los relaciona mediante `asset_assignments`, de modo que cada usuario puede estar asignado a varios assets y cada asset a varios usuarios. El bloqueo es independiente del flujo Kanban. La respuesta incluye `assigned_users` con ID y nombre de usuario; el historial conserva quién realizó cada cambio y cuándo.

`storage_key` es la clave interna/ruta que usa el backend para localizar el archivo en el proveedor configurado. El cliente debe enviar el asset y los metadatos; el proveedor se configura exclusivamente en el backend mediante variables de entorno.

Ejemplo de creación para trabajo abierto:

```json
{
  "original_name": "personaje.fbx",
  "storage_key": "studios/mi-estudio/assets/personaje.fbx",
  "category": "art",
  "status": "backlog",
  "assignment_mode": "open",
  "assigned_user_ids": []
}
```

Para limitar el avance a dos integrantes, usa `"assignment_mode": "restricted"` y `"assigned_user_ids": [2, 5]` con IDs reales de miembros del estudio.

Las migraciones asignan `art`, `backlog` y el modo `open` a los assets existentes. Si un asset tenía un usuario asignado con el esquema anterior, esa asignación se conserva en la tabla nueva. No inventan creador ni eventos anteriores; el historial comienza a partir de su implementación.

## Roles y permisos

Las reglas están en `app/permissions.py`:

- `owner` (dueño) y `admin`: crean proyectos, tareas (`tasks` y `assets`), asignan integrantes y cambian `category`, `assignment_mode` y `assigned_user_ids`; mueven cualquier asset y pueden liberar bloqueos de otros. Solo el dueño nombra o quita admins; nadie puede asignar el rol `owner` ni cambiar o quitar al dueño.
- `developer`: mueve y bloquea assets `code`; registra builds.
- `artist`: mueve y bloquea assets `art`.
- `tester`: solo puede cambiar `status` de `review` a `done` o `in_progress`, y de `done` a `review`.

El modo `restricted` se sigue aplicando a developers, artistas y testers; dueño y admin pueden mover cualquier asset. Las pruebas de estas reglas están en `tests/test_roles.py` (`pytest` desde la carpeta `Backend`, con `requirements-dev.txt`).

## Pendiente

Verificación de correo, recuperación de contraseña, revocación de tokens y límites contra intentos repetidos de inicio de sesión. Las migraciones cubren autenticación y el esquema de assets; todavía falta versionar con migraciones el resto del esquema. También faltan la recepción/verificación de webhooks de GitHub. La subida y descarga binaria están disponibles para almacenamiento local, Firebase y S3.
