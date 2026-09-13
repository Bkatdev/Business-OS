# Business OS v15 — Website Intelligence & Upgrade Engine

## Mission
v15 stops treating a redesign as the value proposition. Business OS first understands the prospect's existing customer journey, preserves what is already strong, identifies evidence-backed gaps, and later uses those findings to propose functional and visual upgrades.

## Block 1 — Prospect Website Intelligence + Evidence Foundation
**Prospect URL → bounded public-site crawl → page inventory → evidence ledger → asset references → capability observations**

This block deliberately does **not** create Upgrade Blueprint recommendations yet. It establishes reliable observation before interpretation.

### Invariants
- Public observations are evidence, not canonical Business Truth.
- The crawler is same-site, bounded, size-limited and rejects local/private network targets.
- Cross-site redirects are rejected.
- Robots rules are respected when retrievable.
- No forms are submitted during analysis.
- No authenticated/private pages are accessed.
- No discovered image is automatically approved for production.
- Every discovered asset defaults to `DISCOVERED_REFERENCE`, `production_allowed=0`.
- Capability observations can be `PRESENT`, `NOT_DETECTED`, or `UNKNOWN`; `NOT_DETECTED` is not equivalent to “the business does not offer this.”
- Static observation cannot prove post-submit behavior such as lead acknowledgment, so those remain `UNKNOWN`.
- Existing v14 audit data is not silently overwritten by v15 intelligence.
- No live SMS, calls, scheduling writes, external publishing or autonomous provider action is introduced.

### Durable observation records
`site_intelligence_runs`, `site_intelligence_pages`, `site_intelligence_evidence`, `site_capability_observations`, `site_asset_observations`.

Later v15 truth-resolution and upgrade-planning blocks consume these records without mutating their source evidence.

## Block 2 — Business Truth Resolver + Capability Gap Engine + Upgrade Blueprint
**Latest completed evidence snapshot → immutable truth resolution → industry relevance → focused Upgrade Blueprint**

Block 2 turns observations into a decision without treating inference as fact. It creates:

- `truth_resolution_runs` and `business_truth_claims` for immutable, tenant-bound truth snapshots.
- `truth_claim_sources` so public claims remain traceable to captured evidence.
- `owner_truth_verifications` as append-only operator records of explicit owner answers.
- `capability_gap_assessments` for the full industry-aware decision model.
- `upgrade_blueprints` and `upgrade_blueprint_items` for the focused sales/product result.

Truth states are explicit: `PUBLIC_OBSERVED`, `INFERRED`, `OWNER_CONFIRMED`,
`SYSTEM_VERIFIED`, `UNKNOWN`, and `CONFLICT`. Multiple public phone or email
values become `CONFLICT`; the engine never chooses one. An owner-confirmed value
wins in the next immutable truth resolution while the original public evidence
remains unchanged.

Capability relevance is based on bounded business profiles rather than a universal
feature checklist. Field-estimate businesses, appointment services, consultation
businesses, and unknown/general businesses receive different decisions. Live
booking is not recommended to an estimate-driven tree company simply because it
exists in the capability catalog.

The full assessment records customer value, conversion friction, operational
savings, trust, urgency, evidence confidence, implementation complexity, and
operational risk. A deterministic score is used only for ordering. The product
does not display an arbitrary overall website score.

The surfaced blueprint is intentionally small:

- **KEEP** preserves useful capabilities already supported by evidence.
- **IMPROVE** identifies a stronger customer journey using existing foundations.
- **ADD** contains only the highest-value relevant missing capabilities.
- **VERIFY** exposes unknowns, conflicts, and claims requiring an owner answer.
- **IGNORE** records deliberate non-priorities so they do not return as feature noise.

Every surfaced item includes evidence, a source URL, why it matters, expected
benefit, confidence, complexity, and owner-verification status.

### Block 2 safety invariants

- Blueprint generation cannot change `businesses`, client configuration, lifecycle state, or automation flags.
- Owner verification creates a new blueprint version; it never edits the crawl or an old blueprint.
- Missing evidence fails to `UNKNOWN` or `VERIFY`, never to an invented fact.
- Cross-tenant blueprint, claim, evidence, and verification reads are scoped by `business_id`.
- Live booking, payment, and customer portals remain blocked/non-prioritized when absent.
- No SMS, calls, autonomous scheduling, provider execution, or external publishing is introduced.
- All blueprint and owner-verification mutations are POST-only in the local operator UI.

## Next block
Block 3 introduces Website Engine 2.0, governed media, materially different design
families, and the deterministic Design Critic. It consumes only approved/verified
truth and the focused Upgrade Blueprint; it must not turn unresolved claims into
production copy.

## Block 1.5 — Product Shell 2.0 + Automated Visual QA
Business OS itself now follows the v15 product-design rule: customer sites can be expressive, while the operator product is quiet, precise, premium and exception-oriented.

Changes:
- Rebuilt operator navigation shell with calm light navigation, real SVG icons, an intentional collapsed state and no crushed sidebar philosophy card.
- Global search is a command-style utility rather than a permanent competing form.
- Command Center was reduced to an operating brief: first action, four meaningful metrics, action queue, quiet system state and recent opportunities.
- Founder HQ became an ordered work surface rather than a card dashboard.
- Website Intelligence results are more scannable: capability tiles, collapsible raw evidence, and a media reference gallery with rights status.
- Existing deep pages inherit calmer surfaces, tables, controls and responsive behavior without changing backend contracts.
- Added `scripts/v15_visual_qa.py`, a GET-only local browser acceptance harness. It discovers context from the local development database, checks major operator/client routes at desktop/tablet/phone widths, captures screenshots, and produces an HTML report. When Playwright is available it also checks horizontal overflow, console errors, page errors, and the collapsed sidebar. Installed Chrome/Edge is used as a no-dependency screenshot fallback.
- Visual QA never submits forms and never invokes provider actions.

This block intentionally precedes Truth Resolution so new v15 systems are built into a stable visual shell instead of multiplying the v14 dashboard language.
