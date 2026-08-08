# Changelog

This changelog records repository work that has not been publicly released. It does not imply distribution rights, production readiness, backward-compatibility support, or a release schedule.

## Unreleased

### Product

- Present the user-facing workspace under the **AIONEX** product label.
- Provide an English browser interface for deterministic intake, structured analysis, follow-up work, saved context, goals, and prediction review.
- Distinguish source freshness, stale cache, partial coverage, degraded service, and unavailable providers in user-visible states.
- Display AI and storage readiness from the application health endpoint instead of a static readiness claim.
- Clarify which actions can invoke an AI provider and which workflows remain deterministic.

### Offline and provider controls

- Keep demonstration analysis deterministic.
- Make public-intelligence networking unavailable by default during demo mode unless separately opted in.
- Add a canonical explicit offline switch for public intelligence and prediction networking.
- Keep prediction network resolution and its background sweeper as separate opt-ins.
- Preserve provider, source URL, observation date, cache, freshness, authority, and limitation metadata when available.

### Security and privacy

- Document plaintext SQLite, anonymous bearer-cookie namespaces, local secret custody, and the absence of production account controls.
- Keep browser rendering on safe DOM construction rather than direct HTML insertion.
- Keep API documentation disabled by default and local evaluation bound to loopback in the documented setup.
- Add private vulnerability-reporting guidance without inventing a public contact.
- Reject Arabic-script text in live provider-generated human-readable output while preserving multilingual user input and opaque identifiers.
- Isolate automated tests from private legacy-vault files and avoid recording a one-time claim when no legacy rows exist.

### Governance and documentation

- Replace the repository README with an English product and evaluation guide.
- Add security, contribution, conduct, support, roadmap, and changelog documents.
- Add an original code-native AIONEX social-preview SVG without third-party marks.
- Add verified desktop and mobile screenshots captured from the reviewed offline demo build.
- Preserve the private pre-release gate pending rights, asset-provenance, competition-history, license, and provider review.

### Release status

- No public or commercial release has been cleared or published.
- The temporary no-license position remains in effect.
- No hosted service, public support channel, security response commitment, or public CI status endpoint is represented.

## Changelog policy

Future entries should remain under **Unreleased** until an authorized release decision is documented. Do not add release dates, version claims, customer claims, performance metrics, or compatibility promises without verifiable evidence and approval.

Related documents: [README](README.md), [Rights Clearance](RIGHTS_CLEARANCE.md), [Roadmap](ROADMAP.md), and [Security Policy](SECURITY.md).
