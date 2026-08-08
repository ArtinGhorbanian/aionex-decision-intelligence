# AIONEX Private Pre-release Demo Script

> Status: Private pre-release demonstration guidance. **AIONEX** is product presentation branding only. This script demonstrates local product behavior with synthetic output; it does not demonstrate live market accuracy, public availability, provider uptime, or guaranteed results.

## Demo objective

In approximately eight minutes, show that a reviewer can:

- complete an English B2C or B2B intake;
- receive a deterministic structured demonstration analysis;
- distinguish unavailable external evidence from live evidence;
- inspect risks, assumptions, action steps, and allowlisted resources;
- ask a follow-up and open a deep dive;
- explicitly confirm or reject memory;
- create a goal and reopen the saved analysis;
- see that no live AI or public-intelligence provider is required.

Use synthetic business details only. Do not enter personal data, credentials, private client plans, regulated information, or unpublished provider content.

## 1. Prepare the Windows environment

From the repository root in PowerShell, use Python 3.14 and the checked-in hash lock:

```powershell
python --version
python -m pip install --disable-pip-version-check --require-hashes -r requirements-dev.lock
```

Set a temporary database and all relevant network-off switches:

```powershell
$env:OMNI_DB_PATH = Join-Path $env:TEMP "aionex-private-demo.sqlite3"
$env:OMNI_SESSION_SECRET = "private-demo-only-session-secret-rotate-before-deployment"
$env:OMNI_DEMO_MODE = "1"
$env:OMNI_AI_DEMO_MODE = "1"
$env:OMNI_OFFLINE_MODE = "1"
$env:OMNI_DEMO_ALLOW_NETWORK = "0"
$env:OMNI_PREDICTION_NETWORK_ENABLED = "0"
$env:OMNI_PREDICTION_SWEEPER_ENABLED = "0"
$env:OMNI_DISABLE_DOCS = "1"
$env:OMNI_RELOAD = "0"
```

`OMNI_OFFLINE_MODE` is the canonical offline switch for intelligence and application prediction networking. Demo mode makes AI generation synthetic and keeps intelligence offline by default; setting the canonical switch and leaving both prediction flags at zero makes the demonstration intent auditable. `OMNI_OFFLINE` is only a legacy application fallback and is not needed here.

## 2. Verify before presenting

Run the same quality gates used by CI:

```powershell
python -m ruff check .
python -m pytest -q
```

For a focused proof that demo/offline intelligence does not fetch:

```powershell
python -m pytest tests/test_intelligence.py -k "offline or demo" -q
```

Record the exact revision and test result for the session. Do not reuse a result from another revision.

## 3. Start the local server

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

In another PowerShell window, check local readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Open `http://127.0.0.1:8000` in a current browser. Keep the service bound to loopback for this private demonstration.

## 4. Opening statement

Use wording like this:

> “This is a private pre-release of AIONEX, used here as the product presentation name. The current session is a fully offline demonstration. Its strategy content is deterministic synthetic data, and external source cards are intentionally unavailable. We are evaluating workflow, transparency, and control—not claiming current market accuracy or a guaranteed outcome.”

Do not say “live,” “production,” “proven,” “secure,” “compliant,” “accurate,” or “customer-ready” without separate current evidence.

## 5. Demonstrate intake and analysis

Use a synthetic prompt such as:

> “Design a low-cost B2B validation plan for a fictional inventory-reporting service. The team has two people, four weeks, and a synthetic budget of $1,500.”

Show:

1. the B2B selection and horizon;
2. bounded clarification questions;
3. the submit and loading states;
4. the evidence/service-status area, emphasizing that sources are degraded or unavailable because the session is offline;
5. the analysis structure: summary, confidence, data gaps, risks, scenarios, actions, checkpoints, and resources;
6. the absence of a live-provider claim.

Explain that confidence is constrained by independent usable evidence. A polished synthetic answer is not evidence of real-world accuracy.

## 6. Demonstrate follow-up and deep dive

Ask a bounded synthetic follow-up:

> “Which assumption should the fictional team test first, and what result would stop the plan?”

Then open one action-step deep dive. Point out:

- the selected step remains the focus;
- substeps and decision checkpoints are structured;
- high-impact failure modes are visible;
- resource URLs come from a deterministic allowlist rather than model invention;
- the answer is still demonstration data.

## 7. Demonstrate memory consent

If the flow proposes a memory candidate:

1. explain that it is only a proposal;
2. confirm one clearly synthetic, non-sensitive fact;
3. open the profile to show the stored fact;
4. use the forget action to show user control.

State that deletion affects the active local database record, not prior copies, backups, provider records, or filesystem snapshots.

## 8. Demonstrate goals and vault

Create a goal from the analysis or create one manually. Update one milestone, then open the vault and return to the saved analysis.

Explain that:

- goal progress is user-managed planning state, not verified business performance;
- vault isolation uses a signed anonymous browser-session cookie, not an authenticated account;
- SQLite stores content in plaintext on the local filesystem.

## 9. Close with explicit limits

Use wording like this:

> “The demo verifies the local workflow and its offline controls. It does not verify live providers, current source accuracy, identity security for public hosting, encryption at rest, or a business result. Before any client or public deployment, AIONEX requires the security, privacy, provider-terms, storage, authentication, and operational gates listed in the security model.”

## Optional controlled live evaluation

A live evaluation is a different test and must not be blended into this demo. Before attempting it:

1. read the [Security Model](SECURITY_MODEL.md);
2. approve the exact data that may leave the host;
3. review current AI and public-provider terms, attribution, pricing, jurisdiction, and retention;
4. use a dedicated least-privilege credential and non-sensitive synthetic input;
5. disable demo/offline flags intentionally and only for the reviewed paths;
6. monitor requests and costs;
7. label the session “controlled live integration test,” not “production.”

Never place a real provider key in a command transcript, screenshot, issue, recording, or repository file.

Related documents: [User Flows](USER_FLOWS.md), [Security Model](SECURITY_MODEL.md), and [Case Study](CASE_STUDY.md).
