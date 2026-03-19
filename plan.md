# plan.md

## 1) Objectives
- Prove the **core pipeline** works end-to-end with realistic failure modes: **Check-in → Validation (TC/Passport) → Queue → Simulated Agent → Simulated KBS SOAP/XML → Ack/Fail → Retry/Quarantine → Audit**.
- Deliver a v1 MVP web app: multi-tenant hotel PMS backend, agent monitoring, operator UI for failures, bilingual UI (TR default + EN).
- Add production-minded foundations: KVKK-oriented data handling, RBAC (Admin/Hotel Manager/Front Desk), observability (metrics/logs), deployment/config model (per-tenant agent + IP whitelist).

## 2) Implementation Steps (Phased)

### Phase 1 — Core Flow POC (Isolation; must be stable before app build)
**User stories**
1. As a hotel operator, I can create a check-in event and see it become a queued KBS submission.
2. As the system, I validate TC Kimlik and Passport differently and reject invalid payloads with reasons.
3. As the agent, I heartbeat, process queue, and send SOAP/XML to simulated KBS.
4. As an operator, I can see retry attempts with backoff and the final quarantine outcome.
5. As a demo presenter, I can toggle “KBS unavailable/timeout/delayed ack/duplicate” and observe correct state transitions.

**Steps**
- Web search: best practices for **idempotency keys**, **exponential backoff**, SOAP/XML fault modeling, and audit logging patterns.
- Implement POC-only modules in backend (no auth/UI yet):
  - Data models: Guest, CheckIn, Submission, Attempt, AuditEvent, AgentState.
  - Validators: TC Kimlik (format + checksum), Passport (country-aware minimal rules).
  - Queue: Mongo-backed queue collection with leasing/lock.
  - Agent runtime: background worker loop + heartbeat + offline toggle.
  - Retry engine: exponential backoff w/ jitter, max attempts, quarantine threshold.
  - Simulated KBS SOAP service: request parser + response generator (success, validation fail, duplicate reject, timeout, delayed ack).
  - State machine: PENDING → SENDING → ACKED | FAILED(RETRYING) | QUARANTINED.
  - Audit trail: immutable append-only events.
- Create a **standalone Python test script** (runs against FastAPI endpoints) that:
  - Generates sample TC + Passport check-ins.
  - Forces each failure scenario and verifies resulting states.
  - Verifies idempotency/duplicate prevention.
- Fix until POC passes deterministically (repeat runs; no flaky timing).

**Exit criteria**
- Script proves: success path + each failure mode leads to expected state, retries, quarantine, and audit entries.

---

### Phase 2 — V1 App Development (MVP around proven core)
**User stories**
1. As a Front Desk Operator, I can check-in a guest (TC or Passport) and immediately see submission status.
2. As a Hotel Manager, I can view queue size, success/fail rates, and quarantine count for my hotel.
3. As an Admin, I can manage hotels/tenants and their agent configuration (IP whitelist, toggles).
4. As an operator, I can open a failed/quarantined submission, correct fields, and requeue.
5. As a viewer, I can switch TR/EN and the UI defaults to Turkish.

**Build**
- Backend (FastAPI + MongoDB):
  - Multi-tenant structure (tenant_id scoping everywhere).
  - REST API for check-ins, submissions, agent status, quarantine actions, audit queries.
  - Configuration endpoints: per-tenant KBS simulation settings + agent toggles.
  - Basic KVKK approach: minimize stored PII, field-level masking in responses, retention flags.
- Frontend (React + shadcn/ui):
  - Pages: Login placeholder (disabled for now), Dashboard, Check-in form, Submissions list, Submission detail (attempts + audit), Agent status.
  - Real-time-ish updates via polling (v1) for agent heartbeat + queue.
  - Bilingual i18n (TR default) with consistent labels/errors.
- Demo controls (admin-only screen for now without auth):
  - Toggle KBS modes: unavailable/timeout/delayed ack/duplicate/validation fault.
  - Toggle agent offline/online.

**Testing (end of phase)**
- 1 E2E run: create TC + Passport check-ins → see queued → agent sends → success.
- 1 E2E run: force KBS unavailable → observe retries → quarantine → manual fix → requeue → success.

**Exit criteria**
- V1 UI fully demonstrates must-have demo scope with stable backend behavior.

---

### Phase 3 — Security, RBAC, Compliance Hardening + Better Ops UX
**User stories**
1. As a user, I can log in and only see data permitted by my role and hotel.
2. As an Admin, I can assign roles to users and invite hotel staff.
3. As a Compliance Officer (optional), I can export audit trails and view data access logs.
4. As a Hotel Manager, I can restrict who can edit/quarantine/requeue submissions.
5. As support, I can view agent logs/metrics to debug failures quickly.

**Steps**
- Implement JWT auth + RBAC (Admin/Hotel Manager/Front Desk) with tenant scoping.
- Enforce authorization on all endpoints + UI route guards.
- KVKK enhancements:
  - PII masking by role, encryption-at-rest strategy (app-level field encryption) for sensitive fields.
  - Data retention policy + deletion/anonymization job.
- Operator UX upgrades:
  - Bulk retry, bulk quarantine resolution, reason codes.
  - Inline validation hints for TC/passport.
- Conclude with 1 E2E test pass across roles.

**Exit criteria**
- RBAC correct, audit complete, and sensitive data exposure controlled.

---

### Phase 4 — Observability, Deployment Model, Production Checklists
**User stories**
1. As an Admin, I can see system-wide success rate, failure rate, and per-tenant queue size.
2. As on-call, I get alerted when queue size spikes or agent heartbeat stops.
3. As an Admin, I can manage per-tenant agent “installation” status and configuration versions.
4. As a Hotel Manager, I can download a deployment guide/config bundle for the agent.
5. As ops, I can run go-live checklist and confirm compliance readiness.

**Steps**
- Metrics: success/fail, retries, quarantine, queue age, heartbeat age; expose via endpoint.
- Structured logging + correlation IDs; audit/data-access logs.
- Alert rules (simple in-app thresholds for v1) + dashboard charts.
- Deployment strategy docs:
  - Per-tenant agent config, IP whitelist, environment separation.
  - Simulated “agent installation” state machine.
- Produce checklists: go-live, compliance, operations.
- Final regression E2E tests (core flows + failure scenarios + RBAC).

## 3) Next Actions
1. Create repo skeleton (backend/frontend) and define Mongo collections + state machine constants.
2. Implement Phase 1 backend POC modules (validator, queue, agent worker, KBS SOAP simulator, audit).
3. Write and run Python POC script; iterate until stable.
4. Build Phase 2 UI screens and wire to proven APIs; add demo toggles.

## 4) Success Criteria
- Core pipeline deterministically passes the POC script for: success, timeout, unavailable, duplicate, validation fail, delayed ack.
- UI shows: queue → attempts → final state (acked/failed/retrying/quarantined) with audit timeline.
- TC + Passport validation both work and produce actionable error messages.
- Agent heartbeat and offline mode are visible and affect processing correctly.
- RBAC and KVKK-oriented controls prevent cross-tenant access and reduce PII exposure.
- Observability dashboards/metrics enable diagnosing failures without database access.
