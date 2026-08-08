# AIONEX Architecture Decision Log

> Status: Private pre-release decision log. **AIONEX** is product presentation branding only. Decisions describe the current engineering tradeoffs and can be revised when deployment evidence changes.

## How to use this log

For a material architecture change, add a numbered decision entry that records context, decision, consequences, verification, and a review trigger. “Accepted” means accepted for the current private pre-release, not approved for unrestricted production use.

## Decision index

| ID | Decision | Pre-release status | Review trigger |
| --- | --- | --- | --- |
| 0001 | Keep a modular single-process FastAPI architecture | Accepted | Multiple workers, independent scaling, or availability requirements |
| 0002 | Use SQLite for local transactional persistence | Accepted with limits | Sensitive data, concurrent service instances, encryption, or high availability |
| 0003 | Use a signed anonymous browser-session namespace | Temporary | Any public, multi-user, cross-device, or client deployment |
| 0004 | Make demo and CI deterministic and network-free by default | Accepted | Any new adapter, background worker, telemetry, or external asset |
| 0005 | Constrain AI output with schemas and deterministic policy layers | Accepted | Provider or SDK change, new autonomous action, or new regulated domain |
| 0006 | Route intelligence only through a fixed source registry | Accepted | New provider, user-configurable connector, or proxy behavior |
| 0007 | Keep outbound execution resources allowlisted | Accepted | Editable catalogs, plugins, or model-generated destinations |
| 0008 | Separate transient request facts from opt-in durable memory | Accepted | New personalization, imports, synchronization, or retention rules |
| 0009 | Preserve provider attribution and confidence limitations | Accepted | New evidence scoring, aggregation, licensing, or customer-facing claim |
| 0010 | Use hash-locked offline Windows/Python 3.14 CI | Accepted | Platform support expansion or dependency-management change |

## 0001 — Modular single-process FastAPI architecture

**Context:** The project benefits from a zero-friction local runtime and clear Python module boundaries.

**Decision:** Keep HTTP orchestration in `app.py` and separate intake, AI, intelligence, resources, and persistence into dedicated modules.

**Consequences:** Local setup and test seams remain simple. In-memory limits and tasks are process-local, and components cannot scale independently.

**Verification:** module-focused tests plus end-to-end API tests.

## 0002 — SQLite local persistence

**Context:** Analyses, messages, goals, memory, predictions, leases, and usage require transactional persistence without an external service.

**Decision:** Use SQLite with foreign keys, write locking, busy timeout, transactions, and WAL mode.

**Consequences:** The product remains portable and inspectable. Data is plaintext, backup and encryption are operator responsibilities, and multi-instance availability is out of scope.

**Review trigger:** any sensitive/client data or public deployment.

## 0003 — Signed anonymous browser-session namespace

**Context:** Local evaluation needs isolation without account onboarding.

**Decision:** Issue a random identifier in an HMAC-signed HTTP-only, SameSite cookie and scope store access to it.

**Consequences:** Simple local continuity and resistance to identifier guessing. This is not identity verification; cookie theft grants namespace access, and there is no recovery, role, MFA, or revocation system.

**Review trigger:** replace or augment before public, multi-user, or cross-device use.

## 0004 — Network-free demo and CI defaults

**Context:** Evaluation and automated tests must not spend provider funds, leak test data, or depend on internet availability.

**Decision:** Use deterministic AI demonstration data, return offline intelligence before HTTP-client construction, disable prediction networking, and store CI data in a runner-temporary database.

**Consequences:** Repeatable safe evaluation. Demo output cannot validate current evidence or live integration.

**Verification:** zero-fetch intelligence tests and the checked-in CI environment.

## 0005 — Schema-constrained AI with deterministic policy

**Context:** Free-form generation is unsuitable for persistence, rendering, budgeting, and downstream decisions.

**Decision:** Use strict Pydantic output types, constant instructions, bounded payloads, typed errors, no hidden retries, and final validation. Keep identity, memory writes, URLs, source routing, confidence caps, and storage authorization outside the model.

**Consequences:** Predictable data shape and clearer failure handling. Schema validity does not prove factual truth.

## 0006 — Fixed public-source registry

**Context:** Arbitrary user-controlled URLs or upstream query interpolation would expand SSRF, privacy, and attribution risk.

**Decision:** Infer routing tags locally and select only registered adapters with fixed destinations and declared metadata.

**Consequences:** Smaller attack surface and more truthful provenance. Coverage is intentionally limited, and each provider's changing terms still require review.

## 0007 — Allowlisted execution resources

**Context:** A model can invent convincing but unsafe links.

**Decision:** Select resources from a validated local catalog by deterministic intent and jurisdiction tags.

**Consequences:** Stable destinations and testability. Catalog owners must maintain links, suitability, cost claims, and terms.

## 0008 — Explicit durable-memory consent

**Context:** Useful request facts should not silently become a long-lived profile.

**Decision:** Use extracted facts for current context and require a separate confirmation endpoint for durable memory. Provide a forget action.

**Consequences:** Better user control. The operator still needs retention, backup, deletion, and provider-data policy.

## 0009 — Attribution and constrained confidence

**Context:** Source quantity, freshness, and independence are easy to overstate.

**Decision:** Expose provider/source/date/cache/freshness/limitations and cap confidence based on independent usable evidence.

**Consequences:** More honest results and visible degradation. Scoring remains a heuristic, not a statistical guarantee or legal assessment.

## 0010 — Hash-locked Windows/Python 3.14 CI

**Context:** The declared target needs reproducible validation without live credentials.

**Decision:** Run Ruff and pytest on Windows/Python 3.14 after `--require-hashes` installation from the development lock, with least GitHub token permissions and offline/demo settings.

**Consequences:** Stronger reproducibility for the declared target. Hashes and CI success do not certify package provenance, third-party actions, or deployment security.

## Required format for future decisions

```text
## NNNN — Short decision title

Context:
Decision:
Alternatives considered:
Consequences:
Verification:
Review trigger:
```

Related documents: [Architecture](../ARCHITECTURE.md), [Technical Deep Dive](../TECHNICAL_DEEP_DIVE.md), and [Security Model](../SECURITY_MODEL.md).
