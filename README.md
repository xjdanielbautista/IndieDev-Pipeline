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

El proyecto está diseñado bajo un modelo **SaaS Multi-Tenant** que garantiza el aislamiento de datos por estudio mediante un discriminador tenant_id en la capa de datos.

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

* **Frontend:** Desarrollado en React con Tailwind CSS y desplegado en Vercel.
* **Backend:** API REST construida con Python (FastAPI) y desplegada en Render.
* **Base de Datos:** Instancia gestionada de MySQL en la nube vía Aiven.
* **Almacenamiento de Archivos:** Bucket desacoplado en Firebase / Amazon S3.

---

## 📂 Estructura del Repositorio

```
indiedev-pipeline/
├── frontend/             # Código fuente de la interfaz de usuario (React)
├── backend/              # API REST, endpoints y scripts de base de datos (FastAPI)
├── docs/                 # Manual Técnico de Arquitectura y documentación
└── README.md             # Documentación principal del proyecto
```
---

## 🛠️ Requisitos Previos

Para ejecutar el proyecto en un entorno local de desarrollo (Dev), necesitas tener instalado:

* Node.js (v18.0 o superior)
* Python (v3.10 o superior)
* Git

---

## 🚀 Guía de Instalación y Ejecución Local

### 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/indiedev-pipeline.git
cd indiedev-pipeline

### 2. Configurar y levantar el Backend (FastAPI)
cd backend
python -m venv venv

## En Windows:
venv\Scripts\activate

## En Linux/Mac:
source venv/bin/activate

---
pip install -r requirements.txt
uvicorn main:app --reload

El servidor Backend estará disponible en: http://localhost:8000

### 3. Configurar y levantar el Frontend (React)
En una nueva terminal:
cd frontend
npm install
npm run dev

El cliente Frontend estará disponible en: http://localhost:5173

---

## 🔑 Variables de Entorno

Asegúrate de crear los archivos .env correspondientes en las carpetas de backend/ y frontend/ antes de ejecutar la aplicación.

### Backend (backend/.env)
- DB_HOST=mysql-11d77a0d-indiedev-pipeline.c.aivencloud.com
- DB_PORT=26900
- DB_USER=avnadmin
- DB_PASSWORD=your_password_here
- DB_NAME=defaultdb
- SECRET_KEY=your_jwt_secret_key

### Frontend (frontend/.env)
VITE_API_BASE_URL=http://localhost:8000

---
