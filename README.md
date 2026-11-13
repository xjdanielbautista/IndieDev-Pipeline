# 🚀 IndieDev Pipeline

> **Plataforma SaaS de Gestión del Ciclo de Vida de Software y Arte para Estudios Indie de Videojuegos**

[![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Tailwind-blue)](https://react.dev/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python-green)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-MySQL%20%28Aiven%29-orange)](https://aiven.io/)
[![Deployment](https://img.shields.io/badge/Deployment-Vercel%20%7C%20Render-black)](https://vercel.com/)

---

## 📌 Descripción del Proyecto

**IndieDev Pipeline** es una solución web SaaS desacoplada diseñada específicamente para estudios independientes de videojuegos. La plataforma centraliza el seguimiento de tareas, la gestión de artefactos de arte y código (*Builds/Assets*) y la integración de eventos de repositorios para resolver la desorganización habitual en equipos multidisciplinarios.

---

## 🏗️ Arquitectura del Sistema

El proyecto está diseñado bajo un modelo **SaaS Multi-Tenant** que garantiza el aislamiento de datos por estudio mediante un discriminador `tenant_id` en la capa de datos.

```
                  ENTORNO DE PRODUCCIÓN (PROD)
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  [ Vercel ]  ──────────>  [ Render ]  ──────────> [ SQL ]    │
│  (Frontend)  Peticiones    (Backend)   Consultas  PostgreSQL │
│               HTTPS            │                  o MySQL    │
│                                │                             │
│                                └─────> [ Supabase S3 ]       │
│                                        o Firebase (archivos) │
└──────────────────────────────────────────────────────────────┘
```

* **Frontend:** React con Vite y Tailwind CSS, desplegado en Vercel.
* **Backend:** API REST con Python (FastAPI), desplegada en Render.
* **Base de Datos:** PostgreSQL o MySQL en la nube (la URL se configura con `DATABASE_URL`). En local, el backend usa SQLite si no se define `DATABASE_URL`.
* **Almacenamiento de Archivos:** Bucket desacoplado compatible con S3 (Supabase Storage o Amazon S3) o Firebase Storage. En local, una carpeta del disco.

---

## 📂 Estructura del Repositorio

```
IndieDev-Pipeline/
├── Frontend/             # Interfaz de usuario (React + Vite + Tailwind)
├── Backend/              # API REST y modelos de datos (FastAPI)
├── docs/
│   └── PENDIENTES_BACKEND.md  # Funciones pendientes con su especificación
└── README.md             # Documentación principal del proyecto
```

---

## 🛠️ Requisitos Previos

Para ejecutar el proyecto en un entorno local de desarrollo necesitas:

* Node.js 20.19 o superior (comprueba con `node -v`)
* Python 3.10 o superior
* Git

---

## 🚀 Guía de Instalación y Ejecución Local

Se necesitan **dos terminales**: una para el backend y otra para el frontend.

### 1. Clonar el repositorio

```bash
git clone https://github.com/xjdanielbautista/IndieDev-Pipeline.git
cd IndieDev-Pipeline
```

### 2. Levantar el Backend (FastAPI)

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY="$(openssl rand -hex 32)"   # obligatorio: firma los tokens de sesión
export ASSET_STORAGE_PROVIDER=local           # guarda los archivos en Backend/uploads
alembic upgrade head
uvicorn app.main:app --reload
```

> En Windows (PowerShell) usa `$env:SECRET_KEY = "<64 caracteres aleatorios>"` y `$env:ASSET_STORAGE_PROVIDER = "local"`. También puedes guardar las variables en `Backend/.env.local` y cargarlas con `source ./load-env.sh` (ver `Backend/README.md`).

El backend queda en `http://localhost:8000`. La documentación interactiva de la API está en `http://localhost:8000/docs` y la ruta de prueba en `http://localhost:8000/health`.

Sin `DATABASE_URL`, el backend usa SQLite, así que **no necesitas instalar ninguna base de datos** para probar. Para conectar PostgreSQL o MySQL, ver `Backend/README.md`.

Para tener datos de ejemplo (2 estudios, integrantes de cada rol, tareas y un build), con el backend corriendo:

```bash
python scripts/seed_demo.py
```

Usuarios: `dueno_pixel`, `dev_pixel`, `artista_pixel`, `tester_pixel` (y los de `nebula`). Contraseña de todos: `Demo12345`.

### 3. Levantar el Frontend (React)

En otra terminal:

```bash
cd Frontend
npm install
cp .env.example .env
npm run dev
```

El frontend queda en `http://localhost:5173`.

---

## 🔑 Variables de Entorno

### Backend

Se definen como variables de entorno (ejemplo en `Backend/.env.example`; el detalle está en `Backend/README.md`):

| Variable | Para qué sirve |
|---|---|
| `SECRET_KEY` | **Obligatoria.** Firma los tokens JWT; mínimo 32 caracteres aleatorios |
| `DATABASE_URL` | Conexión a la base de datos (`postgresql://...`, `mysql+pymysql://...`). Si no se define, usa SQLite local |
| `FRONTEND_ORIGINS` | Orígenes del frontend permitidos por CORS, separados por comas. Por defecto `http://localhost:5173` |
| `ASSET_STORAGE_PROVIDER` | Dónde se guardan los archivos: `local`, `s3` (Supabase/AWS) o `firebase` |
| `MAX_UPLOAD_MB` | Tamaño máximo por archivo (200 por defecto) |
| `PUBLIC_BACKEND_URL` | URL pública del backend para armar la URL del webhook de GitHub (opcional) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración de la sesión (30 por defecto) |
| `FRONTEND_URL` | URL del frontend para el enlace de recuperación de contraseña (por defecto, el primer origen de `FRONTEND_ORIGINS`) |
| `EMAIL_PROVIDER` | Cómo se envían los correos: `console` (solo log, por defecto), `smtp` o `brevo`. Ver `Backend/README.md` |

### Frontend (`Frontend/.env`)

Se crea copiando `Frontend/.env.example`:

| Variable | Para qué sirve |
|---|---|
| `VITE_API_BASE_URL` | URL del backend. En local: `http://localhost:8000` |
| `VITE_ENVIRONMENT` | Entorno de ejecución (`development` en local) |

> ⚠️ Nunca subas archivos `.env` al repositorio. Solo se versionan los `.env.example`.

---

## ✅ Funcionalidades

- **Cuentas y sesión:** registro, inicio de sesión con token JWT, bloqueo temporal tras 5 intentos fallidos y recuperación de contraseña por correo.
- **Multi-tenant:** cada estudio tiene sus integrantes, proyectos y archivos aislados; un usuario puede pertenecer a varios estudios.
- **Roles:** dueño, admin, developer, artista y tester, con permisos validados en el backend.
- **Tablero Kanban:** tareas de código y arte con asignación abierta o restringida, historial de cambios y restauración.
- **Bloqueo y versiones de archivos:** solo quien bloquea un archivo puede subir una nueva versión; descarga con URL firmada.
- **GitHub:** los commits con `#<id>` en el mensaje aparecen en la tarea (webhook firmado con HMAC).
- **Comentarios y notificaciones:** avisos al asignar, comentar, pasar a revisión o liberar un bloqueo.
- **Resumen, Asset Vault y Build History:** avance del proyecto, carga por integrante y registro de builds.
- **Administración:** editar o eliminar estudio, proyectos y tareas, y bitácora de actividad.
- **Versión para celular.**

---

## 🧪 Pruebas

```bash
cd Backend
pip install -r requirements-dev.txt
pytest
```

```bash
cd Frontend
npm run lint
npm run build
```

---

## 🛟 Problemas comunes

| Problema | Solución |
|---|---|
| El backend no arranca: `SECRET_KEY must be set...` | Define `SECRET_KEY` con `openssl rand -hex 32` antes de `uvicorn` |
| "No se pudo conectar con el backend" | El backend no está corriendo, usa otro puerto o (en Render) está despertando; espera unos segundos y reintenta |
| Error de CORS en la consola del navegador | Agrega el origen exacto del frontend a `FRONTEND_ORIGINS` (sin `/` al final) |
| `VITE_API_BASE_URL` sale `undefined` | Debe empezar con `VITE_` y hay que reiniciar `npm run dev` |
| "No se pudo guardar el archivo" | Revisa `ASSET_STORAGE_PROVIDER` y sus credenciales; para probar en local usa `local` |
| Puerto 5173 ocupado | Vite usa el siguiente (5174); agrégalo a `FRONTEND_ORIGINS` |

---

## ☁️ Producción

- **Frontend (Vercel):** https://indiedev-pipeline-frontend.vercel.app. En Vercel, `VITE_API_BASE_URL` apunta a la URL pública del backend en Render, y hay que volver a desplegar si cambia.
- **Backend (Render):** `Backend` como Root Directory, comando de compilación `pip install -r requirements.txt && alembic upgrade head`, comando de inicio `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, con `SECRET_KEY`, `DATABASE_URL`, `FRONTEND_ORIGINS` y las variables del almacenamiento configuradas. La URL `postgres://...` que entrega Render funciona tal cual. Detalle en `Backend/README.md`.
