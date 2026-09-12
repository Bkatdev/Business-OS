# ADR-005 — Cost metering

**Decision:** external paid capabilities emit provider/capability/unit usage records. Estimated or actual cost is recorded only when known; missing cost is unpriced, not free.

**Why:** Business OS cannot set safe pricing or bundles without per-client unit economics.

**Escape hatch:** none for recurring paid providers. Unmetered production usage is a release blocker for usage-sensitive capabilities such as voice and messaging.
