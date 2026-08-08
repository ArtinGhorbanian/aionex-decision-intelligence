# AIONEX Engineering Case Study

> Status: Private pre-release case study. **AIONEX** is used only as product presentation branding. This document records an engineering direction and inspected implementation evidence; it is not a customer testimonial, public-release announcement, audited benchmark, or claim of commercial success.

## Context

The project began as a local strategy-analysis application with valuable domain workflows: B2C and B2B intake, structured AI analysis, live evidence, follow-up conversation, goals, predictions, calibration, and a persistent vault. The engineering challenge was not to replace that identity. It was to make the existing work more explicit, bounded, testable, honest about uncertainty, and safer to evaluate.

The current pre-release remains intentionally compact: one FastAPI process, a browser interface, local SQLite persistence, optional public-source adapters, and an optional AI provider. That simplicity is useful for local evaluation, but it creates clear limits around identity, encryption, scaling, and public deployment.

## Problem statement

A strategy product can become misleading or expensive when it blurs any of these boundaries:

- synthetic demonstrations versus live provider output;
- a source observation versus a model inference;
- many records versus independent evidence;
- current data versus stale cached data;
- transient request facts versus durable memory;
- an anonymous browser namespace versus an authenticated account;
- an action plan versus a guaranteed result;
- a convenient local database versus protected production storage.

The transformation objective was therefore measurable in engineering terms: establish deterministic modes, strict interfaces, source provenance, explicit consent, bounded provider behavior, durable coordination, accessible English presentation, and repeatable offline validation.

## Constraints

- Preserve the B2C/B2B distinction and the existing analysis, chat, deep-dive, vault, goal, and prediction workflows.
- Keep local setup practical and avoid requiring paid calls for tests or demos.
- Do not fabricate providers, live observations, screenshots, users, adoption, revenue, or performance improvements.
- Treat public-data terms, AI-provider terms, attribution, privacy, and jurisdiction as operator obligations.
- Keep generated URLs outside the model trust boundary.
- Make pre-release limitations prominent rather than hiding them in release notes.

## Engineering response

### Deterministic policy around the model

The application assigns deterministic code responsibility for intake, validation, source routing, confidence caps, memory writes, resource selection, ownership checks, persistence, usage budgets, and prediction comparison. The AI provider is confined to schema-validated analysis tasks.

This division does not make model output true. It makes failures easier to detect and prevents the model from silently controlling high-risk boundaries such as storage authorization or outbound URLs.

### Honest evidence handling

The public-intelligence layer selects registered fixed providers from local routing tags. Each returned stream can expose provider, source URL, observation date, cache state, freshness, authority, completeness, relevance, weighted quality, and a limitation. Sources fail independently, and stale fallback is labeled and penalized.

Unofficial automated market endpoints were removed from active routing. Demo and explicit offline modes now return before HTTP-client construction, so the network-free claim is testable rather than aspirational.

### Bounded provider use

The AI gateway caps input, history, output tokens, concurrency, and duration. It disables hidden retries for paid calls, requests non-storage where the provider interface supports it, maps provider failures into typed errors, and validates parsed output against strict schemas.

SQLite-backed leases and budget reservations reduce duplicate generation and bound eligible operations. In-memory burst limits add a local guard but are documented as non-distributed and restart-sensitive.

### Consent and local persistence

Extracted facts can shape one analysis without automatically becoming durable profile memory. A separate explicit confirmation writes memory, and the user can clear it. Analyses, messages, goals, predictions, and usage are stored transactionally under a signed anonymous browser-session identifier.

The implementation deliberately calls this a namespace rather than an account. SQLite is plaintext, the cookie is a bearer credential, and the current identity model is insufficient for a public multi-user service.

### Product and repository clarity

The product presentation is English and labels service, source, cache, freshness, memory, cost, and AI-use states. Repository scaffolding runs an offline Windows/Python 3.14 gate with hash-locked dependencies, Ruff, and pytest. Issue and pull-request templates explicitly reject secrets, hidden network calls, fabricated claims, and public security disclosures.

## Evidence map

| Engineering claim | Inspectable evidence |
| --- | --- |
| Strict request and output schemas | [`app.py`](../app.py), [`omni_ai.py`](../omni_ai.py), and schema-focused tests in [`tests/`](../tests/) |
| Opt-in memory persistence | profile-memory routes in [`app.py`](../app.py) and storage functions in [`omni_store.py`](../omni_store.py) |
| Fixed, attributed public-source routing | [`omni_intelligence.py`](../omni_intelligence.py) and [`tests/test_intelligence.py`](../tests/test_intelligence.py) |
| Deterministic allowlisted resources | [`omni_resources.py`](../omni_resources.py) and resource tests in [`tests/`](../tests/) |
| Anonymous namespace and transactional storage | middleware in [`app.py`](../app.py), schema and queries in [`omni_store.py`](../omni_store.py) |
| Offline, hash-locked CI | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) and [`requirements-dev.lock`](../requirements-dev.lock) |
| Explicit caveats and deployment gates | [Security Model](SECURITY_MODEL.md), [Architecture](ARCHITECTURE.md), and [Decision Log](DECISIONS/README.md) |

## Qualitative outcome

The current revision is easier to evaluate because important states are explicit and executable:

- a reviewer can run the full product path without a network or paid provider;
- a source outage becomes visible degradation rather than a false live claim;
- model output must match a declared schema before persistence;
- memory requires a separate affirmative action;
- confidence depends on independent usable evidence;
- provider use and usage limits have inspectable boundaries;
- the repository has a reproducible, least-privilege validation gate.

No percentage improvement is claimed because no controlled before-and-after benchmark was recorded. No claim is made about public uptime, adoption, conversion, revenue, model accuracy, or client outcomes.

## Remaining gaps

The pre-release still needs authenticated accounts, session revocation, deployment-specific CSRF analysis, encryption at rest, managed secrets, durable distributed rate limiting, backup and deletion policy, observability, incident response, provider/legal review, and independent security testing before public or sensitive use.

Provider output and public data can remain wrong, stale, incomplete, or unsuitable. Calibration can remain statistically weak. The product is a decision-support workspace, not an autonomous execution service and not a guarantee.

## Reusable lesson

The strongest part of this architecture is not a single model prompt or visual effect. It is the separation between deterministic product policy and probabilistic generation. That separation lets a future client adaptation replace providers, storage, identity, or presentation without discarding the core intake and strategy workflow.

Related documents: [Technical Deep Dive](TECHNICAL_DEEP_DIVE.md), [Demo Script](DEMO_SCRIPT.md), and [Client Adaptation Ideas](CLIENT_ADAPTATION_IDEAS.md).
