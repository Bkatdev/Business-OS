# Business OS v14 — Founder Command Center & Production Foundation

## Mission

v14 is one major release, not a chain of cosmetic point releases. Its job is to move Business OS from a protected prospect-demo system toward a founder-usable business while hardening the architectural boundaries that would otherwise become expensive to change later.

Visible operating loop:

**Find → Research → Audit → Rank → Generate → Demo → Track → Convert → Configure → Test**

The website remains the sales wedge. Business OS remains the platform.

## First implementation block

This block deliberately combines product progress with architecture hardening:

1. Founder HQ: a deterministic prioritized prospect/revenue queue built from existing prospect, audit, opportunity, concept and pipeline truth.
2. Provider usage ledger: expensive external capabilities can now emit usage/cost events. Unknown pricing remains unknown.
3. Evidence/provenance contract: facts can carry source type, reference, confidence and storage policy without turning public data into owner-verified production truth.
4. Media asset contract: future owner photos, licensed stock and generated decorative media have an explicit rights/provenance boundary before media is added to production sites.
5. Deployment contract: website deployment identity and history exist before any hosting provider is unlocked. Publishing remains disabled.
6. Governed discovery wrapper: the existing Google Places implementation is reused and metered instead of copied into a second discovery system.

## Core invariants

- Business OS owns canonical truth; vendors are replaceable edges.
- Existing v11 action/provider/outcome architecture is reused, not duplicated.
- Every expensive provider capability must be meterable.
- Every material fact should be able to carry provenance.
- Prospect/public data remains distinct from owner-verified production truth.
- AI proposals never directly perform irreversible actions.
- Website AI produces validated structures, not arbitrary executable code.
- Customer websites will be isolatable from the internal operator application.
- Publishing must be versioned, explicit, reversible and idempotent before it is unlocked.
- External failures become visible states, never silent corruption.
- SQLite remains valid for local development; production persistence must have a planned Postgres path before multi-user rollout.
- Business OS remains a modular monolith until measured scale proves another architecture necessary.

## Provider rule

v11 already owns provider-neutral action identity, attempts, external references and outcome states. v14 does not build another provider framework. Read/generative capabilities may add adapters later, but they must share the same principles: explicit provider selection, simulation/test doubles, usage metering, failure visibility and canonical state staying inside Business OS.

## Cost rule

Never hard-code guessed vendor costs. `usage_events` can store measured units plus estimated or actual cost when pricing is known from a configured rate source. A zero/blank cost means unpriced, not free.

## Discovery/data rule

Discovery providers are replaceable. Store only what the provider terms and product design permit. v14's new provenance layer defaults to reference-only storage and does not persist raw Google response payloads.

## Publishing rule

`site_deployments` is history, not permission. Creating a DRAFT deployment record does not publish anything. No hosting/DNS/domain provider is introduced in this block.

## Next v14 blocks before release protection

- production-grade owner verification and prospect→client conversion;
- public website intake endpoint with CSRF/abuse/idempotency controls;
- media pipeline with rights verification and safe processing;
- static site deployment artifact + hosting adapter + preview/rollback;
- stronger website design system and visual QA loop;
- authentication/authorization boundary for internet exposure;
- production database migration plan and rehearsal;
- integrated end-to-end fake-client acceptance harness;
- per-client unit economics view;
- production monitoring/recovery runbook.

v14 is not complete until those release gates are either implemented or explicitly descoped from the first sellable offer.

## Founder Sales Operating System block

The second v14 implementation block turns Founder HQ from a read-only priority
queue into a founder-controlled sales workflow:

**Rank → Open Sales Workspace → Review Battle Card → Use Grounded Draft → Log Real Activity → Schedule Follow-up → Owner Verification → ONBOARDING**

New boundaries:

- Sales drafts are deterministic and grounded only in known prospect identity and concept state. They are never sent automatically.
- Sales interactions and follow-ups are append-oriented operating history rather than silent overwrites.
- Pipeline state can advance from logged real activity, while agreement alone does not activate a client.
- Public prospect research is visually and structurally separated from owner-verified production truth.
- Prospect conversion requires explicit owner-confirmed identity, industry, contact, services, hours, service area, safety rules, escalation rules and scheduling policy.
- Conversion creates/updates the production client profile, records `OWNER_VERIFIED` provenance, enters `ONBOARDING`, and forces `automation_enabled=0`.
- Existing readiness and activation gates remain the only path to ACTIVE automation.
- Converted clients cannot be silently edited through the prospect verification form; production truth moves to Business Configuration.
- Founder HQ now prioritizes due follow-ups and active conversations before untouched prospects.

This block still does not send email/SMS, publish websites, write provider schedules,
or activate customer automation.

## Customer Delivery Loop

v14 adds a local, immutable customer-delivery simulation that proves the commercial loop without external publishing.

Flow:

Owner verification -> ONBOARDING -> structured owner-verified services -> Website Studio reviewed preview -> immutable local release -> customer request form -> canonical tenant-bound lead -> operator visibility.

Safety boundaries:
- local releases are not internet deployments;
- live provider actions remain locked;
- a release can be created only from an explicitly selected Website Studio preview;
- the frozen artifact is immutable and checksum-addressed;
- a newer reviewed release retires the prior route rather than mutating its artifact;
- public form submissions are tenant-bound to the active release;
- one-time form nonces, idempotency keys, recent-request fingerprint dedupe, bounded fields, service allowlists, and a honeypot reduce accidental/abusive duplicate intake;
- invalid/rejected submissions are recorded rather than silently discarded;
- website submissions create canonical leads only; they do not schedule, message, call, or enable automation;
- owner-confirmed service names may be materialized into structured Business Configuration only after the explicit conversion gate.

External hosting/DNS remains deferred. This surface exists to prove the end-to-end customer journey before a hosting provider is connected.

## Production Experience Block

v14 separates three surfaces on one governed backend: the multi-tenant Operator Console, a single-tenant Client Portal, and customer-facing websites/intake. Client Portal v14 is an operator preview only; production authentication is not claimed until dedicated identity, session, role, and tenant-authorization gates are implemented and adversarially tested.

Production website design now uses owner-verified Website Studio truth plus the validated v13 structured Creative Director blueprint. The design layer cannot persist arbitrary HTML/JS or invent business claims. Design records are version-bound and fail stale when the reviewed Website Studio version changes. The renderer supports differentiated layout families/palettes and explicit mobile behavior. Media is decorative until a licensed or owner-provided asset pipeline is attached with provenance.

## Working Model Stabilization

The stabilization pass treats the real founder workflow as a release gate. Major client capabilities must be reachable from one persistent client workspace rather than requiring knowledge of subsystem routes. Owner Preview is an explicit operator-only preview until production authentication exists. Preview failures are fail-closed but recoverable: the operator receives a visible explanation and safe navigation instead of a dead end.

This pass does not add provider actions, external publishing, or production authentication. Its purpose is reconciliation: make the already-built website, client, delivery, and owner-preview surfaces behave like one intentional product.

---

## v14 Release Candidate Reconciliation

This pass closes the working-model gaps discovered during founder acceptance testing.

### Operator information architecture
The permanent operator navigation is intentionally reduced to five concepts:
**Home → Sales → Clients → Attention → System**. Engineering/governance surfaces remain
available inside System rather than competing for permanent top-level attention.

Inside one client, the persistent workspace is:
**Overview → Website → Leads → Communications → Schedule → Settings → Owner Preview → Test Journey**.
Client-scoped Leads, Communications, and Schedule routes preserve tenant filtering.

### Owner experience
The owner preview is a separate tenant-scoped read model, not a hidden version of the
operator console. It has functional Today, Leads, Calls, Schedule, Website, and Settings
views. Production authentication is still a separate release gate and is not simulated as
complete.

### Three-persona acceptance lab
Each client exposes an operator-only local Acceptance Lab for testing:
1. Business OS operator
2. Business owner preview
3. Customer/lead website journey

The lab never enables external publishing, live messaging/calls, automatic scheduling, or
production owner authentication.

### Production release reconciliation
The customer delivery loop now freezes the same validated production design that was
reviewed by the operator. The production preview and local customer site share a common
safe presentation body. A local release requires:
- client onboarding/active state
- completed owner verification
- customer-ready website truth
- selected reviewed website version
- a production design bound to that exact reviewed version

Immutable release artifacts use schema version 2 and include the validated blueprint,
semantic service-area/hours presentation data, safe service presentation copy, and the
canonical customer intake contract. Arbitrary HTML/JS remains prohibited.

### Release-candidate gate
`v14-rc1` is not a protected production tag. It becomes the protected v14 checkpoint only
after the founder manually completes the three-persona acceptance journey and the full
regression/workflow suite passes in the actual Business OS runtime environment.

## RC2 — Product Experience Finalization Candidate

The RC2 pass closes the gap between a technically safe working model and a product that feels coherent to use and present to a customer.

### Customer website
- Production Preview and local customer release continue to share one renderer and one frozen production artifact.
- The customer renderer now uses a complete responsive composition: branded navigation, editorial hero, original decorative property/tree illustration, services, request process, about, service-area presentation, estimate request, hours, and mobile CTA.
- Customer-facing pages contain no Business OS acceptance/test banner or developer copy. Test-state information remains on operator-only surfaces.
- Owner-entered comma-separated service areas and hours are normalized into semantic display items rather than raw configuration strings.
- Missing service descriptions receive presentation-only request guidance. The fallback copy does not add capabilities, prices, certifications, timing, warranties, outcomes, or other business claims.
- `.example` addresses remain suppressed from public presentation.

### Client workspace
- The client Overview is reorganized around three obvious destinations: Website, Owner Preview, and Test Journey.
- Operational metrics, attention, readiness, and recent activity remain truthful and tenant-bound while secondary subsystem detail is kept below the primary workflow.
- The global application navigation remains Home / Sales / Clients / Attention / System.

### Owner preview
- The owner portal remains a read-only, single-tenant preview and now uses a more polished responsive visual system.
- Today, Leads, Calls, Schedule, Website, and Settings remain real routed tabs.
- Production authentication is still explicitly not claimed.

### Safety boundary
RC2 does not enable external publishing, live SMS, live calls, autonomous scheduling, production owner authentication, arbitrary AI code, or live provider actions. The release remains a local release candidate until the human acceptance journey passes and Git protection is deliberately performed.
