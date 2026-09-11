# Business OS v13 — Prospect-to-Demo Engine / AI Website Designer Foundation

## Mission

v13 makes a deliberate dent in the founder revenue loop without pretending the entire future company can ship in one release.

The release target is:

**Prospect → Evidence-backed audit → Sales brief → Website concept → Private preview → Human review**

It prepares, but does not yet unlock:

**Owner verification → Client conversion → Governed publishing → Hosting → Billing → Production communications**

Business OS remains the platform. The website is the initial sales wedge.

---

## Current-state audit (from the supplied v12.1 working-source archive)

### What already exists and should be reused

1. **Prospect discovery** already exists through Google Places in `services/prospect_finder.py`.
2. **Prospect records** already live in `businesses` and carry source, Google Place ID, address, status and website-audit fields.
3. **Website audit** already inspects public pages and stores evidence, audit state, page count and confidence.
4. **Opportunity scoring** already fails closed when a website audit has not completed.
5. **Sales pipeline states** already exist: Not Contacted → Researching → Qualified → Contacted → Demo → Proposal → Client/Lost.
6. **Website Studio** already has tenant-bound projects, immutable presentation versions, explicit preview selection and deterministic rendering.
7. **Business Configuration** already owns canonical client truth and public service/intake configuration.
8. **Governed execution, quarantine, ledger and reliability foundations** already exist and must remain untouched by website generation.

### Gaps v13 must address

1. Current Website Studio is still structurally close to one layout with three themes.
2. There is no structured Site Blueprint between business truth and rendering.
3. There is no AI/provider boundary for design generation.
4. Prospect audits do not yet become a concise evidence-backed sales battle card.
5. Package recommendations are not yet derived from audit evidence.
6. There is no first-class prospect website-concept object or private concept history.
7. Public prospect facts and owner-verified production truth are not yet represented as distinct website-generation states.
8. Current CSRF protection is insufficient for an internet-exposed production deployment.
9. Live publishing/hosting is intentionally absent.
10. Customer-facing website intake submission is not yet a production-ready public endpoint.

---

## v13 release scope

### Workstream A — Evidence-backed Sales Intelligence

For each prospect, Business OS produces a **Sales Brief** derived only from structured prospect data and completed website-audit evidence.

The brief contains:

- opportunity state;
- strongest evidence-backed pitch angles;
- what Business OS should *not* claim;
- recommended initial package;
- why that package is recommended;
- discovery questions to ask the owner;
- next best action.

Rules:

- No completed audit → no website weakness score presented as fact.
- “Not detected” remains “not detected,” never “does not exist.”
- Business OS never claims lost revenue, missed calls, conversion uplift or ROI unless later measurement proves it.
- Full/Complete automation is never automatically recommended only from a public website audit; it requires owner discovery.

### Workstream B — Site Blueprint Foundation

Introduce a structured, validated **Site Blueprint** that contains design decisions, not arbitrary code.

The blueprint controls:

- design personality;
- hero composition;
- navigation treatment;
- content width;
- typography system;
- spacing density;
- corner/radius treatment;
- surface/background treatment;
- CTA treatment;
- section order;
- section variants;
- visibility of allowed sections.

The blueprint does **not** contain arbitrary JavaScript, executable templates or unrestricted HTML.

All values are selected from an allowlisted component/design registry.

### Workstream C — Prospect Website Concepts

Create immutable prospect website concepts bound to exactly one business record.

Each concept stores:

- business ownership;
- concept number;
- creative brief;
- validated blueprint JSON;
- generation mode/provider;
- truth state;
- lifecycle status;
- creation time.

Initial truth state for prospect concepts:

`PUBLIC_UNVERIFIED`

This visually distinguishes a private sales concept from production owner-verified truth.

### Workstream D — Designer Provider Boundary

v13 establishes a provider-neutral interface:

`Creative Brief + Allowed Facts + Blueprint Schema -> Proposed Blueprint`

Initial local generation can create varied deterministic blueprints for development and tests.

A later provider adapter may call an LLM, but every returned blueprint must pass the same deterministic validator before persistence or rendering.

The provider may choose design and marketing expression. It may not add new business facts.

### Workstream E — Private Concept Workspace

From Prospect Intelligence, Ben can:

1. review audit evidence;
2. see the Sales Brief;
3. enter creative direction;
4. generate a new concept;
5. see immutable concept history;
6. open a private preview;
7. regenerate a substantially different direction.

No public publishing occurs in this workstream.

---

## Site Blueprint security contract

### Allowed

- enum-based component variants;
- allowlisted palettes;
- allowlisted type systems;
- allowlisted layout compositions;
- plain-text creative brief;
- plain-text copy derived from allowed facts;
- server-rendered safe components.

### Forbidden

- arbitrary HTML;
- arbitrary CSS supplied by a model;
- arbitrary JavaScript;
- script URLs;
- inline event handlers;
- iframes generated by a model;
- arbitrary external assets;
- model-created business claims;
- direct model publication.

### Validation rule

AI/procedural output is a **proposal**. A concept exists only after deterministic validation succeeds.

Unknown/invalid enum values fail closed to a rejected proposal; they are not silently trusted.

---

## Truth model

### Prospect concept

Source: public/observed information.

State: `PUBLIC_UNVERIFIED`.

Use: private demonstration only.

The preview must visibly indicate that business details should be confirmed before launch.

### Production website

Source: owner-confirmed Business Configuration.

State: `OWNER_VERIFIED` / production classification as defined by later publishing architecture.

Use: customer-facing publication only after explicit review and governed publication.

Prospect data must never silently become production truth.

---

## Sales package recommendation contract

The system recommends a **starting conversation**, not a binding price or promise.

### Website

Suitable when the evidence primarily points to web-presence/intake shortcomings.

### Front Office

Suitable when public evidence suggests higher-intent operational workflows (for example emergency service or appointment/estimate workflows) and a website-only offer may leave obvious workflow value unused.

### Complete

Never auto-prescribed from public website inspection alone. Mark as “discovery required.” Production communications, AI receptionist and scheduling depend on owner-confirmed workflows, consent/compliance and provider readiness.

---

## Threat model

### Prompt injection from prospect websites

Threat: Website copy contains text intended to manipulate a model.

Control: Treat scraped website material as untrusted evidence/data, never as model instructions. Future AI provider prompts must put source content in a clearly delimited data field and require schema-only output.

### Hallucinated business claims

Threat: Model invents awards, years, rankings, prices or guarantees.

Control: Blueprint cannot introduce arbitrary fact fields. Copy generation must be tied to an allowlisted fact packet and validated separately before publication.

### Stored/reflected XSS

Threat: Prospect names, notes, creative briefs or generated copy contain executable markup.

Control: Persist plain text; Jinja autoescaping remains on; renderer never marks raw business/model text safe.

### Cross-tenant concept access

Threat: Concept ID from one business used to view another business.

Control: Every concept fetch requires both `concept_id` and `business_id` ownership match.

### Malicious URLs

Threat: scraped or generated javascript/data/file URLs.

Control: only explicit HTTP/HTTPS URLs pass renderer normalization.

### CSRF

Threat: authenticated operator is induced to trigger state-changing routes.

Control: v13 production readiness remains blocked until application-wide CSRF is installed and verified. New concept generation is local-development functionality until then.

### Publishing unknown state

Threat: UI implies a site is live when provider/host outcome is unknown.

Control: v13 does not implement live publishing. Future publishing must use governed Action → Provider → Outcome architecture and distinguish accepted/pending/succeeded/unknown.

---

## Explicitly deferred

- live hosting/domain/DNS automation;
- production website publication;
- billing/subscriptions;
- automated cold outreach;
- autonomous sales calls;
- arbitrary HTML/CSS/JS generation;
- owner self-service website builder;
- production AI receptionist unlock;
- live SMS unlock;
- live scheduling writes;
- full CRM replacement;
- advanced analytics/A-B testing;
- fake or inferred ROI claims.

---

## v13 acceptance criteria

v13 foundation is acceptable only when:

1. Existing v12 schema and renderer regression tests still pass.
2. New blueprint validator rejects unsupported values and executable content paths.
3. Two different creative directions can produce materially different safe blueprints.
4. A prospect concept cannot be fetched under another business ID.
5. Sales recommendations are evidence-backed and do not convert unknown into negative fact.
6. Prospect concept preview is clearly private/unverified and cannot be mistaken for publication.
7. No live provider, live publishing, SMS or scheduling gate is unlocked.
8. Desktop and mobile preview are visually accepted by Ben.
9. Fresh Git status is reviewed before any protected commit/tag.

---

## Commercial acceptance test

The release should move Ben materially closer to this event:

1. discover a real prospect;
2. run an evidence-backed audit;
3. understand why the prospect is worth contacting;
4. see a sensible starting package and pitch angle;
5. generate a private concept that visibly feels designed for that company;
6. show it to the owner without claiming it is already live or owner-approved.

That is the v13 dent. Conversion, verified onboarding and governed publication follow after this loop is proven.
