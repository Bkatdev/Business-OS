# ADR-002 — Replaceable provider adapters

**Decision:** Business OS owns canonical identity/state. External AI, discovery, messaging, voice, email and hosting systems are adapters. v11 execution infrastructure remains the canonical action/outcome spine.

**Why:** prevents vendor lock-in and makes provider cost/reliability changes localized.

**Escape hatch:** provider-specific features may be exposed when valuable, but provider identifiers remain references rather than canonical record identity.
