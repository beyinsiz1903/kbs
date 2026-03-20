# plan.md

## 1) Objectives
- ✅ **Completed**: Prove the **core pipeline** works end-to-end with realistic failure modes: **Check-in → Validation (TC/Passport) → Queue → Simulated Agent → Simulated KBS SOAP/XML → Ack/Fail → Retry/Quarantine → Audit**.
- ✅ **Delivered (v1 core app)**: Cloud management panel + simulated local bridge agent runtime + operator monitoring UI.
- 🟡 **In progress (Phase 2 hardening)**: Fix minor frontend UX/testability issues (navigation targeting, Check-in hotel Select stability) to reach “demo-polished” level.
- ⏭️ **Next (Phase 3 — Productization for real hotels)**: Implement **hotel-based tenant onboarding + RBAC login + KBS integration setup**.
  - **Explicit constraint**: **Do NOT collect e-Devlet passwords in-app.**
  - Support both operational models via onboarding: **EGM KBS** (portal credentials) and **Jandarma KBS** (e-Devlet access / official flow + potential web-service credentials).
- ⏭️ Later: Observability upgrades + deployment model + production checklists.

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
**Status: 🟡 NEARLY COMPLETE**
- Backend: ✅ 100% functional (testing agent: 21/21 API tests passed)
- Frontend: 🟡 ~75–90% (core flows work; a few UX/testability items remain)

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

**Testing (completed)**
- ✅ Automated POC script confirms pipeline behavior.
- ✅ Testing agent results:
  - Backend: **100%**
  - Frontend: core scenarios pass; minor UI targeting issues.

**Known issues to fix (Phase 2 polish)**
1. 🟡 Navigation targeting in Turkish UI (timeouts when selecting some TR labels)
   - Current state: `data-testid` exists on nav links; needs verification with E2E selectors.
   - Fix: ensure stable selectors for sidebar items across TR/EN and mobile/desktop.
2. 🟡 Check-in Hotel Select stability
   - Fix: add stable `data-testid` for `SelectItem` options (e.g., `checkin-hotel-option-<hotelId>`), and ensure selection can be reliably automated.
3. 🟡 CheckInForm guest type switch (TC/Pasaport) potential race condition
   - Fix: ensure tab switch resets irrelevant fields deterministically; avoid stale required validation on hidden inputs.
4. 🟢 Language toggle minor: brand text not translated (acceptable for v1) → optional.

**Revised Phase 2 exit criteria**
- All demo flows are stable *and* UI is testable/reliable:
  - ✅ Check-in → queued → agent send → ack
  - ✅ KBS unavailable → retries → quarantine → correction → success
  - ✅ TC + Passport validation
  - ✅ Agent offline/online affects processing
  - ✅ Audit trail visible
  - 🟡 Fix remaining UI targeting issues (nav + hotel select) and eliminate Check-in tab/validation flakiness

---

### Phase 3 — Tenant Onboarding + RBAC + KBS Integration Setup (No in-app e‑Devlet password)
**Status: ⏭️ NEXT (re-scoped based on product decision)**

#### Phase 3 guiding decisions (must-haves)
- **No e-Devlet password field** in UI, API, storage, logs.
- Separate concerns:
  - **Human user access**: users log into *our* panel (JWT + RBAC).
  - **Machine/service integration**: per-hotel KBS access parameters are configured via onboarding and stored securely.
- Every data access is scoped by **tenant/hotel context** (unless Admin).

#### Phase 3 user stories
1. As a user, I can log in to the panel and only see data permitted by my role and assigned hotel(s).
2. As an Admin, I can onboard a hotel with a guided wizard: region → EGM/Jandarma → integration type → agent assignment → credentials → test.
3. As a Hotel Manager, I can manage my hotel’s KBS integration settings and monitor health.
4. As Front Desk, I can run check-in flows without seeing sensitive integration credentials.
5. As Support/IT (optional role), I can assist setup and view health diagnostics without broad PII exposure.
6. As Compliance (optional role), I can export audit trails and view data access logs.

#### Phase 3 workstreams

##### 3A) Authentication + RBAC + Tenant Context
- Backend
  - Add **users collection** and CRUD (admin-only for creation/invite in v1).
  - Implement JWT auth (access token) + password hashing.
  - Add authorization dependencies:
    - `Admin`: global access.
    - `Hotel Manager` / `Front Desk`: hotel-scoped access.
    - Optional roles: `Compliance`, `IT Support`.
  - Update all endpoints to enforce:
    - `hotel_id` scoping on reads/writes.
    - entity ownership (e.g., submissions belong to hotel).
  - Add audit events for data access where necessary (Phase 3.5 KVKK section).
- Frontend
  - Add **Login page** (email/password) + logout.
  - Route guards + role-based nav visibility.
  - Tenant context handling:
    - If user has one hotel → auto-select.
    - If multiple hotels → prompt/select (topbar switcher).

##### 3B) Hotel Onboarding Wizard (per-hotel)
- UI: “KBS Entegrasyon Kurulum” wizard (Admin/Hotel Manager)
  - Step 1: Hotel profile (name, tax, city, address, authorized person)
  - Step 2: Authority region: **Emniyet / Jandarma** (or hybrid)
  - Step 3: Integration type: **EGM KBS / Jandarma KBS**
  - Step 4: Network prerequisites: static IP, IP whitelist guidance
  - Step 5: Agent assignment/status (bridge agent installed? simulated now, real later)
  - Step 6: Credentials / access parameters (see Vault below)
  - Step 7: Test connection / test submission
  - Step 8: Summary + state transitions
- Backend
  - Extend `Hotel` model with onboarding fields:
    - `authority_region` (egm/jandarma/hybrid)
    - `integration_type`
    - `onboarding_status` and timestamps
    - `authorized_contact` fields
  - Endpoint(s):
    - `POST/PUT /hotels/{id}/onboarding` (wizard step save)
    - `POST /hotels/{id}/integration/test` (connectivity + auth sanity checks)

##### 3C) Credential Vault (service credentials only)
- Core requirement: store **officially issued** access parameters for integration (NOT e-Devlet passwords).
- Fields (example; per integration type)
  - KBS username / facility code / service user
  - secret: password/token
  - certificate/key uploads (future: file store; now: base64/placeholder)
  - endpoint URL
  - environment: test/prod
  - whitelisted IPs
- Backend
  - New model(s): `KbsIntegrationConfig` (per hotel)
  - Encryption-at-rest strategy:
    - app-level field encryption for secrets (token/password/private key)
    - ensure secrets never appear in logs/audit payloads
  - Endpoints:
    - `GET/PUT /hotels/{id}/kbs-config`
    - `POST /hotels/{id}/kbs-config/rotate-secret`
- Frontend
  - “Credential Vault” page/tab:
    - masked secret fields
    - rotate/update flow
    - view permissions restricted (Admin + Hotel Manager; never Front Desk)

##### 3D) Official Redirect pages/buttons
- UI provides **official portal redirect** actions without collecting credentials:
  - Button: “EGM KBS giriş sayfasına git”
  - Button: “Jandarma KBS / e‑Devlet doğrulama sayfasına git”
- Copy & guidance section:
  - After completing official authorization, return and input issued integration parameters into Vault.
- No callback-based OAuth assumed unless official flow supports it; treat as informational redirect.

##### 3E) Tenant-based Health Panel (per hotel)
- UI (Hotel Manager/Admin)
  - Agent online/offline + last heartbeat
  - last successful connection test
  - last successful submission / last error
  - queue depth, quarantine count
- Backend
  - Add per-hotel health summary endpoint:
    - `GET /hotels/{id}/health`

##### 3F) KVKK/Compliance hardening (Phase 3.5)
- PII masking by role (e.g., Front Desk sees minimal, Compliance sees more, Admin as needed).
- Retention policy + anonymization/deletion job.
- Data access audit events (who viewed what; avoid storing raw PII in audit payloads).

**Phase 3 exit criteria**
- ✅ Users must authenticate to access app.
- ✅ RBAC enforced on backend endpoints and UI routes.
- ✅ Tenant/hotel scoping prevents cross-hotel access.
- ✅ Hotel onboarding wizard works end-to-end.
- ✅ Credential Vault stores only service credentials; secrets are encrypted/masked.
- ✅ Official redirects exist; **no e-Devlet password field anywhere**.
- ✅ Health panel shows per-hotel status and basic diagnostics.

---

### Phase 4 — Observability, Deployment Model, Production Checklists
**Status: ⏭️ LATER**

**User stories**
1. As an Admin, I can see system-wide success rate, failure rate, and per-hotel queue size.
2. As on-call, I get alerted when queue size spikes or agent heartbeat stops.
3. As an Admin, I can manage per-hotel agent “installation” status and configuration versions.
4. As a Hotel Manager, I can download a deployment guide/config bundle for the agent.
5. As ops, I can run go-live checklist and confirm compliance readiness.

**Steps**
- Metrics: success/fail/retry/quarantine, queue age, heartbeat age; expose via endpoint + dashboard charts.
- Structured logging + correlation IDs; extend audit/data-access logs.
- Alerts: simple threshold-based (v1) then integrate external alerting (later).
- Deployment strategy docs:
  - Per-hotel agent config, IP whitelist, environment separation.
  - Simulated “agent installation” state machine and versioning.
- Produce checklists: go-live, compliance, operations.
- Final regression E2E tests (core flows + failure scenarios + RBAC + onboarding).

---

## 3) Next Actions
1. **Finish Phase 2 polish**
   - Verify sidebar nav `data-testid` selectors across TR/EN; fix any missing/unstable ones.
   - Stabilize Check-in hotel Select targeting: add `data-testid` to each option item.
   - Remove Check-in tab/required-field race: reset irrelevant fields on guest type switch; ensure hidden fields are not required.
2. Re-run lightweight UI E2E verification (manual + automated smoke) to confirm 100% demo stability.
3. Start **Phase 3 Sprint 1 (Auth + RBAC)**
   - Backend JWT + users + RBAC middleware
   - Frontend login page + guards + role-based nav
4. Phase 3 Sprint 2 (Hotel Onboarding Wizard)
   - Wizard UI + onboarding endpoints + onboarding status model
5. Phase 3 Sprint 3 (Credential Vault + Test Connection + Official Redirect)
   - Secure secret storage + masked UI
   - Test connection endpoint
   - Official redirects + guidance screen
6. Phase 3 Sprint 4 (Health Panel + KVKK baseline)
   - Hotel health endpoint + UI
   - PII masking + retention scaffolding + access audit events

---

## 4) Success Criteria
- ✅ Core pipeline deterministically passes: success, timeout, unavailable, duplicate, validation fail, delayed ack.
- ✅ UI demonstrates: queue → attempts → final state (acked/retrying/quarantined) with audit timeline and XML viewer.
- ✅ TC + Passport validation both work and produce actionable errors.
- ✅ Agent heartbeat and offline mode are visible and affect processing.
- 🟡 Phase 2 polish: navigation + hotel dropdown stability + check-in tab validation reliability.
- ⏭️ Phase 3: **Login + RBAC + tenant onboarding** and **KBS integration setup** implemented.
- ⏭️ Phase 3: **No in-app e‑Devlet password**; only official redirect + per-hotel service credential configuration.
- ⏭️ Phase 3: KVKK-oriented controls reduce PII exposure and add access logging.
- ⏭️ Phase 4: Observability enables diagnosing failures without DB access; deployment and checklists ready for go-live.
