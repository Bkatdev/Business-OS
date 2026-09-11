# Business OS v13 — Revenue Engine / Creative Director Finalization

## Release stopping point

v13 is complete enough to protect as a development checkpoint when the full
automated suite and desktop/mobile manual acceptance pass.

v13 proves the commercial loop:

**Prospect → evidence-backed sales brief → private website concept → alternate
creative direction → immutable history → human review**

It deliberately does **not** unlock production publishing, autonomous outreach,
SMS, scheduling, receptionist actions, billing, domains/DNS, or arbitrary
model-generated website code.

## What v13 now owns

### 1. Evidence-backed prospect workflow
Business OS can discover/audit a prospect, build a truthful sales brief, and
open a Prospect-to-Demo Studio without silently turning public prospect facts
into owner-verified production truth.

### 2. Structured Creative Director
The Creative Director chooses from a validated blueprint contract. It can vary
layout family, hero architecture, typography system, palette, spacing, density,
section order, component variants, CTA treatment, and visual personality.

The current provider is deterministic/local for reproducibility. A future LLM
may propose the exact same blueprint shape, but its output must pass the same
validator before storage or rendering.

### 3. Immutable concepts + backward compatibility
New concepts use blueprint schema v2. Historical v1 concepts remain immutable
in storage and are adapted only in memory through strict validation.

### 4. Safe prospect rendering
The renderer uses canonical/public facts already present in Business OS.
Missing proof disappears. The prospect-facing page does not expose internal
engineering disclaimers and does not invent services, credentials, warranties,
pricing, service area, availability, years in business, outcomes, or ROI.

### 5. Visual-quality baseline
The final v13 pass removes fake empty "art" placeholders and replaces them with
meaningful fact-driven composition. Reputation is not duplicated. The
Prospect-to-Demo Studio is action-first and responsive. Website concepts have
multiple safe layout families while sharing a maintainable renderer.

## Security / reliability invariants

- No arbitrary HTML, CSS, JavaScript, iframe, event handler, or executable model output.
- Tenant-bound concept lookup.
- Immutable concept history.
- v1 compatibility is read-only; stored legacy bytes are not mutated.
- Unsupported/malformed blueprints fail closed.
- Public/unverified prospect data never silently becomes owner-verified truth.
- Publishing remains human-governed and locked in v13.
- Existing provider/SMS/scheduling live-action gates remain untouched.
- Private preview is noindex/noarchive and uses private/no-store response headers.

## Manual acceptance before protection

Test at least:
1. one tree/home-service prospect,
2. one auto/industrial prospect,
3. one third industry.

For each:
- Studio is usable at desktop width with no collapsed rail.
- Generate a concept.
- Generate a clearly different direction.
- Preview has no broken/empty placeholder blocks.
- Public facts are correct.
- Missing facts are omitted.
- Desktop hierarchy looks credible enough to show privately to an owner.
- Browser mobile emulation around 390px has no horizontal overflow and keeps
  contact action readable.

## Deferred beyond v13

These are intentionally not required to call v13 a successful development
checkpoint:

- External LLM Creative Director provider.
- Real photography/media ingestion and rights/provenance controls.
- Owner verification workflow that promotes prospect facts to production truth.
- Production public forms and abuse/CSRF hardening.
- Hosting/domain/DNS/publishing adapters.
- Billing/subscriptions.
- Automated outreach.
- Production receptionist/SMS/scheduling unlock.
- A/B testing and advanced analytics.

Those should be separate governed workstreams rather than being smuggled into a
visual website release.

## Commercial test

The next business milestone is not another architecture layer. It is:

> Can a real owner be shown a private, accurate concept for their actual
> business and become interested enough to continue the conversation?

That is the right validation target after this checkpoint.
