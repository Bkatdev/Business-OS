\# Business OS v12 Architecture

\## Website Studio



Status: Design Contract

Base Release: v11.1

Protected Base Tag: v11.1

Protected Base Commit: 777125a89b430aecd86e88c7045b510735e7b9de

Development Branch: feature/v12-website-studio



\---



\# 1. Mission



Business OS v12 introduces Website Studio.



Website Studio is not a generic website builder.



Its purpose is to turn verified Business OS configuration into a professional customer-facing front door that feeds directly into the same canonical Business OS operating system.



The intended product loop is:



Business Configuration

→ Website Studio

→ Customer Website

→ Customer Intake

→ Canonical Lead

→ Front Office Intelligence

→ Governed Action Engine



The product should feel like:



"Business OS already understands my business. Help me turn that verified information into a professional front door."



It should not feel like:



"Here are 80 website-builder controls. Build everything yourself."



\---



\# 2. Product Thesis



The v12 thesis is:



Verified Business

→ Professional Website

→ Canonical Lead



Website Studio should make Business OS easier to demonstrate, easier to understand, and easier to sell.



A business owner should be able to configure the truth about their business once and see that same verified information power:



\- the internal operating system,

\- customer-facing website content,

\- customer intake,

\- lead creation,

\- future communications,

\- future scheduling,

\- and future provider actions.



Website Studio is another entrance into the same Business OS brain.



It is not a separate product with a separate source of truth.



\---



\# 3. Architectural Law



Business OS owns business truth.



Website Studio owns presentation.



Website Studio MUST NOT create competing systems for facts already owned elsewhere.



Existing canonical systems remain authoritative for:



\- businesses,

\- business identity,

\- service catalog,

\- intake configuration,

\- leads,

\- lead ownership,

\- tenant identity,

\- business configuration,

\- policy,

\- automation,

\- actions,

\- approvals,

\- outcomes,

\- system history.



Website Studio may reference these systems but must not silently duplicate them.



Examples of architecture that should be avoided when canonical equivalents already exist:



\- website\_services

\- website\_business\_phone

\- website\_business\_email

\- website\_hours

\- website\_intake\_questions

\- website\_leads

\- website\_customer\_records



Website-specific state is acceptable only when it represents presentation or website lifecycle state rather than duplicated business truth.



\---



\# 4. Source-of-Truth Boundaries



\## Business Configuration owns



\- verified business identity

\- verified service offerings

\- structured service information

\- configured intake questions

\- relevant business context

\- operational configuration

\- readiness information



\## Website Studio owns



\- website draft state

\- presentation preferences

\- visual theme choices

\- layout choices within approved templates

\- section visibility

\- safe presentation copy

\- page titles

\- SEO presentation metadata

\- draft/version history

\- preview state

\- publish-readiness state

\- future publishing references



\## Canonical Lead system owns



\- submitted lead identity

\- customer contact information

\- request details

\- service association

\- intake answers

\- source attribution

\- timestamps

\- lifecycle state

\- timeline/history



Website submissions must become canonical Business OS leads.



They must not remain trapped inside a Website Studio-specific submission database.



\---



\# 5. v12.0 Core Scope



The first Website Studio release should prove one excellent end-to-end experience.



CORE:



\- one Website Studio experience per configured business

\- configuration-readiness awareness

\- professional industry-neutral starting website

\- business name and verified business identity reuse

\- verified service catalog reuse

\- configured intake question reuse

\- hero section

\- services section

\- about/trust section

\- service-area/contact section

\- customer call-to-action section

\- safe editable presentation copy

\- controlled branding settings

\- desktop preview

\- mobile preview

\- customer-facing request form

\- canonical lead creation

\- website source attribution

\- intake answer preservation

\- tenant isolation

\- duplicate submission protection

\- draft/version state

\- safe local preview

\- accessibility fundamentals

\- basic SEO metadata

\- missing-information warnings

\- explicit publish-readiness state

\- system history where operationally meaningful

\- deterministic verification scripts

\- no live publishing in v12.0



The primary success case is:



1\. Configure a business.

2\. Open Website Studio.

3\. Business OS generates a credible front door from verified information.

4\. Adjust safe presentation settings.

5\. Preview the site on desktop and mobile.

6\. Submit a real test customer request.

7\. The request appears as a canonical Business OS lead.

8\. Existing Front Office Intelligence can work with that lead.



\---



\# 6. Explicit Non-Goals for v12.0



Do not build these merely because traditional website builders have them:



\- freeform drag-and-drop page builder

\- arbitrary HTML editing

\- arbitrary JavaScript

\- user-supplied scripts

\- plugin marketplace

\- dozens of templates

\- arbitrary page trees

\- full CMS

\- blog platform

\- ecommerce

\- payment processing

\- production custom domains

\- DNS management

\- live hosting integrations

\- production publishing integrations

\- autonomous AI publishing

\- autonomous AI business claims

\- sophisticated analytics

\- A/B testing

\- advanced SEO tooling

\- automatic review importing

\- complex media library

\- unrestricted file uploads

\- scheduling-provider integration

\- live SMS

\- live email

\- automatic customer communication

\- any provider action that bypasses the v11 execution spine



These may be evaluated in later releases only when a real customer need justifies them.



\---



\# 7. Website Content Rules



Website Studio may help present verified facts.



It must never manufacture facts.



The system must not invent:



\- services

\- prices

\- discounts

\- guarantees

\- warranties

\- certifications

\- licenses

\- years in business

\- employee counts

\- locations

\- service areas

\- availability

\- response times

\- review scores

\- awards

\- insurance claims

\- emergency availability

\- financing

\- medical claims

\- legal claims

\- safety claims

\- customer outcomes



If required information is missing, the system should:



1\. identify that information as missing,

2\. explain why it matters,

3\. allow the owner/operator to configure it in the authoritative system,

4\. avoid presenting invented placeholder claims as truth.



Presentation copy must remain distinguishable from verified business facts.



\---



\# 8. AI Boundary



AI may assist with:



\- suggesting presentation wording

\- rewriting owner-provided copy

\- summarizing verified business information

\- recommending section order

\- identifying missing information

\- suggesting clearer calls to action

\- suggesting SEO-friendly titles/descriptions based on verified facts



AI must not:



\- invent business facts

\- fabricate credentials

\- fabricate reviews

\- fabricate service coverage

\- fabricate pricing

\- fabricate policies

\- publish autonomously

\- alter canonical business configuration without explicit governed action

\- convert uncertainty into a factual claim



Where AI-generated text is eventually introduced, its inputs must be constrained to authoritative business data plus explicit owner-provided presentation context.



\---



\# 9. Customer Intake Architecture



Customer-facing website intake must reuse canonical Business OS intake configuration.



The preferred architecture is:



Website Request Form

→ resolve business/tenant

→ load active canonical intake schema

→ render approved questions

→ validate submission

→ normalize values

→ protect against duplicate submission

→ create canonical lead

→ preserve website provenance

→ preserve intake answers

→ write relevant history/system events

→ allow existing Front Office Intelligence to continue processing



Website Studio must not fork intake logic into a second incompatible system.



If a business changes its canonical intake configuration, the website experience should derive from that updated source of truth according to explicit versioning/readiness rules.



\---



\# 10. Canonical Lead Creation



Website submissions must create real Business OS leads through a reusable service boundary.



The website route must not contain a second hand-written lead implementation that drifts from existing lead behavior.



Lead creation should preserve at minimum:



\- business/tenant ownership

\- customer name when provided

\- phone when provided

\- email when provided

\- service request

\- selected canonical service when applicable

\- intake answers

\- freeform customer message when applicable

\- source = website or equivalent canonical source identifier

\- created timestamp

\- data classification

\- provenance

\- idempotency or duplicate-submission protection



A website lead must behave like a lead created through any other legitimate Business OS entrance.



\---



\# 11. Tenant Isolation



Every Website Studio operation must resolve and enforce the owning business.



Never trust a business ID merely because it appears in:



\- a URL

\- a form field

\- browser state

\- hidden HTML

\- query parameters

\- preview parameters



Server-side ownership checks are required.



A user or request associated with Business A must not be able to:



\- read Business B's website configuration

\- edit Business B's website

\- preview Business B's private draft

\- submit data into the wrong tenant through manipulated identifiers

\- access Business B's draft versions

\- publish Business B's website

\- load Business B's private presentation state



Cross-tenant access must fail closed.



\---



\# 12. Security Threat Model



v12 must explicitly defend against:



\- cross-tenant access

\- IDOR

\- XSS

\- stored XSS

\- reflected XSS

\- unsafe HTML

\- unsafe URL handling

\- template injection

\- arbitrary script execution

\- malicious iframe/embed content

\- CSRF

\- spam submissions

\- duplicate submissions

\- automated form abuse

\- malicious payload sizes

\- unsafe redirects

\- poisoned SEO fields

\- unsafe file uploads

\- wrong-tenant publishing

\- unknown publishing outcome

\- forged provider callbacks

\- duplicate provider callbacks

\- secrets leaking into rendered pages

\- secrets being stored in presentation state

\- AI-generated false claims

\- accidental exposure of internal-only business configuration

\- accidental exposure of quarantined/test data



All customer-supplied content must be treated as untrusted.



Escaping and sanitization should default to the framework's safest behavior.



Arbitrary HTML and JavaScript editing are prohibited in v12.0.



\---



\# 13. Publishing Boundary



Live publishing is NOT enabled in v12.0.



The system may model publishing lifecycle states such as:



\- DRAFT

\- PREVIEW\_READY

\- NEEDS\_ATTENTION

\- READY\_TO\_PUBLISH

\- PUBLISHING

\- PUBLISHED

\- PUBLISH\_FAILED

\- PUBLISH\_UNKNOWN



However, v12.0 should stop before performing a real hosting/domain/provider action.



Any future publishing capability must use a governed provider/action architecture consistent with v11.



Future publishing must support:



\- explicit policy evaluation

\- tenant verification

\- idempotency

\- provider abstraction

\- provider acknowledgement

\- outcome verification

\- retries only when safe

\- unknown outcome reconciliation

\- kill switches

\- system ledger

\- Attention escalation



Provider acceptance must never be treated automatically as successful publication.



\---



\# 14. Data Model Principles



Do not create schema simply because Website Studio is a new feature.



New tables are justified only when they represent genuinely new concepts.



Likely legitimate Website Studio concepts include:



\- website project/configuration

\- website draft/version

\- website presentation settings

\- publish/readiness state

\- future provider publication reference



Website-specific rows should reference canonical business records by foreign key.



Where practical, presentation state should store references to canonical entities rather than copies of canonical facts.



If snapshots of canonical information are required for version integrity, those snapshots must be clearly identified as historical presentation snapshots rather than new authoritative truth.



All new tables should follow existing Business OS database hardening and tenant-boundary practices.



\---



\# 15. Versioning



Website editing should not destroy the previous good state.



The architecture should support understandable version behavior.



At minimum:



\- edits occur in a draft state

\- the system can identify the current draft

\- an operator can distinguish current configuration from prior versions

\- preview uses an explicit version

\- later publishing will reference an explicit version

\- publishing a version in the future must not make newer unapproved draft edits live automatically



Versioning should remain simple enough for a small-business owner to understand.



Do not expose Git-like complexity to the user.



\---



\# 16. UX Principles



The visual authority remains the v9.2/v10.2 Business OS design language:



\- dark navy sidebar

\- clean light workspace

\- green accent

\- restrained premium SaaS appearance

\- readable hierarchy

\- consistent cards

\- subtle interaction

\- clarity before decoration



Website Studio itself should feel visually richer than an admin settings page because it contains a real site preview.



However, it must still feel like part of Business OS.



The owner should primarily see:



\- what their website looks like

\- what information Business OS is using

\- what is missing

\- what can safely be changed

\- whether the site is ready

\- how a customer request will enter Business OS



Avoid turning the screen into a dense technical configuration console.



\---



\# 17. Studio Interaction Model



Prefer guided editing over unrestricted construction.



A strong default layout is more valuable than dozens of controls.



Potential presentation controls include:



\- business logo reference when safely supported

\- accent/theme choice from constrained options

\- hero headline

\- hero supporting text

\- primary CTA wording

\- section visibility

\- about presentation

\- service ordering/display choices

\- trust/supporting copy

\- contact presentation

\- SEO title

\- SEO description



Canonical business facts should be visibly sourced from Business Configuration.



If a user wants to change an authoritative fact, Website Studio should send them to the correct configuration surface rather than silently overriding it.



\---



\# 18. Preview Architecture



Preview must be safe.



A preview must:



\- resolve the correct tenant

\- render an explicit draft/version

\- avoid live publishing

\- avoid leaking internal-only fields

\- escape unsafe content

\- render canonical verified data

\- render presentation overrides only in approved fields

\- support desktop/mobile inspection



Preview routes should be clearly distinguishable from future public production routes.



The system should not rely on obscurity of a preview URL as its only security mechanism for private drafts.



\---



\# 19. Public Website Architecture



The eventual customer-facing website should be intentionally thin.



It should consume prepared Website Studio presentation state and canonical business truth.



It should not contain business logic that belongs in internal services.



Public route responsibilities should be limited to things such as:



\- resolve business/site identity

\- load approved website version

\- render safe content

\- render canonical customer intake

\- validate customer submission

\- pass normalized submission into canonical lead creation

\- return safe customer confirmation/error states



The public website should not directly perform SMS, scheduling, provider actions, or ungoverned automation.



\---



\# 20. Lead Submission Reliability



Submission handling must be designed for real customer behavior.



The system should safely handle:



\- double-clicked submit buttons

\- browser retries

\- slow requests

\- repeated identical posts

\- invalid fields

\- partial intake

\- missing optional contact channels

\- large payloads

\- spam

\- server exceptions

\- database conflicts



The user must not receive a false success message if Business OS cannot safely determine that the lead was recorded.



Unknown write outcomes must be treated deliberately.



Never silently lose a customer request.



\---



\# 21. Observability



Website Studio should produce useful operational evidence without creating noisy telemetry.



Meaningful events may include:



\- website project created

\- draft updated

\- version created

\- preview generated

\- readiness changed

\- customer submission accepted

\- duplicate submission suppressed

\- submission rejected

\- canonical lead created

\- future publish attempt started

\- future publish outcome confirmed

\- website exception requiring Attention



Do not fabricate analytics.



Do not display impressive-looking metrics from tiny samples without clear semantics.



\---



\# 22. Accessibility



v12 should establish accessibility fundamentals from the beginning.



At minimum:



\- semantic page structure

\- usable keyboard navigation

\- visible focus states

\- form labels

\- useful error messages

\- sufficient contrast

\- responsive text/layout

\- meaningful button/link text

\- sensible heading order

\- reduced reliance on color alone

\- mobile usability



Accessibility should be treated as product quality, not an optional future polish task.



\---



\# 23. SEO Fundamentals



v12.0 may support restrained SEO presentation settings such as:



\- page title

\- meta description

\- canonical business name

\- meaningful headings

\- sensible page structure



SEO tooling must not invent keywords, claims, locations, or services unsupported by verified business information.



Advanced SEO is outside v12.0.



\---



\# 24. Release Safety



v12 must preserve every safety guarantee established before it.



In particular:



\- live provider delivery remains locked

\- simulation remains first-class

\- Retell safety rules remain unchanged

\- unknown tenant ownership fails closed

\- quarantine behavior remains unchanged

\- no client is activated merely for testing

\- no provider secrets are committed

\- .env remains ignored

\- business\_os.db remains ignored

\- SQLite hardening remains intact

\- v11 governed execution remains authoritative for provider actions

\- no live SMS

\- no live scheduling

\- no autonomous customer communication

\- no live website publishing



Website Studio is not permission to bypass existing governance.



\---



\# 25. Testing Requirements



v12 must include deterministic automated verification.



Tests should cover at minimum:



\- release/version identity

\- schema correctness

\- foreign keys

\- tenant isolation

\- Website Studio ownership

\- canonical service reuse

\- canonical intake reuse

\- canonical lead creation

\- source attribution

\- duplicate submission protection

\- malicious tenant identifiers

\- XSS escaping

\- unsafe URL rejection where relevant

\- CSRF behavior where relevant

\- malformed form input

\- missing configuration

\- draft/version behavior

\- preview behavior

\- public submission behavior

\- no live publishing path

\- no live SMS path

\- no live scheduling path

\- no provider bypass

\- existing v11 verifier compatibility

\- database integrity

\- release preflight



Existing v11 and v11.1 verification must continue passing unless an intentional forward-compatible verifier update is required.



\---



\# 26. Visual Acceptance



Automated tests are necessary but not sufficient.



Before v12 is tagged as a protected release, manually inspect:



\- Website Studio desktop layout

\- Website Studio mobile layout

\- preview desktop layout

\- preview mobile layout

\- empty state

\- incomplete business configuration state

\- configured business state

\- service section behavior

\- intake form behavior

\- validation errors

\- successful lead-submission state

\- duplicate-submission behavior

\- long business names

\- long service names

\- missing optional information

\- navigation continuity

\- responsive behavior

\- accessibility basics



Do not tag v12 merely because tests pass.



\---



\# 27. Release Process



Development should follow this sequence:



1\. Audit exact protected v11.1 source.

2\. Define v12 architecture.

3\. Define minimal schema changes.

4\. Implement service layer.

5\. Implement Website Studio routes.

6\. Implement Studio UI.

7\. Implement safe preview.

8\. Implement public customer intake.

9\. Route intake into canonical lead creation.

10\. Add verification scripts.

11\. Run existing v11/v11.1 verification.

12\. Run release preflight.

13\. Perform visual acceptance.

14\. Fix discovered issues.

15\. Re-run all verification.

16\. Commit.

17\. Tag.

18\. Push.

19\. Verify clean remote checkpoint.



Unexpected Git state must abort installation or release tooling rather than guessing.



\---



\# 28. Commercial Acceptance Test



v12 should be judged partly by whether a real business owner can understand the value quickly.



A compelling demonstration should be:



1\. Show Business Configuration.

2\. Enter verified business information.

3\. Open Website Studio.

4\. Show the website already understanding the business.

5\. Make a few simple presentation changes.

6\. Preview the professional customer-facing website.

7\. Submit an estimate/service request as a customer.

8\. Return to Business OS.

9\. Show the new canonical lead.

10\. Show the lead's structured intake and source.

11\. Show Business OS determining the appropriate next step.



If that sequence feels coherent, trustworthy, and useful, v12 is doing its job.



\---



\# 29. Decision Standard



When choosing between two implementations, prefer the one that improves:



1\. reliability

2\. clarity

3\. customer value

4\. safety and truthful behavior

5\. operator efficiency

6\. extensibility

7\. visual polish

8\. novelty



A feature should not be added merely because it is technically possible.



Every addition should answer at least one of these questions:



\- Does this help the business owner launch a credible front door?

\- Does this help a customer submit a useful request?

\- Does this help Business OS receive better structured information?

\- Does this improve safety or reliability?

\- Does this make the product easier to sell or operate?

\- Does this create a reusable architectural capability without unnecessary complexity?



If not, defer it.



\---



\# 30. v12 North Star



Website Studio succeeds when Business OS can truthfully demonstrate:



"We understand your business once, use that verified information to create your customer-facing front door, capture real customer demand, and carry that demand into the same operating system that manages what happens next."



That is the v12 product.



Not a website builder.



A front door to Business OS.
