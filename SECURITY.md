# Security Policy

> **Private pre-release.** AIONEX is not cleared for public deployment or distribution. This policy describes how authorized collaborators should handle suspected vulnerabilities during controlled repository work. It is not a security certification, warranty, bug-bounty program, or response-time commitment.

## Supported scope

Only the current private pre-release branch under active review is in scope. There are no supported public releases, hosted production instances, or maintained historical versions.

Relevant components include:

- the FastAPI application and request policy;
- the English browser interface;
- anonymous cookie namespace handling;
- local SQLite persistence;
- the AI gateway and usage controls;
- public-intelligence adapters and prediction networking;
- deterministic resources and outbound-link validation;
- dependency and CI configuration.

Operator infrastructure, third-party provider systems, browser extensions, package registries, and unmodified dependencies are outside this repository's direct control. Reports about those systems may still help identify an integration risk.

## Reporting a sensitive issue

Do not place exploit details, credentials, tokens, session cookies, personal data, client content, database records, or unredacted logs in an ordinary issue.

When an access-controlled GitHub remote exists:

1. Open the repository's **Security** area.
2. Use **Advisories** to create a private draft security advisory.
3. Include only the minimum redacted evidence needed to reproduce and assess the issue.

If no remote or advisory channel exists, use only an already-established private channel to an authorized repository maintainer. This repository intentionally publishes no email address, domain, or alternate contact until one is formally established.

Use ordinary repository issues only for clearly non-sensitive security improvements, such as documentation corrections, defense-in-depth suggestions, or dependency-maintenance tasks that do not disclose an exploitable weakness.

## What to include

A useful private report contains:

- the affected file, route, component, or configuration;
- the preconditions and tested local mode;
- concise reproduction steps using synthetic data;
- expected and observed behavior;
- the likely impact and trust boundary crossed;
- whether any outbound provider or network call occurred;
- a minimal proof of concept with secrets removed;
- suggested containment or remediation, if known.

Do not test against systems or data you are not authorized to access. Do not retain or redistribute data encountered during validation.

## Handling process

Authorized maintainers should:

1. acknowledge the report through the same private channel when practical;
2. preserve confidentiality and restrict access to those needed for review;
3. reproduce with synthetic data in demo/offline mode where possible;
4. assess impact across identity, storage, provider, cost, and source boundaries;
5. prepare a focused fix and regression test;
6. review whether secrets, local data, or provider credentials require rotation;
7. document the resolution in the private advisory and, when appropriate, [CHANGELOG.md](CHANGELOG.md);
8. decide separately whether any disclosure is legally and operationally appropriate.

No response or remediation deadline is promised for this pre-release.

## Current security boundaries

The current application has important limitations:

- SQLite data and locally generated signing-secret files are plaintext;
- the signed anonymous cookie is a bearer credential, not account authentication;
- there is no public multi-tenant authorization, recovery, or revocation system;
- short-window rate limits are process-local;
- public-provider and AI-provider behavior remains subject to external terms and account settings;
- there is no completed independent penetration test or production deployment review.

Do not expose the application directly to the public internet. Review [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for the threat model and deployment gate.

## Related documents

- [README](README.md)
- [Support](SUPPORT.md)
- [Contributing](CONTRIBUTING.md)
- [Rights Clearance](RIGHTS_CLEARANCE.md)
- [Third-Party Notices](THIRD_PARTY_NOTICES.md)
