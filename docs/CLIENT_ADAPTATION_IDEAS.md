# AIONEX Client Adaptation Ideas

> Status: Private pre-release discovery material. **AIONEX** is product presentation branding only. Every item below is an idea or delivery option, not a currently implemented feature, price, commitment, endorsement, or guaranteed result.

## Adaptation principle

Preserve the core separation between deterministic product policy and probabilistic generation. A client adaptation should change identity, data sources, schemas, resources, terminology, and workflows through reviewed interfaces rather than moving authorization, compliance, or external actions into a model prompt.

No adaptation should be proposed until the client's data classification, jurisdiction, provider terms, threat model, accessibility needs, retention obligations, and measurable decision workflow are understood.

## Foundation work before client data

| Capability | Why it comes first | Evidence required |
| --- | --- | --- |
| Account authentication and authorization | The current signed browser namespace is not a client identity system | tenant-bound object tests, session rotation/revocation, recovery and admin controls |
| Protected persistence | SQLite is plaintext and local | encryption, managed secrets, backups, retention, deletion evidence, migration and restore tests |
| Deployment security | The current target is local/private | TLS, trusted proxies, host policy, CSRF review, secure cookies, monitoring, incident response and independent testing |
| Provider governance | Live calls can carry client context and contractual duties | approved providers, DPA/terms review, attribution, geography, retention, cost limits and shutdown procedure |
| Durable abuse and cost controls | In-memory limits do not scale | shared rate limits, queues, idempotency, budgets, audit events and alert thresholds |
| Evaluation framework | Schema-valid output can still be wrong | domain fixtures, human rubric, source checks, hallucination tests, accessibility and failure-mode acceptance criteria |

## Vertical workflow ideas

These are discovery directions, not out-of-the-box claims.

### Professional-services opportunity review

- adapt B2B intake to service scope, utilization, buyer role, sales cycle, delivery capacity, and conflict checks;
- connect only approved CRM or proposal systems through a reviewed adapter;
- generate a decision memo and reversible validation plan rather than an automatic bid;
- require human approval before any external communication.

### Procurement and supplier-risk workspace

- add client-owned supplier records and jurisdiction-specific review fields;
- use licensed or official procurement and risk data with preserved attribution;
- separate observed supplier facts, client assertions, model inferences, and unresolved gaps;
- add expiry dates and owners for evidence and compliance documents;
- do not represent the result as a legal clearance or supplier certification.

### Workforce and skills planning

- tailor B2C/B2B intake to role families, skills evidence, location, time, budget, and accessibility needs;
- connect approved internal learning catalogs rather than recommending invented resources;
- measure plan completion and validated skill evidence, not guaranteed employment or salary;
- avoid protected-trait inference and review employment-law implications.

### Regulated-market research triage

- restrict the product to research organization and question routing;
- use client-approved official sources and a jurisdiction field that cannot be silently inferred;
- label every legal, medical, financial, safety, or compliance question for qualified human review;
- prohibit autonomous recommendations where professional judgment is required.

### Internal innovation portfolio

- adapt analyses into comparable hypothesis, evidence, risk, budget, checkpoint, and stop-condition records;
- add role-based review and decision logs;
- compare projects using transparent client-defined criteria rather than opaque model scoring;
- keep “selected,” “funded,” and “successful” as separate states.

## Product-surface options

### Branded private workspace

- client typography, color, terminology, and domain while preserving accessibility and status clarity;
- configurable sections driven by validated schemas;
- explicit environment indicator for demo, test, and controlled live modes;
- client-owned privacy notice and support route once formally established.

### Review and approval workflow

- draft, reviewer, approver, and archived states;
- field-level provenance and comments;
- immutable decision snapshots and redacted export;
- no model-triggered external action without explicit human approval.

### Evidence workspace

- client-approved connector registry;
- source owner, license, attribution, collection time, effective date, expiry, jurisdiction, and confidence fields;
- stale-evidence alerts and manual verification tasks;
- provider-specific circuit breakers and deletion workflows.

### Evaluation dashboard

- schema conformance, evidence coverage, reviewer agreement, correction categories, latency, and approved cost measures;
- separate demo fixtures, offline regression, and live integration suites;
- minimum sample sizes and visible uncertainty for calibration;
- no “accuracy” headline without a defined labeled dataset and reproducible method.

## Integration strategy

1. **Discover:** map the real decision, accountable role, inputs, outputs, systems, harms, and stop conditions.
2. **Classify:** identify personal, confidential, regulated, licensed, and export-controlled data.
3. **Constrain:** define provider allowlists, schemas, budgets, retention, jurisdictions, and forbidden actions.
4. **Prototype offline:** use synthetic fixtures and deterministic adapters.
5. **Evaluate:** compare against a documented human baseline and failure rubric.
6. **Pilot privately:** use a small approved group, least-privilege credentials, monitoring, and reversible migration.
7. **Gate expansion:** require security, privacy, legal, accessibility, provider, and operational sign-off.

## Packaging options to explore

| Option | Appropriate when | Main caution |
| --- | --- | --- |
| Local evaluation package | a team needs workflow discovery with synthetic data | not a shared account system and not encrypted by default |
| Single-organization private deployment | one organization accepts managed operational ownership | requires identity, protected storage, monitoring and provider governance first |
| Embedded decision module | a host product already owns identity and records | authorization and deletion boundaries must remain enforceable across systems |
| Client-managed provider mode | the client owns credentials and contracts | credential isolation, billing, retention and incident responsibilities must be explicit |
| Fully offline rules-only mode | external providers are prohibited | capability is narrower; do not imply live evidence or AI reasoning |

## Ethical adoption ideas

- publish a precise capability and limitation sheet instead of outcome promises;
- offer a synthetic-data workshop before requesting any client content;
- demonstrate source degradation, memory consent, deletion boundaries, and offline behavior—not only ideal results;
- define success as a measurable workflow improvement such as reduced review omissions or faster evidence organization, then measure it honestly;
- avoid urgency, fabricated scarcity, fake testimonials, invented customer logos, or unsupported ROI;
- make cancellation, export, deletion, and provider responsibilities understandable before a pilot.

## Non-negotiable exclusions

Do not adapt the current pre-release into:

- autonomous trading, purchasing, hiring, legal approval, medical direction, or safety-critical control;
- covert employee, applicant, customer, or citizen profiling;
- an internet-facing multi-tenant service without the foundation controls above;
- a system that removes provider attribution or presents stale/model-generated content as verified fact;
- a product that promises profit, compliance, accuracy, procurement success, or another guaranteed outcome.

Related documents: [Architecture](ARCHITECTURE.md), [Security Model](SECURITY_MODEL.md), [User Flows](USER_FLOWS.md), and [Case Study](CASE_STUDY.md).
