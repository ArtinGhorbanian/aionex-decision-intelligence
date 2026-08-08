# AIONEX Support

> **Private pre-release.** AIONEX has no public support service, service-level agreement, production operations team, paid support plan, or guaranteed response time. Support is limited to authorized collaborators evaluating the repository in a controlled environment.

## Start here

| Need | First reference |
| --- | --- |
| Local offline evaluation | [README.md](README.md) |
| Architecture or runtime boundaries | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Security limitations or deployment gate | [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) |
| Sensitive vulnerability | [SECURITY.md](SECURITY.md) |
| Contribution workflow | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Rights, licensing, or release question | [RIGHTS_CLEARANCE.md](RIGHTS_CLEARANCE.md) and [LICENSE](LICENSE) |
| Provider attribution or dependency question | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |
| Planned work | [ROADMAP.md](ROADMAP.md) |

## Requesting help

When an access-controlled repository remote exists, use an ordinary private issue only for non-sensitive setup, documentation, test, or product-behavior questions.

Use a private GitHub security advisory for any issue involving:

- a suspected exploitable weakness;
- credentials, tokens, cookies, or signing secrets;
- personal, client, or regulated data;
- unredacted logs or database content;
- provider-account details;
- bypass of identity, object scoping, rate, budget, or network controls.

If no remote exists, use only an already-established private channel to an authorized maintainer. No external email address, domain, chat room, or form is designated by this repository.

## Safe diagnostic information

For a non-sensitive report, include:

- the exact command that failed;
- the local operating environment and Python version;
- whether demo and offline switches were enabled;
- the affected route, module, or user-visible action;
- a minimal reproduction using synthetic data;
- the shortest relevant error excerpt with paths and identifiers redacted;
- the tests or checks already run;
- whether an outbound network or provider call was expected.

Do not attach:

- <code>.env</code> files or environment dumps;
- API keys, session secrets, cookies, authorization headers, or proxy credentials;
- local SQLite databases or write-ahead-log files;
- real user questions, analyses, messages, memory, or goals;
- full logs that may contain request content or local paths;
- screenshots containing personal data, secrets, or provider-account information.

## Common checks

### Offline demo does not start

1. Confirm the virtual environment is active.
2. Install [requirements.lock](requirements.lock) with <code>--require-hashes</code>.
3. Set <code>OMNI_DEMO_MODE=1</code>, <code>OMNI_AI_DEMO_MODE=1</code>, and <code>OMNI_OFFLINE_MODE=1</code>.
4. Keep <code>OMNI_PREDICTION_NETWORK_ENABLED=0</code> and <code>OMNI_PREDICTION_SWEEPER_ENABLED=0</code>.
5. Set a random <code>OMNI_SESSION_SECRET</code> of at least 32 characters.
6. Use an isolated, writable <code>OMNI_DB_PATH</code>.
7. Keep the host on <code>127.0.0.1</code>.

### The health indicator is degraded

The health endpoint reports AI and storage readiness separately. In demo mode, check the database path and local filesystem permissions. In live mode, a missing provider key can also make AI readiness unavailable. Do not add a live key merely to clear a status indicator unless live-provider use has been authorized and reviewed.

### Source information is stale, partial, or unavailable

That state can be expected when offline policy is active, an adapter fails, a cached record has aged, or a provider is unavailable. Preserve the displayed freshness and limitation labels. Do not relabel degraded evidence as live.

### Tests fail

Run the focused failing test first, then:

~~~powershell
python -m pytest -q
python -m ruff check .
~~~

Default tests should not need a live provider credential. A failing check is not permission to weaken offline, security, validation, attribution, or cost controls.

## What support does not provide

Project support does not provide:

- financial, legal, compliance, medical, safety, or investment advice;
- provider-account, billing, or contractual support;
- production deployment approval;
- rights or licensing clearance;
- recovery of lost anonymous browser namespaces;
- database confidentiality or backup guarantees;
- guarantees about decision quality, accuracy, profit, or outcomes.

The project must remain private until the documented rights and provider gates are resolved.
