# Ethical Launch Package

Status: **draft only — do not publish until rights and provider gates pass**

Every claim below is deliberately limited to behavior verified in the private
pre-release. Remove the gate notice only after `RIGHTS_CLEARANCE.md` is complete,
CI is green on the release commit, and a real production-provider smoke test has
been approved.

## Tagline

Turn uncertainty into a testable action plan.

## GitHub announcement

Introducing AIONEX, a decision-intelligence workspace that turns a loosely
defined question into explicit assumptions, risks, evidence, and a reviewable
action plan. The project supports offline demonstrations, English-only product
output, source-freshness labels, manual goals, and opt-in long-term memory.

This is decision support, not a prediction or guarantee. Live data and AI are
operator-controlled, and the repository documents where external terms and
human review still apply.

## LinkedIn draft

We built AIONEX to make difficult decisions easier to inspect—not to pretend
uncertainty has disappeared.

Start with a goal, constraints, budget, and timeline. AIONEX asks focused
questions, exposes assumptions and risks, checks available sources, and returns
a plan you can review and update. The interface is English-only; offline demo
mode avoids external network and model calls; generating a real analysis uses
the configured AI provider only after an explicit action.

The most important engineering work was behind the interface: browser-scoped
storage boundaries, opt-in long-term memory, hash-locked dependencies, linked
source attribution, bounded requests, and a network-off default for demo and
CI. It remains decision support and requires human judgment.

## X / Twitter thread draft

1/ AIONEX turns a fuzzy decision question into assumptions, risks, evidence,
and a testable action plan.

2/ The goal is inspectability. Context coverage is labelled as an estimate,
progress is manual, and data can be fresh, stale, partial, or unavailable.

3/ Offline demo mode makes no external data or AI request. Real AI runs only
after an explicit, labelled action with the operator's configured provider.

4/ The project includes hash-locked dependencies, CI, browser-scoped history,
opt-in long-term memory, and linked source attribution.

5/ AIONEX is decision support—not financial, legal, medical, or operational
advice, and never a guarantee of an outcome.

## Product Hunt draft

- **Name:** AIONEX
- **Tagline:** Turn uncertainty into a testable action plan.
- **Description:** A decision-intelligence workspace for individuals and teams.
AIONEX asks focused context questions, surfaces assumptions and risks, checks
available evidence, and builds a plan you can review. It includes offline demos,
manual goals, opt-in memory, and transparent source freshness. Real analysis
uses the operator's configured AI provider only after an explicit action.

## Reddit draft

I have been working on AIONEX, a local-first decision-support workspace. It is
designed for situations where a polished answer is less useful than a clear
record of assumptions, constraints, evidence, risk, and next actions.

The private pre-release now has an English-only UI, offline demo mode, linked
source attribution, manual goals, browser-scoped history, and opt-in long-term
memory. I would value feedback on the clarity of the decision flow and on which
assumptions should be easiest to challenge. It is not a forecasting guarantee
or professional advice.

## Hacker News draft

**Title:** Show HN: AIONEX — turn uncertain decisions into reviewable action plans

AIONEX is a FastAPI and vanilla-JavaScript decision-support workspace. A local
intake pass identifies missing context without a model call; an explicitly
requested analysis can then use the configured OpenAI provider. Optional public
data sources are routed by a local taxonomy and displayed with provider links,
freshness, as-of time, and limitations. Demo/CI are network-off by default.

I focused this iteration on truthful state and boundaries: no fake readiness,
no “private” claim for plaintext SQLite, opt-in long-term memory, manual rather
than “evidence-proven” goal progress, bounded requests, locked dependencies, and
an English-only LTR interface. Feedback on the architecture and failure states
is welcome.

## Customer segments

- Founders and operators structuring go/no-go or rollout decisions.
- Small teams documenting assumptions, risks, and review gates.
- Independent professionals comparing constrained courses of action.
- Product and strategy consultants preparing transparent decision artifacts.
- Internal innovation teams prototyping a client-specific decision workflow.

## Discovery keywords

decision intelligence, decision support, action plan, risk assumptions,
evidence review, source freshness, local-first AI, offline AI demo, FastAPI,
structured analysis, B2B planning, B2C planning, opt-in memory

## Launch checklist

- [ ] Complete and sign the rights-clearance record.
- [ ] Replace the temporary no-license notice with the approved final license.
- [ ] Verify SVG and favicon provenance.
- [ ] Review every enabled data provider's current commercial terms and plan.
- [x] Run OSV/dependency audit on the exact release lock.
- [x] Pass CI, the full test suite, and lint on the private pre-release commit.
- [x] Pass a clean-clone loopback smoke test on the exact release-candidate commit.
- [ ] Run approved real-provider smoke tests without recording private inputs.
- [x] Capture real desktop and mobile screenshots from a clean demo database.
- [ ] Verify accessibility with keyboard, 200% zoom, reduced motion, and a
  screen reader.
- [x] Review all copy for guarantees, endorsements, or unsupported metrics.
- [ ] Enable private vulnerability reporting and branch protection.
- [ ] Change visibility only after a named authorized reviewer records approval.
