# PRD: KBS Bridge Management System

## Problem Statement
Production-grade identity reporting integration system for hotels in Turkey. Integrates a cloud-based Hotel PMS with the Turkish Identity Reporting System (KBS). Currently a **simulation** of the real-world architecture.

## Core Requirements
- **KBS Integration**: Simulated SOAP/XML endpoint (not connected to real EGM/Jandarma)
- **Bridge Agent**: Simulated local agent runtime with web management dashboard
- **Data Scope**: Turkish citizens (TC Kimlik) + foreign nationals (Passports)
- **Authentication**: RBAC with Admin, Hotel Manager, Front Desk roles
- **Multi-Tenancy**: Hotel-based tenant structure with onboarding flow
- **Security**: No e-Devlet passwords collected; credential vault for service credentials only
- **Language**: Bilingual (Turkish default, English)

## Architecture
- **Stack**: FastAPI + React + MongoDB (FARM)
- **Model**: Cloud Dashboard + Simulated Local Agent + Multi-Tenancy
- **Auth**: JWT + bcrypt + RBAC middleware
- **Encryption**: Fernet symmetric encryption for credential vault

## Completed Phases
- **Phase 1**: Core pipeline (check-in → validation → queue → KBS → ack/retry/quarantine)
- **Phase 2**: V1 polish (data-testid, race condition fix, navigation stability)
- **Phase 3**: RBAC, multi-tenancy, hotel onboarding, credential vault, user management
- **Phase 4**: Observability, go-live checklists, KVKK compliance, deployment guide

## Key Credentials
- Admin: admin@kbsbridge.com / admin123
- Manager: manager@grandistanbul.com / manager123
- Front Desk: resepsiyon@grandistanbul.com / front123

## Simulation Notice
KBS SOAP endpoint and Bridge Agent are internal simulators. Real KBS integration requires connection to actual EGM/Jandarma endpoints.

## P0 Backlog
- Threshold-based alerting system (queue depth, heartbeat, quarantine spikes)
- Diagnostic bundle download
- Real KBS SOAP client implementation

## P1 Backlog
- Time-series analytics charts
- Per-hotel comparison dashboards
- SLA tracking and reporting
- Notification system for admins

## P2 Backlog
- Compact table mode
- Global search (Command)
- Certificate-based auth for production KBS
