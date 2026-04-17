# KBS Bridge Management System

## Overview
A production-grade identity reporting integration system for hotels in Turkey. It bridges cloud-based Hotel Property Management Systems (PMS) with the Turkish Identity Reporting System (KBS), automating the reporting of Turkish citizens (TC Kimlik) and foreign nationals (Passports) to Turkish authorities (EGM/Jandarma).

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Radix UI (Shadcn-style), React Router 7, React Hook Form, Zod, Axios
- **Backend**: FastAPI (Python), MongoDB (motor async driver), JWT authentication, Fernet encryption, APScheduler
- **Build**: craco (Create React App Configuration Override) for frontend, uvicorn for backend
- **Database**: MongoDB (v7.0) running locally on port 27017

## Architecture
- `frontend/` - React application (port 5000)
- `backend/` - FastAPI application (port 8000)
- API requests from frontend are proxied from port 5000 to backend port 8000 via craco devServer proxy

## Key Files
- `frontend/src/lib/api.js` - Axios API client, proxies to `/api` (backend)
- `frontend/craco.config.js` - Webpack config with proxy, host=0.0.0.0, port=5000, allowedHosts=all
- `backend/server.py` - Main FastAPI application (~1500 lines)
- `backend/auth.py` - JWT + RBAC authentication
- `backend/models.py` - Pydantic models + MongoDB schemas
- `backend/kbs_simulator.py` - Simulated SOAP/XML KBS endpoint
- `backend/agent_runtime.py` - Simulated local bridge agent
- `start_frontend.sh` - Startup script: starts MongoDB, backend on port 8000, frontend on port 5000

## Environment Variables
- `MONGO_URL` - MongoDB connection string (default: `mongodb://localhost:27017`)
- `DB_NAME` - MongoDB database name (default: `kbs_bridge_system`)
- `JWT_SECRET` - JWT signing secret
- `REACT_APP_BACKEND_URL` - Backend URL for frontend (empty = use proxy)

## Running the App
The main workflow `Start application` runs `bash start_frontend.sh` which:
1. Starts MongoDB daemon (dbpath: /tmp/mongodb_data)
2. Starts FastAPI backend on localhost:8000
3. Starts React dev server on 0.0.0.0:5000

## Features
- Multi-tenant hotel onboarding and management
- Simulated local "Bridge Agent" for queue processing and KBS communication
- Role-Based Access Control (RBAC) with Admin, Manager, and Front Desk roles
- Credential vault with Fernet symmetric encryption
- KVKK (Turkish GDPR) compliance tools and observability dashboards
- Bilingual support (Turkish/English)
- KBS submission simulation with configurable modes (success/failure/delay)
