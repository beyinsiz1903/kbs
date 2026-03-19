# plan.md

## 1) Objectives
- ✅ **Completed**: Prove the **core pipeline** works end-to-end with realistic failure modes: **Check-in → Validation (TC/Passport) → Queue → Simulated Agent → Simulated KBS SOAP/XML → Ack/Fail → Retry/Quarantine → Audit**.
- ✅ **Delivered (v1 core app)**: Cloud management panel + simulated local bridge agent runtime + operator monitoring UI.
- 🟡 **In progress (Phase 2 hardening)**: Fix minor frontend UX/testability issues (navigation targeting, hotel dropdown targeting) to reach “demo-polished” level.
- ⏭️ **Next**: Move to **Phase 3**: RBAC (Admin/Hotel Manager/Front Desk), security hardening, KVKK compliance controls.
- ⏭️ Later: Observability upgrades + deployment model + production checklists.

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
- Frontend: 🟡 ~75% (core flows work; minor UX/testability issues found)

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
1. 🟡 Navigation targeting in Turkish UI (timeouts when selecting some TR labels) → add/standardize `data-testid`/attributes for nav links.
2. 🟡 Hotel dropdown targeting inconsistency on Check-in page → ensure stable `data-testid` on trigger + list items; verify Select portal behavior.
3. 🟢 Language toggle minor: brand text not translated (acceptable for v1) → optional.

**Revised Phase 2 exit criteria**
- All demo flows are stable *and* UI is testable/reliable:
  - ✅ Check-in → queued → agent send → ack
  - ✅ KBS unavailable → retries → quarantine → correction → success
  - ✅ TC + Passport validation
  - ✅ Agent offline/online affects processing
  - ✅ Audit trail visible
  - 🟡 Fix remaining UI targeting issues (navigation + hotel select)

---

### Phase 3 — Security, RBAC, Compliance Hardening + Better Ops UX
**Status: ⏭️ NEXT**

**User stories**
1. As a user, I can log in and only see data permitted by my role and hotel.
2. As an Admin, I can assign roles to users and invite hotel staff.
3. As a Compliance Officer (optional), I can export audit trails and view data access logs.
4. As a Hotel Manager, I can restrict who can edit/quarantine/requeue submissions.
5. As support, I can view agent logs/metrics to debug failures quickly.

**Steps**
- Implement JWT auth + RBAC (Admin/Hotel Manager/Front Desk) with hotel scoping.
- Enforce authorization on all endpoints + UI route guards.
- KVKK enhancements:
  - PII masking by role.
  - Encryption-at-rest strategy (app-level field encryption for sensitive fields).
  - Retention policy + deletion/anonymization job.
  - Data access audit events (who viewed what).
- Operator UX upgrades:
  - Bulk retry/requeue, reason codes.
  - Inline validation hints for TC/passport.
- Conclude with role-based E2E test pass.

**Exit criteria**
- RBAC correct, audit complete, sensitive data exposure controlled.

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
- Final regression E2E tests (core flows + failure scenarios + RBAC).

## 3) Next Actions
1. **Finish Phase 2 polish**:
   - Add/standardize `data-testid` for sidebar navigation items.
   - Stabilize Check-in hotel Select targeting (testids for option items / ensure predictable portal rendering).
   - Quick sanity pass of TR/EN toggle coverage.
2. Re-run lightweight UI E2E verification (manual + automated smoke).
3. Start **Phase 3**:
   - Implement JWT auth + RBAC models.
   - Add tenant/hotel scoping to all reads/writes.
   - Add KVKK controls (masking + retention + access logging).

## 4) Success Criteria
- ✅ Core pipeline deterministically passes: success, timeout, unavailable, duplicate, validation fail, delayed ack.
- ✅ UI demonstrates: queue → attempts → final state (acked/retrying/quarantined) with audit timeline and XML viewer.
- ✅ TC + Passport validation both work and produce actionable errors.
- ✅ Agent heartbeat and offline mode are visible and affect processing.
- 🟡 Phase 2 polish: navigation + hotel dropdown stability.
- ⏭️ Phase 3: RBAC + KVKK-oriented controls prevent cross-hotel access and reduce PII exposure.
- ⏭️ Phase 4: Observability enables diagnosing failures without DB access; deployment and checklists ready for go-live.
