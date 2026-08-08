# AIONEX Technical Deep Dive

> Status: Private pre-release engineering documentation. **AIONEX** is product presentation branding only. This document describes inspected behavior; it is not a certification, public-launch statement, or performance guarantee.

## Engineering objective

The central engineering problem is to turn incomplete user context and optional external evidence into useful, structured decision support without disguising uncertainty. The implementation combines deterministic policy layers with a bounded AI gateway. Deterministic code owns validation, identity, source selection, memory consent, persistence, usage controls, resource URLs, and confidence caps. The model is used only for schema-constrained analysis, follow-up, and deep-dive generation when live AI mode is explicitly configured.

## Boundary 1: request admission

Mutation requests pass through a body-size guard before JSON validation. The middleware handles both declared `Content-Length` and streamed bodies, drains oversized input, and avoids retaining over-limit chunks. Request models use Pydantic with `extra="forbid"`, bounded strings, and explicit enums. The API returns stable English error structures.

Every response receives a request identifier and defensive headers. API responses are marked `no-store`. The product UI receives a strict same-origin content-security policy; opt-in developer documentation routes use a separate, more permissive policy because FastAPI documentation relies on inline and CDN assets.

These measures reduce common accidental exposure and parser abuse. They do not replace reverse-proxy limits, TLS, host policy, distributed abuse controls, or an authenticated user model.

## Boundary 2: anonymous session namespace

The server creates a random client identifier and signs it with HMAC-SHA256. The cookie is HTTP-only, SameSite=Lax, and can be marked Secure through configuration. The signature prevents a caller from simply choosing another identifier. Store reads and writes include that identifier when they access user-visible records.

The cookie is not encrypted and does not identify a verified person. It behaves as a bearer credential for a local anonymous namespace. This distinction matters: a valid cookie can authorize access to its associated local history even though no account login occurred. Internet-facing adaptation therefore requires a replacement or augmentation with real authentication, session revocation, CSRF analysis, and object-level authorization tests.

## Boundary 3: deterministic intake and memory consent

Intake questions and answer validation are local operations. Extracted facts can shape the current analysis without automatically becoming durable profile memory. Long-lived memory is written only through the explicit memory-confirmation endpoint, and the profile endpoint can clear it.

Model-proposed memory items are candidates, not silent writes. This is an important consent boundary, but operators must still define retention, deletion, access, and backup policies. SQLite does not cryptographically erase deleted content from prior backups or storage snapshots.

## Boundary 4: public intelligence routing

The intelligence router follows these stages:

1. Normalize the query and bounded local context.
2. Infer a deterministic taxonomy such as technology, regulation, geography, hazards, or procurement.
3. Rank a bounded set of registered fixed adapters, preferring authority and evidence-layer diversity.
4. Return immediately with a deterministic degraded envelope when offline policy applies.
5. Fetch selected adapters concurrently through a response-size-bounded HTTP client.
6. Apply per-source timeouts, cache TTLs, stale-if-error windows, locks, and short failure backoff.
7. Normalize each stream with canonical provider attribution and evidence-quality metadata.

Raw user text is not forwarded into an arbitrary upstream URL, query language, or user-selected host. The registry controls destinations. Individual adapters may make multiple fixed requests, so both adapter timeouts and an outer wall-clock limit are used.

Each stream distinguishes:

- provider and attribution URL;
- observation `as_of` time when supplied by the source;
- fresh-cache, stale-cache, miss, bypassed, or unavailable state;
- observation age and freshness score;
- official, public, or community authority classification;
- completeness, routing relevance, weighted evidence quality, and limitations.

A successful HTTP response is not automatically high-confidence evidence. Old observations, missing fields, stale cache use, low authority, or weak routing relevance reduce the weighted contribution. A source outage becomes a degraded record rather than fabricated data.

## Boundary 5: structured AI generation

The AI gateway serializes query, strategy, history, memory, and evidence into a user-data payload under constant system instructions. Those instructions explicitly treat every payload value as untrusted data and reject embedded role changes, schema escapes, prompt extraction, and invented citations.

Generation is bounded by:

- separate Pydantic output schemas for B2C, B2B, chat, and deep dive;
- fixed cost-profile model choices and capped output tokens;
- maximum query, context, and history sizes;
- a concurrency semaphore and hard timeouts;
- no hidden SDK retries for paid requests;
- typed provider-error translation;
- final strict validation of parsed output;
- provider usage capture for the local ledger;
- `store=False` on the configured Responses API request.

Structured validation proves shape, not truth. The application therefore keeps external evidence, data gaps, assumptions, risk items, and confidence logic visible. Live provider output can still be incomplete, mistaken, or unsuitable for a jurisdiction.

## Boundary 6: confidence and falsifiability

Confidence is capped by the count of independent usable providers rather than raw stream count or weighted coverage alone. Multiple records from one provider do not become multiple independent confirmations. Degraded sources do not count as usable.

The application can translate model-suggested measurable claims into predictions with a recorded baseline and future resolution window. A deterministic resolver can compare supported metrics later, and calibration aggregates outcomes. Prediction networking is opt-in and separate from analysis intelligence.

Calibration is a local diagnostic, not proof of future accuracy. Small samples, changing conditions, selection effects, and unsupported metrics can make a win rate misleading. The UI and documentation must not present it as an audited track record.

## Boundary 7: durable coordination and cost controls

SQLite transactions retain analyses, messages, goals, predictions, usage events, generation leases, and budget reservations. Leases reduce duplicate concurrent generation for the same fingerprint. Durable per-client and global reservations bound eligible AI operations before the provider call; recorded usage captures available token metadata afterward.

The application also uses in-memory sliding-window limits for short bursts. These reset on process restart and do not coordinate multiple processes. A scaled deployment needs an external rate-limit and job-coordination service plus idempotency guarantees appropriate to its provider contract.

## Boundary 8: execution resources

The execution-kit layer is deterministic and uses an allowlisted resource catalog. The AI is not trusted to invent outbound URLs. Jurisdiction and intent tags narrow selected resources, and catalog validation rejects destinations outside the declared allowlist.

An allowlisted URL is not a legal endorsement or a promise that a service remains free, available, suitable, or correctly licensed. Catalog maintenance and periodic link/provider review are required.

## Failure behavior

| Failure | Current behavior | Residual concern |
| --- | --- | --- |
| Offline or demo intelligence | Returns deterministic degraded streams before creating an HTTP client | Analysis has less external evidence and confidence should remain constrained |
| One public source fails | Other branches continue; eligible stale data is labeled and penalized | Stale data may still be unsuitable for a fast-moving decision |
| AI credential missing or rejected | Typed configuration error; no synthetic live claim | Operator must select demo mode or configure a valid account |
| AI timeout, rate limit, or invalid schema | Typed error with bounded handling and available usage metadata | A user operation can remain incomplete and may require a later retry |
| Duplicate generation | Lease and cache logic reduce duplicate paid calls | Multi-process correctness requires stronger shared coordination |
| SQLite unavailable | Health readiness reports storage failure | No automatic failover or encrypted backup exists |

## Verification strategy

The checked-in CI workflow runs on Windows with Python 3.14, installs [`requirements-dev.lock`](../requirements-dev.lock) with `--require-hashes`, sets demo and offline modes, uses a temporary database, runs Ruff, and executes the test suite. This verifies deterministic behavior without requiring an AI credential or public-data network access.

Live integration checks must be separate, explicitly authorized, and clearly labeled. They must respect provider test modes, terms, attribution, cost, and data-handling obligations. Passing offline CI does not certify a live provider, a deployment, or a business outcome.

See [Architecture](ARCHITECTURE.md), [Security Model](SECURITY_MODEL.md), and [Decision Log](DECISIONS/README.md).
