# Pendientes del backend

Este documento describe lo que falta implementar en el backend, con los endpoints y formatos exactos que **el frontend ya espera**. El frontend ya tiene las pantallas listas: mientras un endpoint no exista muestran "Próximamente", y se activan solas en cuanto el endpoint responde.

Cada sección se puede trabajar por separado. Sugerencia: una persona por sección, una rama por sección y un Pull Request al terminar.

## Cómo detecta el frontend que algo ya está implementado

- Si una ruta no existe, FastAPI responde `404` con `{"detail": "Not Found"}` (o `405` si existe la ruta con otro método). El frontend interpreta eso como "todavía no implementado" y muestra "Próximamente".
- **Importante:** cuando un recurso no exista (por ejemplo, un comentario que ya se borró), responde `404` con un mensaje propio en español, **nunca** con el texto exacto `"Not Found"`, o el frontend creerá que la función no existe.
- En la sección de archivos, el frontend busca los campos nuevos de `AssetRead` (`file_size`, etc.); si no vienen en la respuesta, muestra "Próximamente".

Todas las rutas usan el token Bearer y la membresía del estudio, igual que las rutas actuales, y deben respetar los permisos de `app/permissions.py`. Las rutas de cada sección van bajo `/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}` (abreviado como `.../assets/{asset_id}`).

---

## 1. Subida y descarga de archivos (Firebase / S3)

Hoy un asset solo guarda metadatos (`original_name`, `storage_key`). Falta subir el archivo real al proveedor configurado en `ASSET_STORAGE_PROVIDER`.

### Cambios al modelo `Asset` (con migración de Alembic)

| Campo | Tipo | Nota |
| --- | --- | --- |
| `file_size` | `BigInteger`, nullable | Bytes del último archivo subido. |
| `content_type` | `String(120)`, nullable | MIME del archivo. |
| `file_uploaded_at` | `DateTime(timezone=True)`, nullable | Cuándo se subió la última versión. |

`AssetRead` debe incluir los tres campos (en `null` mientras no haya archivo). **Su sola presencia en la respuesta es lo que activa la sección "Archivo" en el frontend.**

### `POST .../assets/{asset_id}/file`

- Cuerpo `multipart/form-data` con el campo `file`.
- Reglas:
  - El usuario debe tener el asset **bloqueado a su nombre** (`locked_by_user_id == current_user.id`). Si no, `409` con `"Bloquea el archivo antes de subir una nueva versión"`. Así el bloqueo tiene sentido real: nadie sobrescribe el trabajo de otro.
  - Debe poder bloquear según su rol (`require_can_lock`).
  - Tamaño máximo configurable con `MAX_UPLOAD_MB` (sugerido: 200). Si se excede, `413`.
- Guarda el archivo en el proveedor en la ruta `storage_key` (reemplaza la versión anterior) y actualiza `file_size`, `content_type` y `file_uploaded_at`.
- Registra en el historial la acción `file_uploaded` con `new_value = "<nombre> (<tamaño legible>)"`. El frontend ya traduce esa acción como "subió una nueva versión".
- Responde `200` con el `AssetRead` actualizado.

### `GET .../assets/{asset_id}/file`

- Cualquier integrante del estudio.
- Si no hay archivo: `404` con `"Este asset todavía no tiene archivo"`.
- Firebase / S3: responde `200` con JSON `{ "url": "<URL firmada>", "expires_at": "<ISO 8601>" }`. Basta con 10 minutos de vigencia. El frontend abre esa URL.
- Proveedor `local` (para desarrollo): puede responder directamente el archivo con `FileResponse`; el frontend también sabe descargarlo así.

Variables de entorno nuevas a documentar: `MAX_UPLOAD_MB` y las credenciales del proveedor (`FIREBASE_CREDENTIALS`/`FIREBASE_BUCKET` o `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`S3_BUCKET`), y `LOCAL_UPLOAD_DIR` para `local`.

---

## 2. Webhooks de GitHub: commits en las tareas de código

Objetivo: cuando alguien hace push con un mensaje como `Arregla colisiones #12`, el commit aparece en la tarjeta #12.

### Cambios al modelo

- `Project`: agregar `github_repo` (`String(200)`, nullable, formato `owner/repo`) y `github_webhook_secret` (`String(64)`, nullable). El secreto **nunca** se devuelve en `ProjectRead`.
- Tabla nueva `asset_commits`: `id`, `tenant_id`, `asset_id` (FK, `ondelete=CASCADE`), `sha` (`String(40)`), `message` (`Text`), `author_name` (`String(120)`), `url` (`String(500)`), `committed_at` (`DateTime(timezone=True)`), con `UniqueConstraint("asset_id", "sha")`.

### `POST /api/tenants/{tenant_id}/projects/{project_id}/github`

- Solo dueño/admin. Cuerpo `{ "github_repo": "owner/repo" }`.
- Genera un secreto nuevo (`secrets.token_hex(32)`), lo guarda y responde **una sola vez**:
  `{ "github_repo": "owner/repo", "webhook_url": "https://<backend>/api/webhooks/github/{project_id}", "secret": "<secreto>" }`.
- Con eso se configura el webhook en GitHub: *Settings → Webhooks → Add webhook*, Content type `application/json`, evento *Just the push event*.

### `POST /api/webhooks/github/{project_id}` (pública, sin token)

- Verifica la firma `X-Hub-Signature-256` con HMAC-SHA256 del **cuerpo crudo** y el secreto del proyecto, comparando con `hmac.compare_digest`. Firma inválida o proyecto sin secreto: `401`.
- Evento `ping` (`X-GitHub-Event: ping`): responde `200`.
- Evento `push`: por cada elemento de `payload["commits"]`, busca referencias con la expresión `#(\d+)` en `message`. Si el número es un asset **de ese proyecto**, inserta en `asset_commits` (ignora duplicados por `sha`). Los campos salen de `id`, `message`, `author.name`, `url` y `timestamp`. Responde `204`.

### `GET .../assets/{asset_id}/commits`

- Cualquier integrante. Responde la lista, la más reciente primero:

```json
[
  {
    "sha": "f7a9c2b1d3e4...",
    "message": "Agrega dash aéreo #12",
    "author_name": "Alex",
    "url": "https://github.com/owner/repo/commit/f7a9c2b...",
    "committed_at": "2026-10-20T08:15:00Z"
  }
]
```

El frontend muestra esta sección solo en tareas de tipo `code`.

---

## 3. Comentarios en las tareas

### Modelo

Tabla `asset_comments`: `id`, `tenant_id`, `asset_id` (FK, `ondelete=CASCADE`), `user_id` (FK, `ondelete=SET NULL`, nullable), `body` (`Text`), `created_at` (`DateTime`, `server_default=func.now()`).

### Endpoints

- `GET .../assets/{asset_id}/comments`: cualquier integrante. Lista del **más antiguo al más reciente**:

```json
[
  {
    "id": 3,
    "asset_id": 12,
    "user": { "id": 2, "username": "sam_art" },
    "body": "Ya quedó la primera versión del sprite",
    "created_at": "2026-10-20T08:20:00"
  }
]
```

- `POST .../assets/{asset_id}/comments`: cualquier integrante. Cuerpo `{ "body": "..." }` (1 a 2000 caracteres, sin espacios al inicio o final). Responde `201` con el comentario en el mismo formato.
- `DELETE .../assets/{asset_id}/comments/{comment_id}`: el autor del comentario, o dueño/admin. Responde `204`. Si el comentario no existe: `404` con `"Comentario no encontrado"`.

---

## 4. Notificaciones

### Modelo

Tabla `notifications`: `id`, `user_id` (destinatario), `tenant_id`, `project_id` (nullable), `asset_id` (nullable), `kind` (`String(40)`), `message` (`String(300)`), `read_at` (`DateTime`, nullable), `created_at`.

### Cuándo se crean

| `kind` | Destinatarios | Ejemplo de `message` |
| --- | --- | --- |
| `assigned` | Cada usuario recién asignado a un asset (al crear o al editar asignados). | `xsep123 te asignó "Skin nueva de Ahri"` |
| `comment` | Asignados y creador del asset, excepto quien comenta. | `sam_art comentó en "Skin nueva de Ahri"` |
| `review` | Testers del estudio, cuando un asset pasa a `review`. | `"Parche 14.2" está listo para revisión` |
| `unlocked` | Quien tenía el bloqueo, cuando un dueño/admin lo libera. | `xsep123 liberó tu bloqueo de "level3.psd"` |

Nunca se notifica a quien hizo la acción.

### Endpoints

- `GET /api/notifications?limit=30`: notificaciones del usuario autenticado (de todos sus estudios), la más reciente primero:

```json
[
  {
    "id": 9,
    "kind": "assigned",
    "message": "xsep123 te asignó \"Skin nueva de Ahri\"",
    "tenant_id": 3,
    "project_id": 3,
    "asset_id": 12,
    "read": false,
    "created_at": "2026-10-20T08:25:00"
  }
]
```

- `POST /api/notifications/read`: marca como leídas. Cuerpo `{ "ids": [9, 10] }` o `{ "all": true }`. Responde `204`. Solo afecta notificaciones del propio usuario.

El frontend consulta este endpoint cada 30 segundos y al hacer clic en una notificación abre la tarea correspondiente.

---

## 5. Limpieza y mantenimiento

- **Sacar `Backend/indiedev.db` del repositorio.** Cada quien debe tener su base local. Ejecutar `git rm --cached Backend/indiedev.db` y agregar `*.db` al `.gitignore` de `Backend`.
- **CORS en errores 500.** Cuando el backend lanza una excepción no controlada, la respuesta sale sin cabeceras CORS y el navegador lo reporta como "no se pudo conectar", lo que confunde al depurar. Agregar un manejador `@app.exception_handler(Exception)` que registre el error con `logging` y responda `JSONResponse({"detail": "Error interno del servidor"}, status_code=500)`, para que pase por el middleware de CORS.
- **Migraciones.** Las tablas nuevas de este documento deben crearse con migraciones de Alembic (no solo con `create_all`) y probarse en SQLite **con una base que ya tenga datos**: en SQLite, `batch_alter_table` exige que toda llave foránea tenga nombre (`sa.ForeignKey("users.id", name="fk_...")`).
- **Pruebas.** Cada sección debe agregar sus pruebas en `Backend/tests/`, usando las fixtures `client` y `login` de `tests/conftest.py`.

---

## Checklist

- [✔️] 1. Subida y descarga de archivos
- [✔️] 2. Webhooks de GitHub y commits por tarea
- [✔️] 3. Comentarios
- [✔️] 4. Notificaciones
- [ ] 5. Limpieza (`indiedev.db`, CORS en 500, migraciones, pruebas)
