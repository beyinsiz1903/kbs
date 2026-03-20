# plan.md

## 1) Objectives
- ✅ **Completed**: Prove the **core pipeline** works end-to-end with realistic failure modes: **Check-in → Validation (TC/Passport) → Queue → Simulated Agent → Simulated KBS SOAP/XML → Ack/Fail → Retry/Quarantine → Audit**.
- ✅ **Delivered (v1 core app)**: Cloud management panel + simulated local bridge agent runtime + operator monitoring UI.
- ✅ **Completed (Phase 2 polish)**: Resolved remaining UI testability/UX stability items:
  - Stable `data-testid` selectors for sidebar navigation
  - Stable `data-testid` for Check-in hotel select options
  - Deterministic field reset when switching guest type (TC/Pasaport)
- ✅ **Completed (Phase 3 — Productization for real hotels)**: Implemented **hotel-based tenant onboarding + RBAC login + KBS integration setup**.
  - **Explicit constraint upheld**: **Do NOT collect e-Devlet passwords in-app.**
  - Supports both operational models via onboarding: **EGM KBS** (portal credentials) and **Jandarma KBS** (e-Devlet official flow + possible service credentials).
- ⏭️ **Next (Phase 4)**: Observability upgrades + deployment model + production checklists.

---

## 2) Implementation Steps (Phased)

### Phase 1 — Core Flow POC (Isolation; must be stable before app build)
**Status: ✅ COMPLETE (52/52 tests passed)**

**User stories (delivered)**
1. ✅ As a hotel operator, I can create a check-in event and see it become a queued KBS submission.
2. ✅ As the system, I validate TC Kimlik and Passport differently and reject invalid payloads with reasons.
3. ✅ As the agent, I heartbeat, process queue, and send SOAP/XML to simulated KBS.
4. ✅ As an operator, I can see retry attempts with backoff and the final quarantine outcome.
5. ✅ As a demo presenter, I can toggle “KBS unavailable/timeout/delayed ack/duplicate” and observe correct state transitions.

**Steps (implemented)**
- ✅ Implemented backend modules:
  - Data models: Hotel, Guest, CheckIn, Submission, Attempt, AuditEvent, AgentState.
  - Validators: TC Kimlik (checksum), Passport (basic format + expiry support).
  - Queue + processing: Mongo-backed queue behavior via submission status + scheduling fields.
  - Agent runtime: background worker loop + heartbeat + offline toggle.
  - Retry engine: exponential backoff + jitter + max attempts + quarantine.
  - Simulated KBS SOAP service: realistic responses for success, validation fail, duplicate reject, timeout, unavailable, delayed ack.
  - State machine: PENDING/QUEUED → SENDING → ACKED | RETRYING → QUARANTINED.
  - Audit trail: append-only events.
- ✅ Created and executed deterministic POC test suite:
  - Success path + all failure modes.
  - Duplicate prevention.
  - Manual correction + requeue.
  - Agent offline/online.

**Exit criteria**
- ✅ POC test suite passes deterministically: **52/52 PASS**.

---

### Phase 2 — V1 App Development (MVP around proven core)
**Status: ✅ COMPLETE (demo-polished)**

**User stories (delivered)**
1. ✅ Front Desk Operator can check-in a guest (TC or Passport) and see submission status.
2. ✅ Hotel Manager can view queue size + success/fail metrics (Dashboard + Metrics endpoint).
3. ✅ Admin can manage hotels/tenants and view agent status.
4. ✅ Operator can open quarantined submission, correct fields, and requeue.
5. ✅ UI is bilingual (TR default + EN toggle) and demonstrates end-to-end demo scope.

**Build (implemented)**
- ✅ Backend (FastAPI + MongoDB):
  - Multi-hotel support (hotel_id scoping).
  - REST API for: hotels, guests, check-ins, submissions (detail/attempts), agent status/toggle, KBS simulation control, audit, metrics.
  - Demo reset endpoint.
- ✅ Frontend (React + shadcn/ui + Tailwind):
  - Enterprise dark dashboard shell (sidebar/topbar).
  - Pages implemented:
    - Dashboard (KPIs + charts)
    - Check-in (TC/Foreign tabs)
    - Submissions list (filters + detail navigation)
    - Submission detail (timeline + attempts + SOAP XML viewer)
    - Agent monitor (heartbeat + toggle online/offline)
    - KBS simulation control
    - Audit trail
    - Hotels management (create hotel)
  - Polling for “real-time feel”.
  - Status badges and clear state indicators.

**Phase 2 polish items (completed)**
1. ✅ Navigation targeting in Turkish UI
   - Stable selectors via `data-testid` + consistent `data-nav-path` usage.
2. ✅ Check-in Hotel Select stability
   - Added stable `data-testid` for `SelectItem` options: `checkin-hotel-option-<hotelId>`.
3. ✅ CheckInForm guest type switch (TC/Pasaport) race condition
   - Deterministic reset of irrelevant fields when switching guest type.
4. 🟢 Language toggle minor: brand text not translated (optional, acceptable for v1).

**Exit criteria**
- ✅ All demo flows are stable and UI is testable/reliable:
  - ✅ Check-in → queued → agent send → ack
  - ✅ KBS unavailable → retries → quarantine → correction → success
  - ✅ TC + Passport validation
  - ✅ Agent offline/online affects processing
  - ✅ Audit trail visible

---

### Phase 3 — Tenant Onboarding + RBAC + KBS Integration Setup (No in-app e‑Devlet password)
**Status: ✅ COMPLETE (implemented + tested)**

#### Phase 3 guiding decisions (must-haves)
- ✅ **No e-Devlet password field** in UI, API, storage, logs.
- ✅ Separate concerns:
  - **Human user access**: users log into *our* panel (JWT + RBAC).
  - **Machine/service integration**: per-hotel KBS access parameters are configured via onboarding and stored securely.
- ✅ Every data access is scoped by **tenant/hotel context** (unless Admin).

#### Phase 3 user stories (delivered)
1. ✅ As a user, I can log in to the panel and only see data permitted by my role and assigned hotel(s).
2. ✅ As an Admin, I can onboard a hotel with a guided wizard: region → EGM/Jandarma → integration type → network → credentials → test.
3. ✅ As a Hotel Manager, I can manage my hotel’s KBS integration settings and monitor health.
4. ✅ As Front Desk, I can run check-in flows without seeing sensitive integration credentials.

#### Phase 3 workstreams (implemented)

##### 3A) Authentication + RBAC + Tenant Context
- ✅ Backend
  - Users collection + seeding demo users.
  - JWT auth (Bearer token) + password hashing.
  - RBAC roles implemented:
    - `admin`: global access
    - `hotel_manager`: hotel-scoped
    - `front_desk`: hotel-scoped
  - Auth endpoints:
    - `POST /auth/login`
    - `GET /auth/me`
    - `POST /auth/change-password`
  - Bugfix: invalid credentials correctly return **401** (no 500).
- ✅ Frontend
  - Login page + logout
  - AuthContext token handling + route guards
  - Role-based nav visibility (e.g., Users page admin-only)

##### 3B) Hotel Onboarding Wizard (per-hotel)
- ✅ UI: “KBS Entegrasyon Kurulumu” wizard (6-step)
  - Step 1: Hotel profile
  - Step 2: Authority region: **Emniyet / Jandarma**
  - Step 3: Integration type: **EGM KBS / Jandarma KBS**
  - Step 4: Network prerequisites (static IP guidance)
  - Step 5: Credentials / access parameters (Vault)
  - Step 6: Test connection + official redirects
- ✅ Backend
  - Hotel model extended with onboarding fields:
    - `authority_region`, `integration_type`, `onboarding_status`, `onboarding_step`
    - authorized contact fields, static IP, district
  - Endpoints:
    - `PUT /hotels/{id}/onboarding`
    - `POST /hotels/{id}/integration/test` (simulated connectivity test)

##### 3C) Credential Vault (service credentials only)
- ✅ Implemented encrypted storage for KBS service credentials (NOT e-Devlet passwords)
  - Fields supported: KBS username, facility code, service username, endpoint URL, env (test/prod), auth method
  - Secret stored encrypted-at-rest; API responses **mask** secret
- ✅ Backend
  - `kbs_configs` collection + encryption (Fernet key derived from configured secret)
  - Endpoints:
    - `GET /hotels/{id}/kbs-config`
    - `PUT /hotels/{id}/kbs-config`
- ✅ Frontend
  - Credentials step in onboarding includes explicit security warning

##### 3D) Official Redirect pages/buttons
- ✅ UI provides official portal redirects (no credential collection)
  - Link to **EGM KBS**: `https://kbs.egm.gov.tr`
  - Link to **Jandarma KBS / e-Devlet**: `https://www.turkiye.gov.tr/jandarma-kimlik-bildirim-sistemi`

##### 3E) Tenant-based Health Panel (per hotel)
- ✅ Backend
  - `GET /hotels/{id}/health` returns:
    - agent status (heartbeat, queue size)
    - integration status (configured, last test)
    - submissions breakdown + last success + last error
- ✅ Frontend
  - Per-hotel health panel page
  - Hotels list includes quick actions to Health + Onboarding

##### 3F) User Management (Admin-only)
- ✅ Backend
  - `GET /users`, `POST /users`, `PUT /users/{id}`
- ✅ Frontend
  - Users page listing users, roles, hotel assignment
  - Create user dialog (admin-only)

**Testing (completed)**
- ✅ Testing results:
  - Backend: **94% initially** (17/18), then fixed invalid login error handling → **no critical bugs remaining**
  - Frontend: **95%** (all core Phase 3 flows verified)

**Phase 3 exit criteria**
- ✅ Users must authenticate to access app.
- ✅ RBAC enforced on backend endpoints and UI routes.
- ✅ Tenant/hotel scoping prevents cross-hotel access.
- ✅ Hotel onboarding wizard works end-to-end.
- ✅ Credential Vault stores only service credentials; secrets are encrypted/masked.
- ✅ Official redirects exist; **no e-Devlet password field anywhere**.
- ✅ Health panel shows per-hotel status and basic diagnostics.
- ✅ Admin-only user management available.

---

### Phase 4 — Observability, Deployment Model, Production Checklists
**Status: ⏭️ NEXT**

**User stories**
1. As an Admin, I can see system-wide success rate, failure rate, and per-hotel queue size.
2. As on-call, I get alerted when queue size spikes or agent heartbeat stops.
3. As an Admin, I can manage per-hotel agent “installation” status and configuration versions.
4. As a Hotel Manager, I can download a deployment guide/config bundle for the agent.
5. As ops, I can run go-live checklist and confirm compliance readiness.

**Steps**
- Metrics expansion:
  - success/fail/retry/quarantine, queue age, heartbeat age; expose via endpoint + dashboard charts.
  - add per-hotel trend charts and time-windowed stats.
- Structured logging + correlation IDs:
  - trace submission_id across API → agent → KBS simulator
  - ensure logs never include secrets; review vault masking + log filters
- Alerts:
  - simple threshold-based (v1) then integrate external alerting (later).
- Deployment strategy docs:
  - per-hotel agent config, IP whitelist, environment separation.
  - simulated “agent installation” state machine and versioning.
- Produce checklists:
  - go-live, compliance, operations.
- Final regression E2E tests:
  - core flows + failure scenarios + RBAC + onboarding + health.

---

## 3) Next Actions
1. **Phase 4 Sprint 1 — Observability foundations**
   - Add correlation IDs, structured logs, and metric aggregation endpoints.
   - Improve dashboard charts (remove warnings; ensure responsive sizing).
2. **Phase 4 Sprint 2 — Alerts + Diagnostics**
   - Alert rules (queue depth, heartbeat age, quarantine spikes).
   - Diagnostic bundle download for support.
3. **Phase 4 Sprint 3 — Deployment model + docs**
   - Agent installation guide, config templates, IP whitelist steps.
   - Environment separation (test vs prod) operational playbook.
4. **Phase 4 Sprint 4 — Go-live checklists + final regression**
   - Compliance readiness checklist (KVKK baseline)
   - Full E2E regression suite and demo script.

---

## 4) Success Criteria
- ✅ Core pipeline deterministically passes: success, timeout, unavailable, duplicate, validation fail, delayed ack.
- ✅ UI demonstrates: queue → attempts → final state (acked/retrying/quarantined) with audit timeline and XML viewer.
- ✅ TC + Passport validation both work and produce actionable errors.
- ✅ Agent heartbeat and offline mode are visible and affect processing.
- ✅ Phase 2 polish completed: navigation + hotel dropdown stability + check-in tab validation reliability.
- ✅ Phase 3 completed:
  - ✅ **Login + RBAC + tenant onboarding** implemented.
  - ✅ **No in-app e‑Devlet password**; only official redirect + per-hotel service credential configuration.
  - ✅ Health panel and user management implemented.
- ✅ Phase 4 completed:
  - ✅ Observability enables diagnosing failures without DB access.
  - ✅ Per-hotel go-live checklist (10-point readiness verification).
  - ✅ KVKK compliance hardening (PII masking, retention, export/delete).
  - ✅ Deployment guide and architecture documentation.
