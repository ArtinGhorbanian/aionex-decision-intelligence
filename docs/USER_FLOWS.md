# AIONEX User Flows

> Status: Private pre-release product and engineering documentation. **AIONEX** is product presentation branding only. The flows below describe the current local build and do not claim public availability or guaranteed outcomes.

## Shared principles

- The product interface and generated product content are English and left-to-right.
- User-authored text may contain other languages, but it is handled as data and does not change the output-language policy.
- The current identity is an anonymous signed browser session, not an account login.
- Profile memory is opt-in. Facts used in one request are not automatically durable memory.
- Demo results are deterministic synthetic examples and must not be described as live analysis.
- Live evidence is labeled with provider, source, date, cache, freshness, authority, and limitations when available.
- Every strategy is decision support. No flow guarantees profit, accuracy, legal compliance, financing, procurement success, or operational safety.

## Flow 1: first local visit

1. The user opens the local AIONEX URL.
2. The server creates a random anonymous client identifier and returns an HMAC-signed HTTP-only cookie.
3. The browser receives the English interface and same-origin security policy.
4. No database client row is required until a stateful operation needs it.

**User-visible expectation:** the workspace is isolated to this browser session on this installation.

**Important caveat:** there is no verified account, password, recovery address, role, or cross-device sync. Possession of the cookie grants access to its local namespace. Clearing or losing it can make prior records inaccessible.

## Flow 2: bounded intake

1. The user chooses B2C or B2B, a time horizon, and enters a decision question.
2. The API validates field types, bounds, and unknown fields.
3. Deterministic intake logic extracts immediately useful facts and selects clarification questions.
4. The application may use already confirmed profile memory to avoid asking for a known fact.
5. The server stores the intake session within the anonymous namespace.

**Privacy boundary:** intake is local until an analysis operation is requested. In live AI mode, bounded query and clarification context can then be sent to the configured AI provider.

## Flow 3: analysis in offline demo mode

1. The operator starts the application with demo and offline switches.
2. The user answers the clarification questions and submits the analysis.
3. The intelligence router returns deterministic degraded source records without constructing an HTTP client.
4. The AI gateway generates a deterministic schema-valid demonstration result without calling an AI provider.
5. The execution-kit layer attaches allowlisted resources locally.
6. The result is saved to the temporary or configured SQLite database.

**Expected labels:** synthetic demonstration output, unavailable external evidence, zero live-provider use, and constrained confidence.

**What this flow proves:** application navigation, validation, persistence, result rendering, follow-up surfaces, and failure-safe states.

**What it does not prove:** current market accuracy, provider availability, provider integration, a successful deployment, or an achievable commercial result.

## Flow 4: controlled live analysis

1. The operator disables demo mode, configures the AI credential, reviews provider terms, and intentionally enables the required outbound paths.
2. The source router infers local tags and chooses only registered fixed providers relevant to the request.
3. Source adapters retrieve bounded observations. They do not receive raw user text as arbitrary query content.
4. The server compacts usable evidence with attribution and quality metadata.
5. The configured AI provider receives the bounded query, relevant answers, confirmed memory, and compact evidence needed for structured generation.
6. The response is schema-validated, confidence-capped, enriched with deterministic resources, usage-recorded, and saved.

**External disclosure:** public data providers receive fixed data requests. The AI provider receives user and workspace context included in the generation payload. Provider handling remains governed by the operator's agreement and settings even though the request asks for `store=False`.

**Operator obligation:** confirm acceptable-use rules, data rights, required attribution, cost, privacy terms, jurisdiction, retention, and incident procedures before using real or client information.

## Flow 5: history and vault

1. The user opens the vault.
2. The server returns bounded summaries belonging to the current anonymous namespace.
3. The user opens one analysis to reconstruct the detailed view and deterministic execution kit.
4. Stored messages, intelligence summaries, goals, and predictions remain separate records linked to the analysis.

**Caveat:** SQLite content is plaintext. The vault is not an encrypted personal safe, and the anonymous cookie is not account authentication.

## Flow 6: follow-up chat

1. The user asks a question about a saved analysis.
2. The API loads the owned strategy, recent bounded history, confirmed memory, related goal, and relevant intelligence.
3. Demo mode returns deterministic synthetic follow-up content; live mode sends the bounded payload to the configured AI provider.
4. The structured answer states how it affects the strategy and may propose memory candidates.
5. The message is stored only after successful generation.

**Memory rule:** proposed memory candidates are not durable until the user explicitly confirms one through the memory action.

## Flow 7: deep dive

1. The user selects a specific action step.
2. The server verifies that the analysis and step belong to the current namespace.
3. A bounded strategy summary, the selected step, current question, and evidence are passed to the demo generator or live AI provider.
4. The result decomposes execution into substeps, checkpoints, risks, and allowlisted resources.
5. A cache can reuse an identical completed deep dive.

**Caveat:** detailed instructions remain decision support. The user must validate laws, licenses, counterparties, prices, and operational conditions independently.

## Flow 8: explicit memory control

1. The user reviews a proposed fact.
2. The user explicitly confirms storage for the selected B2C or B2B profile.
3. The API stores the bounded fact in the profile memory record.
4. Later intake and analysis operations may include that confirmed fact.
5. The user can invoke the forget-profile action to clear the current profile memory.

**Deletion boundary:** application deletion removes the active database record. It cannot promise deletion from prior filesystem backups, copied databases, provider records, logs outside this project, or storage snapshots.

## Flow 9: goals and progress

1. The user creates a manual goal or derives one from an owned analysis.
2. Deterministic code validates milestones, dates, status, and progress updates.
3. The goal is stored within the anonymous namespace.
4. The user can update progress or archive the goal.

Goals are planning aids. Progress percentages represent user-managed state, not verified business performance.

## Flow 10: predictions and calibration

1. A completed analysis may contain falsifiable predictions for supported metrics.
2. The server records the baseline, direction, threshold, and resolution window.
3. If prediction networking is explicitly enabled, a resolver can retrieve current supported metrics after a prediction is due.
4. Deterministic comparison marks a supported prediction outcome.
5. The calibration view aggregates available outcomes.

**Interpretation rule:** calibration is a local diagnostic with sample-size and selection limitations. It is not an audited performance history, investment return, or promise of future accuracy.

## Flow 11: degraded and recovery states

| Condition | User-facing behavior | Safe next action |
| --- | --- | --- |
| Offline or default demo intelligence | Sources are shown as unavailable/degraded, not live | Continue with demonstration data or intentionally configure a reviewed live mode |
| One public provider fails | Other providers can continue; eligible stale data is labeled | Check freshness and verify the observation directly at the attributed source |
| AI credential is absent | Live generation is unavailable | Use demo mode or configure a valid credential privately |
| AI request times out or is rate limited | A bounded typed error is returned | Wait, review usage, and retry intentionally |
| Storage is unavailable | Health readiness reports failure | Stop stateful use and repair the local database path or permissions |
| Session cookie is lost | Existing namespace may no longer be reachable | Use an approved migration mechanism only when configured; do not bypass ownership checks |

## Recommended evaluation order

1. Run the [offline demo script](DEMO_SCRIPT.md) with synthetic content.
2. Review the [security model](SECURITY_MODEL.md).
3. Confirm local retention and deletion behavior.
4. Review every intended provider's current terms and attribution requirements.
5. Only then perform a separately labeled live integration test with non-sensitive data.

Related documents: [Architecture](ARCHITECTURE.md), [Technical Deep Dive](TECHNICAL_DEEP_DIVE.md), and [Client Adaptation Ideas](CLIENT_ADAPTATION_IDEAS.md).
