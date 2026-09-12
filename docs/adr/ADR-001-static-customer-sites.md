# ADR-001 — Static customer website deployments

**Decision:** Approved website versions should compile to static deployable artifacts whenever practical. Dynamic forms call a narrow Business OS public API rather than exposing the internal operator application.

**Why:** lower hosting cost, smaller attack surface, fast delivery, easier rollback, renderer/provider independence.

**Escape hatch:** dynamic server rendering remains possible for future capabilities that truly require it, but it must not become the default by accident.
