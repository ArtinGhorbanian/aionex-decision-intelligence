# AIONEX Roadmap

> **Gate-based planning, not a delivery promise.** AIONEX is a private pre-release. This roadmap has no committed dates, staffing assumptions, public milestones, or guarantee that any phase will be completed or released.

## Current position

The repository supports controlled local evaluation with deterministic demo output, explicit offline controls, an English browser workspace, local SQLite persistence, and automated checks. Public and commercial release remain blocked by rights and provider clearance.

## Guiding principles

- Evidence before claims.
- Offline and demo behavior before live-provider convenience.
- Human review before consequential action.
- Explicit consent for long-term memory.
- Source attribution and freshness before confidence.
- Secure defaults before public reach.
- Documented rights before distribution.
- No hidden network, cost, ownership, partnership, or readiness claims.

## Gate 1: Rights and provenance

Exit criteria:

- identify original authors and contributors through appropriate private records;
- document grants, assignments, or licenses for code, copy, designs, datasets, and assets;
- determine any competition, classroom, employment, client, or team obligations;
- record provenance for current and future visual assets;
- replace the temporary no-license position only after authorized review;
- document who can approve distribution and under what continuing restrictions.

Reference: [RIGHTS_CLEARANCE.md](RIGHTS_CLEARANCE.md).

## Gate 2: Provider and attribution clearance

Exit criteria:

- review each enabled AI and public-data provider's current acceptable-use, privacy, retention, training, pricing, licensing, attribution, and rate-limit terms;
- determine permitted data classes and jurisdictions;
- preserve required provider and source attribution;
- remove or disable any adapter whose conditions cannot be met;
- document live-evaluation authorization and a provider shutdown path;
- keep default tests and demonstrations network-free.

Reference: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Gate 3: Identity, storage, and application security

Exit criteria for any deployment beyond trusted local evaluation:

- choose and implement an authenticated account and authorization model;
- add session rotation, revocation, recovery, and administrative controls;
- complete a deployment-specific CSRF, CORS, host, TLS, proxy, and secure-cookie review;
- establish secret management and rotation;
- choose encryption-at-rest, backup, retention, deletion, and restore policies;
- replace process-local rate controls when multi-process or multi-host operation requires it;
- add security monitoring, redaction, incident handling, and independent testing appropriate to the intended environment.

Reference: [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

## Gate 4: Product evidence and evaluation quality

Exit criteria:

- define representative decision-support evaluations without fabricated users, testimonials, or outcomes;
- test schema validity, source attribution, freshness handling, refusal and degraded paths, and cost bounds;
- document known failure modes and human-review requirements;
- evaluate keyboard, screen-reader, contrast, zoom, reduced-motion, and responsive behavior;
- capture real reviewed screenshots with synthetic data and no secrets;
- ensure product copy matches observed behavior in demo, offline, degraded, and authorized live modes.

## Gate 5: Operational readiness decision

Only after earlier gates are satisfied should authorized reviewers decide whether to pursue a controlled release. A positive decision would still require:

- a defined audience and access model;
- deployment architecture and rollback plan;
- monitoring, backup, recovery, and support ownership;
- privacy, terms, provider, attribution, and accessibility review;
- release artifacts that contain no local databases, secrets, personal data, or uncleared assets;
- a final license and notice package supported by the rights evidence.

This gate may result in continued private development or no release.

## Deferred unless separately authorized

- public multi-tenant hosting;
- regulated or confidential client-data processing;
- autonomous financial, procurement, legal, compliance, medical, or safety execution;
- third-party transactions or outbound communication without human confirmation;
- public integrations, marketplaces, mobile stores, or commercial plans;
- claims of certification, endorsement, partnership, guaranteed accuracy, or guaranteed outcomes.

## Maintaining this roadmap

Update the roadmap when a gate, constraint, or evidence requirement changes. Keep completed repository work in [CHANGELOG.md](CHANGELOG.md). Do not convert an aspiration into a public commitment without written authorization and evidence.
