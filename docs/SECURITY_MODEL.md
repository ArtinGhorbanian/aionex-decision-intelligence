# AIONEX Security Model

> Status: Private pre-release security documentation. **AIONEX** is product presentation branding only. This is a design review of current controls and limitations, not a penetration-test report, compliance certification, security warranty, or authorization for public deployment.

## Security objective

The current application aims to make local evaluation predictable, limit accidental data exposure, constrain paid and public-provider calls, isolate records by an anonymous browser namespace, and fail safely when providers are unavailable. The highest-priority properties are:

- no hidden network activity in the documented offline demo and CI paths;
- bounded and strictly validated input and model output;
- explicit memory consent;
- source attribution and honest freshness states;
- same-origin browser behavior and defensive response headers;
- transactional local persistence and bounded provider usage;
- no secret, personal data, or local database committed to source control.

## Scope and assumptions

This model covers the checked-in FastAPI application, browser assets, local SQLite store, public-intelligence adapters, AI gateway, and GitHub CI configuration. It assumes a trusted local operator, a current Windows/Python environment, same-origin access, and controlled credentials.

It does not assume that the application is safe for untrusted internet users, multiple organizations, regulated data, high-value secrets, autonomous financial execution, or safety-critical decisions.

## Assets

- user questions, clarification answers, and generated strategies;
- explicitly confirmed profile memory;
- message history, goals, predictions, and usage records;
- anonymous session identifiers and signing secret;
- AI provider credential and account budget;
- local database integrity and availability;
- source attribution, freshness, and confidence metadata;
- curated resource allowlist and provider configuration.

## Trust boundaries

| Boundary | Trusted side | Untrusted or conditional side |
| --- | --- | --- |
| Browser to FastAPI | Server validation and namespace checks | Browser state, headers, cookies, and all submitted content |
| FastAPI to SQLite | Parameterized store functions and transactions | Filesystem access, copied databases, backup policy, and local host compromise |
| Router to public providers | Fixed registry, HTTPS destinations, bounds, and parsing | Availability, response content, terms, accuracy, and rate limits |
| Gateway to AI provider | Constant instructions, bounded payload, schemas, and typed errors | Provider output, service availability, account settings, and provider-side handling |
| Model to resource layer | Validated structured intent | Model-suggested URLs or claims, which are not trusted as catalog entries |
| CI to repository | Read-only job token and hash-locked dependencies | Third-party actions, runner image, package registries, and future dependency updates |

## Implemented controls

### Request and browser controls

- mutation-body size limits cover both `Content-Length` and streamed bodies;
- strict Pydantic models reject unknown fields and enforce bounds;
- API errors are normalized to stable English structures;
- response headers include CSP, frame denial, MIME sniffing protection, referrer policy, permissions policy, request identifiers, and API `no-store`;
- the main UI CSP permits only same-origin scripts, styles, fonts, images, and connections;
- cookies are HTTP-only and SameSite=Lax; the Secure attribute is configurable and must be enabled behind HTTPS;
- short-burst limits consider both anonymous client identifier and a hashed remote address;
- API documentation is disabled by default.

### Identity and object isolation

- the anonymous identifier is random and validated against a narrow format;
- HMAC-SHA256 protects the cookie against simple identifier substitution;
- `compare_digest` is used for signature comparison;
- user-visible store operations scope records to the current client identifier;
- legacy-vault transfer is disabled unless a separate operator token is configured.

### Provider and cost controls

- AI credentials are read from the environment and are not accepted from request payloads;
- paid provider requests have hard token, input, history, concurrency, and timeout ceilings;
- hidden provider retries are disabled;
- structured output is parsed and strictly validated before use;
- generation leases and durable reservations reduce duplicate or over-budget calls;
- public adapters use fixed registered destinations, response-size caps, timeouts, source locks, caching, stale labeling, and failure backoff;
- demo/offline intelligence returns before HTTP-client construction;
- prediction networking and its background sweeper require separate explicit opt-ins.

### Data-minimization controls

- intake and execution-kit generation can run deterministically without a model;
- raw user text remains local during public-source route selection;
- external evidence is compacted before AI use;
- provider calls request `store=False` where supported by the configured API;
- profile memory persists only after explicit confirmation;
- vault summaries omit bulky raw evidence and execution details;
- outbound execution resources come from a validated allowlist.

### Supply-chain and CI controls

- runtime and development lock files carry hashes;
- CI installs the development lock with `--require-hashes`;
- CI uses Windows and the declared Python 3.14 target;
- CI sets demo mode, the canonical offline switch, disabled prediction networking, and a runner-temporary database;
- the GitHub Actions token receives only `contents: read`;
- Dependabot checks Python and GitHub Actions dependencies on a bounded weekly schedule.

## Threat analysis

| Threat | Current mitigation | Residual risk / required follow-up |
| --- | --- | --- |
| Session identifier tampering | HMAC signature and strict identifier format | Stolen cookies remain bearer credentials; add account auth, rotation, revocation, and device/session management before public use |
| Cross-site request abuse | SameSite=Lax, same-origin UI, strict CSP, bounded models | There is no explicit CSRF token; perform a deployment-specific CSRF and CORS review |
| Prompt injection | Constant instructions, untrusted-data serialization, schema validation, deterministic URL layer | Models can still misunderstand or produce plausible errors; keep human review and evidence checks |
| SSRF through intelligence | Fixed registry and no user-selected provider host | Adapter or registry changes require security review; proxy configuration remains operator-controlled |
| Oversized or malformed input | Stream-aware size limit and strict schemas | Reverse proxy and server limits should add defense in depth |
| Paid-call duplication or cost abuse | rate limits, leases, reservations, concurrency and token caps, no hidden retry | In-memory limits reset and do not coordinate processes; public hosting needs distributed enforcement |
| Provider outage or stale data | failure isolation, cache state, stale penalties, degraded records | Stale evidence can still mislead; users must check observation date and source |
| Local data disclosure | namespace-scoped queries and signed cookie | SQLite and session-secret files are plaintext; host/file access exposes data |
| Dependency compromise | hash-locked CI install and update monitoring | Hashes do not prove package trust; action revisions and dependency updates still require review |
| Misleading product claims | demo/live labels, evidence metadata, confidence caps, caveats | Operators and downstream adaptations must preserve the wording and avoid guarantees |

## Known limitations

These are explicit pre-release constraints, not deferred footnotes:

1. **Plaintext SQLite:** analyses, messages, memory, goals, predictions, and usage metadata are stored in an ordinary SQLite file. There is no application-level encryption at rest.
2. **Anonymous browser-session identity:** the signed cookie identifies a local namespace only. It is not a user account and provides no identity verification, password, multi-factor authentication, role, recovery, or audit-grade attribution.
3. **No complete public-service authorization model:** object scoping exists, but the product has not implemented the account lifecycle, revocation, tenant administration, policy engine, or security operations expected of public multi-user software.
4. **Bearer-cookie exposure:** anyone who obtains a valid session cookie can act within that namespace until the cookie expires or the signing context changes.
5. **Local secret storage:** absent an environment secret, the application can create a local signing-secret file. Production secret custody, rotation, and backup are not implemented.
6. **In-memory burst limits:** short-window rate limits reset on restart and are not shared across workers or hosts.
7. **No complete erasure workflow:** profile memory has an explicit delete route, but there is no single account/vault erasure operation covering every analysis, message, goal, prediction, and usage record.
8. **No storage-level retention proof:** deleting an active record does not erase copied databases, backups, filesystem snapshots, or provider-side records.
9. **Provider dependence:** live operation is subject to provider terms, attribution duties, rate limits, outages, geographic limits, pricing, and data accuracy. These can change without a code change.
10. **No end-to-end confidentiality guarantee:** HTTPS termination, reverse proxies, host security, logs, browser extensions, provider handling, and operator practices are outside this local application boundary.
11. **No outcome guarantee:** source evidence and AI output can be wrong, incomplete, stale, or unsuitable. AIONEX does not guarantee profit, accuracy, compliance, funding, procurement success, safety, or any other result.

## Offline and demo guarantees within scope

`OMNI_OFFLINE_MODE=1` causes market-intelligence gathering to return a deterministic degraded envelope before creating its HTTP client and keeps application prediction networking disabled. Demo mode also disables source calls by default unless `OMNI_DEMO_ALLOW_NETWORK=1` is explicitly set. `OMNI_OFFLINE` remains only a legacy application fallback; new configurations should use `OMNI_OFFLINE_MODE`. The checked-in CI uses the canonical switch, demo flags, disabled prediction flags, and a temporary database.

This guarantee applies to the documented application code path under those settings. It cannot prevent unrelated host software, package installation, browser extensions, developer tools, or newly added code from using the network. Any new adapter or background task must receive an offline-mode test.

## Live-provider obligations

Before enabling a live provider, the operator must:

- review current acceptable-use, privacy, retention, training, licensing, and attribution terms;
- determine whether the intended data and jurisdiction are permitted;
- configure a dedicated least-privilege credential and cost controls;
- avoid regulated, personal, confidential, or client data unless a documented legal and security basis exists;
- preserve provider/source URL, observation date, cache, freshness, authority, and limitation metadata;
- separately label live integration checks and never run them in default CI;
- maintain a shutdown and incident-response path.

## Deployment gate

Do not expose this pre-release directly to the public internet. A deployment review must resolve at least:

- authenticated accounts, authorization tests, cookie rotation/revocation, CSRF, and recovery;
- TLS and trusted-proxy configuration, host validation, secure cookies, and secret management;
- database encryption or a managed data store, backups, retention, deletion, and migration;
- centralized rate limiting, audit logs with redaction, monitoring, alerting, and incident response;
- privacy notice, provider agreements, attribution, jurisdiction, accessibility, and legal review;
- threat modeling and independent security testing for the intended environment.

## Vulnerability handling

Because this is a private pre-release, suspected vulnerabilities should be reported through the repository's private security channel or directly to the authorized repository maintainers. Do not place credentials, exploit details, session cookies, personal data, or client content in an ordinary issue. A public reporting address should not be invented before one is formally established.

Related documents: [Architecture](ARCHITECTURE.md), [Technical Deep Dive](TECHNICAL_DEEP_DIVE.md), [User Flows](USER_FLOWS.md), and [Decision Log](DECISIONS/README.md).
