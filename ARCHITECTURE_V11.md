# Business OS v11 — Governed Execution Spine

## Purpose

v11 turns Business OS from a system that can decide and simulate front-office work into a system with one provider-neutral execution spine. It does **not** unlock live customer contact. The goal is to make future SMS, scheduling, voice, website, and other external actions share the same ownership, policy, idempotency, provider, outcome, retry, attention, and audit model.

## Ownership boundaries

Business OS owns:

- business and tenant context
- verified configuration
- lead/customer operational records
- action identity and idempotency
- governance and approval state
- provider attempt history
- normalized action outcome
- retry eligibility and next retry time
- attention state and system ledger history

External providers own only provider-specific execution capability and provider-side identifiers. Provider IDs are references, never Business OS identity.

## Execution flow

`Intent -> tenant safety -> policy -> idempotency -> provider adapter -> provider result -> normalized outcome -> retry/reconciliation -> Attention -> System Ledger`

### Canonical action states

- `REQUESTED`
- `ATTEMPTING`
- `ACCEPTED_PENDING_OUTCOME`
- `SUCCEEDED`
- `RETRY_SCHEDULED`
- `FAILED_PERMANENT`
- `UNKNOWN`
- `BLOCKED`
- `CANCELLED`

A provider accepting a request is deliberately different from Business OS confirming the desired outcome.

## Idempotency

An action idempotency key is derived from action type, tenant, lead, source entity, mode, and a SHA-256 fingerprint of the canonical payload. Repeating the same request reuses the original action instead of repeating the provider side effect.

This protects against double-clicks and common application retries. Provider-specific idempotency keys should additionally be supplied to real providers when their API supports them.

## Unknown outcomes

An unexpected exception at the provider boundary becomes `UNKNOWN`. Business OS does not blindly retry an unknown result because the provider may already have performed the side effect. Unknown outcomes belong in Attention and require reconciliation.

## Retry model

Retryable provider failures can become `RETRY_SCHEDULED` with bounded exponential delay. v11 persists the retry schedule but intentionally does not introduce a background worker. A worker/queue will be selected only when a real provider workflow requires asynchronous execution.

## Provider adapters

`services/providers/` is the replaceable integration boundary. v11 registers only the side-effect-free `SimulationProvider`. Live mode remains unavailable even if a developer changes UI behavior.

A real provider must not be added until it has:

1. deliberate configuration and secrets handling
2. compliance/consent policy for the action type
3. a kill switch
4. authenticated callback/webhook handling
5. duplicate callback protection
6. provider-specific idempotency strategy
7. error classification
8. outcome reconciliation
9. release verification

## Live gate

The global environment gate is `BUSINESS_OS_LIVE_ACTIONS_ENABLED`. It defaults off. Live execution also requires an ACTIVE business, business-level automation enabled, PRODUCTION data, non-quarantined ownership, and an actual provider adapter. v11 includes no live provider adapter.

## Provider events

`provider_events` stores authenticated, normalized provider callbacks idempotently by `(provider, event_id)`. There is intentionally no generic public webhook route. Each future provider must verify its own signature/authenticity before passing an event into the shared execution layer.

## Compatibility

The v10.x `automation_executions` table remains as a compatibility ledger while new actions use the canonical `actions` and `action_attempts` tables. Existing SMS screens and routes remain intact and are routed through the new execution core.

## Future integrations

### Messaging

`SEND_SMS` / future channel action -> messaging adapter -> provider -> delivery callback -> normalized outcome.

### Scheduling

Future scheduling actions should reuse the same action spine but must add authoritative availability, concurrency protection, provider appointment IDs, and reconciliation before any live writes are enabled.

### Retell

Retell remains a voice channel. Voice events should enter the same Business OS intake/domain model. Retell should not become a separate business-logic engine.

### Website Studio

Generated websites should remain presentation/intake surfaces over verified Business Configuration. Website forms, calls, and future booking requests should feed the same Business OS intake and execution spine rather than creating a parallel database or workflow engine.

## Deferred intentionally

- live SMS provider selection
- scheduling provider selection
- background worker/queue technology
- PostgreSQL migration
- production authentication/authorization
- cloud hosting choice
- billing/payment provider
- Website Studio

These are deferred so infrastructure follows proven requirements instead of dictating the domain architecture.
