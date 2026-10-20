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
│  [ Vercel ]  ──────────>  [ Render ]  ──────────> [ Aiven ]  │
│  (Frontend)  Peticiones    (Backend)   Consultas    (MySQL)  │
│               HTTPS                     SQL                  │
│                                                              │
│                   └─────> [ Firebase ]                       │
│                           (Assets 3D / Builds)               │
└──────────────────────────────────────────────────────────────┘
```

* **Frontend:** React con Vite y Tailwind CSS, desplegado en Vercel.
* **Backend:** API REST con Python (FastAPI), desplegada en Render.
* **Base de Datos:** MySQL gestionado en la nube vía Aiven. En local, el backend usa SQLite si no se define `DATABASE_URL`.
* **Almacenamiento de Archivos:** Bucket desacoplado en Firebase / Amazon S3.

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
uvicorn app.main:app --reload
```

El backend queda en `http://localhost:8000`. La documentación interactiva de la API está en `http://localhost:8000/docs` y la ruta de prueba en `http://localhost:8000/health`.

Sin `DATABASE_URL`, el backend usa SQLite, así que **no necesitas instalar MySQL** para probar. Para conectar MySQL, ver `Backend/README.md`.

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
| `DATABASE_URL` | Conexión a la base de datos. Si no se define, usa SQLite local |
| `FRONTEND_ORIGINS` | Orígenes del frontend permitidos por CORS. Por defecto `http://localhost:5173` |

### Frontend (`Frontend/.env`)

Se crea copiando `Frontend/.env.example`:

| Variable | Para qué sirve |
|---|---|
| `VITE_API_BASE_URL` | URL del backend. En local: `http://localhost:8000` |
| `VITE_ENVIRONMENT` | Entorno de ejecución (`development` en local) |
| `VITE_TENANT_ID` | ID del estudio (tenant) con el que se hacen las pruebas; debe existir en el backend |
| `VITE_TENANT_HEADER_NAME` | Nombre del encabezado HTTP para enviar el tenant (`X-Tenant-ID`) |
| `VITE_USER_ID` | ID del usuario de prueba (para bloquear y liberar assets) |
| `VITE_ASSET_ID` | ID de un asset de prueba; debe existir en el backend |

> ⚠️ Nunca subas archivos `.env` al repositorio. Solo se versionan los `.env.example`.

---

## 🎨 Frontend: conexión con el backend local

### Cómo funciona la conexión

- La URL del backend se lee de `VITE_API_BASE_URL` en `Frontend/src/config/api.js`. Usa `API_BASE_URL` desde ahí en lugar de escribir URLs a mano.
- Si cambias el `.env`, detén `npm run dev` (Ctrl + C) y vuelve a correrlo. Vite solo lee las variables al arrancar.
- El indicador **"Conectado: indie-dev-pipeline-api"** del login y del header (componente `ApiStatus`) comprueba la ruta `/health` del backend.

### Qué está conectado hoy

- El login es una simulación: cualquier correo y contraseña entra.
- El tablero Kanban usa datos de ejemplo definidos en `Frontend/src/App.jsx`.
- **Lo único conectado al backend** es el botón de candado de la tarea `ART-105` (bloquear y liberar un asset). Usa `VITE_TENANT_ID`, `VITE_ASSET_ID` y `VITE_USER_ID`.

### Datos de prueba para el candado

Con el backend corriendo y la base vacía (SQLite):

1. Crea el estudio y su usuario propietario. Con base vacía quedan con id 1:
```bash
   curl -X POST http://localhost:8000/api/tenants \
     -H "Content-Type: application/json" \
     -d '{"name":"Estudio Demo","slug":"estudio-demo","owner_email":"demo@ejemplo.com"}'
```
2. Crea un proyecto y un asset de prueba desde `http://localhost:8000/docs`, con "Try it out" en `POST /api/tenants/1/projects` y luego en `POST /api/tenants/1/projects/1/assets`. Swagger llena un ejemplo con los campos exactos.
3. Deja el asset bloqueado, para que coincida con cómo aparece `ART-105` en pantalla:
```bash
   curl -X PATCH http://localhost:8000/api/tenants/1/assets/1/lock \
     -H "Content-Type: application/json" \
     -d '{"user_id":1}'
```
4. En `http://localhost:5173`, inicia sesión y presiona el candado de `ART-105`. Debe liberarse sin alert de error; si lo presionas de nuevo, se vuelve a bloquear.

### Problemas comunes

| Problema | Solución |
|---|---|
| "Sin conexión con el backend" | El backend no está corriendo o usa otro puerto |
| Error de CORS en la consola del navegador | Si el frontend corre en otro puerto, define `FRONTEND_ORIGINS` en el backend con ese origen exacto |
| `VITE_API_BASE_URL` sale `undefined` | Debe empezar con `VITE_` y hay que reiniciar `npm run dev` |
| "Asset no encontrado" al usar el candado | El asset con ese id no existe; revisa los datos de prueba |
| "Solo quien bloqueó el asset puede liberarlo" | El asset no está bloqueado en el backend; haz el paso 3 de los datos de prueba |
| Puerto 5173 ocupado | Vite usa el siguiente (5174); agrégalo a `FRONTEND_ORIGINS` |

---

## ☁️ Producción

- **Frontend (Vercel):** https://indiedev-pipeline-frontend.vercel.app. En Vercel, `VITE_API_BASE_URL` apunta a la URL pública del backend en Render, y hay que volver a desplegar si cambia.
- **Backend (Render):** `Backend` como Root Directory, comando de inicio `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, con `DATABASE_URL` y `FRONTEND_ORIGINS` configuradas. Detalle en `Backend/README.md`.