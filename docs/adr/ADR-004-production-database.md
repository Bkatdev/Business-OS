# ADR-004 — Production database path

**Decision:** keep hardened SQLite for local development. Do not treat it as the final multi-user production database. Prepare a Postgres migration before internet-facing multi-user client production.

**Why:** minimizes current complexity while avoiding a false assumption that local persistence is the production architecture.

**Escape hatch:** a small single-process pilot may temporarily use SQLite only after explicit concurrency, backup and recovery acceptance; this is not the long-term target.
