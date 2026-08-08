# Contributing to AIONEX

> **Private pre-release.** Contributions are limited to authorized collaborators working in an access-controlled repository. This document does not invite public submissions, grant a license, or imply that public distribution has been cleared.

## Before contributing

Read:

- [README.md](README.md) for current product boundaries;
- [SECURITY.md](SECURITY.md) before reporting a vulnerability;
- [RIGHTS_CLEARANCE.md](RIGHTS_CLEARANCE.md) and [LICENSE](LICENSE) before adding or redistributing material;
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) before changing dependencies, providers, datasets, or attribution;
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) before changing trust boundaries.

Do not contribute material unless you are authorized to do so and can document the rights needed for the repository's private evaluation use. Acceptance of a change does not establish authorship, transfer ownership, or grant public distribution rights. A separate written contribution or rights agreement may be required before release.

## Contribution principles

- Keep the product label **AIONEX** in user-facing material while preserving compatibility identifiers unless a migration is explicitly approved.
- Write product and governance copy in English.
- Do not add personal names, credentials, private data, invented contacts, domains, testimonials, usage metrics, customers, partnerships, endorsements, certifications, or outcome guarantees.
- Treat user, model, source, and provider content as untrusted data.
- Preserve safe DOM construction and strict request/output validation.
- Keep demo and offline paths deterministic and network-free by default.
- Keep prediction networking and background resolution separately opt-in.
- Preserve source URL, observation date, cache, freshness, authority, and limitation metadata.
- Do not add third-party marks or assets without documented provenance and permission.
- Avoid broad refactors in security- or cost-sensitive work unless the change is separately reviewed.

## Workflow

1. Confirm the task is authorized and does not conflict with the release gate.
2. For non-sensitive work, record the problem in the private repository issue tracker once a remote exists. Use a private security advisory for sensitive issues.
3. Create a focused branch or worktree and keep unrelated changes out of the patch.
4. Add or update tests that fail before the fix and pass afterward when practical.
5. Update affected documentation, privacy boundaries, provider notes, or the unreleased changelog.
6. Review the diff for secrets, personal data, generated databases, unsupported claims, and accidental network enablement.
7. Open a private pull request with the problem, scope, validation, risks, and rollback notes.
8. Obtain review from an authorized collaborator familiar with the affected boundary.

## Local setup

Use the offline demo in [README.md](README.md). It avoids a live AI credential and disables documented public-source and prediction network paths.

Install development dependencies and run:

~~~powershell
python -m pip install --require-hashes -r requirements-dev.lock
python -m pytest -q
python -m ruff check .
~~~

Add narrower checks for the files or behavior changed. Live-provider validation must be explicitly authorized, separately labeled, and excluded from default tests.

## Pull request checklist

- [ ] The change is authorized for this private pre-release.
- [ ] The patch is focused and contains no secrets, personal data, databases, or local artifacts.
- [ ] New copy is English and avoids unsupported claims.
- [ ] Rights and provider implications were reviewed.
- [ ] Offline/demo behavior remains safe by default.
- [ ] Security, privacy, cost, identity, and attribution boundaries are documented.
- [ ] Tests and static checks were run and their exact results are recorded.
- [ ] No third-party asset or mark was added without provenance and permission.
- [ ] Relevant unreleased changelog or roadmap notes were updated when needed.

## Review and acceptance

Maintainers may decline or defer a change because it expands the legal, provider, security, privacy, cost, maintenance, or deployment boundary. Merge approval means only that the change was accepted for the current private repository state; it does not clear a public release.
