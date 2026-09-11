# Business OS v13 — Creative Director Addendum

## Purpose
This pass moves Website Concepts from style variation toward context-aware, structurally different private prospect demos while preserving Business OS truth and safety boundaries.

## Design contract
- Prospect facts remain PUBLIC_UNVERIFIED until owner confirmation.
- The Creative Director changes presentation only. It cannot create services, credentials, guarantees, pricing, service areas, availability, outcomes, or ROI claims.
- Creative output is a structured allowlisted blueprint, never arbitrary HTML/CSS/JavaScript.
- The deterministic renderer owns executable presentation code.
- Every stored concept remains immutable and tenant-bound.
- Live publishing and provider action gates remain locked.

## What ships in this pass
- Blueprint schema v2 with layout families, hero architectures, visual motifs, density, copy tone, section composition, and design rationale.
- Context-aware local Creative Director provider boundary.
- Business-category + creative-brief-aware design selection.
- Safe site render model that uses only prospect facts already held by Business OS.
- Multiple materially different page compositions: cinematic, editorial, utility, poster, minimal, and local-trust.
- Graceful omission of unavailable proof instead of engineering disclaimers inside the prospect-facing page.
- Public rating/review presentation only when those exact values exist.
- Compact operator workspace that prioritizes generating concepts.

## Explicitly not shipped
- External LLM credentials or vendor lock-in.
- Arbitrary model-generated HTML/CSS/JS.
- Image scraping or unlicensed prospect imagery.
- Owner-confirmed production truth conversion.
- Hosting, domains, DNS, billing, live publishing, production forms, live SMS, scheduling, or receptionist actions.

## External AI path
A future model provider plugs into `generate_concept_blueprint()` and must return the same schema-v2 blueprint. The existing deterministic validator remains the authority before persistence or rendering.
