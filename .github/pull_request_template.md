## Summary

Describe the user or engineering problem and the bounded change made to address it.

## Verification

List exact commands, test results, and any manual checks. Use synthetic or redacted data.

## Risk and rollback

Describe security, privacy, provider, storage, compatibility, and migration effects. Explain how to revert the change safely.

## Pre-release checklist

- [ ] The change is appropriate for the private AIONEX pre-release and makes no public-availability claim.
- [ ] Product-facing content is English and treats AIONEX as presentation branding only.
- [ ] No secret, cookie, personal data, private strategy, local database, or provider response is included.
- [ ] Demo and CI paths remain offline unless a documented, explicit opt-in is under test.
- [ ] Live-provider behavior preserves source attribution, freshness, limitations, and applicable terms.
- [ ] Ruff and the relevant offline tests pass on the declared Python version.
- [ ] New behavior has tests or a concise explanation of why automated coverage is not practical.
- [ ] Documentation and decision records are updated when architecture or operator obligations change.
- [ ] No text promises profit, accuracy, legal compliance, or another guaranteed outcome.

## Screenshots or recordings

Attach only when they add review value. Redact all user-authored and provider-derived sensitive content.
