# Third-Party Notices

Reviewed: 2026-08-08

This file records install-time software dependencies and optional runtime data
services. It is not a substitute for the complete license text distributed by
each project or for legal review of a particular deployment.

## Python dependency graph

The hash-locked Windows/Python 3.14 development graph contains the following
packages. They are downloaded at installation time and are not vendored here.

| Package | Version | Reported license |
| --- | ---: | --- |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.14.2 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| click | 8.4.2 | BSD-3-Clause |
| colorama | 0.4.6 | BSD-3-Clause |
| distro | 1.9.0 | Apache-2.0 |
| fastapi | 0.141.1 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httptools | 0.8.0 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.18 | BSD-3-Clause |
| iniconfig | 2.3.0 | MIT |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| jiter | 0.16.0 | MIT |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| openai | 2.6.0 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.6.0 | MIT |
| pydantic | 2.13.4 | MIT |
| pydantic-core | 2.46.4 | MIT |
| Pygments | 2.20.0 | BSD-2-Clause |
| pytest | 9.0.3 | MIT |
| pytest-asyncio | 1.4.0 | Apache-2.0 |
| python-dotenv | 1.2.2 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| ruff | 0.12.5 | MIT |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |
| starlette | 1.5.0 | BSD-3-Clause |
| tqdm | 4.70.0 | MIT and MPL-2.0 terms reported by package metadata |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.2 | MIT |
| uvicorn | 0.35.0 | BSD-3-Clause |
| watchfiles | 1.2.0 | MIT |
| websockets | 17.0.1 | BSD-3-Clause |

Versions and artifact hashes are authoritative in `requirements.lock` and
`requirements-dev.lock`. Package names link to their canonical records at
`https://pypi.org/project/<name>/`. Review each installed distribution's
license files when producing a binary or hosted distribution.

## OpenAI service

Real analysis can use the OpenAI API after the user selects an AI-labelled
action and supplies their own API configuration. The OpenAI Python SDK is
covered by its Apache-2.0 license; API processing is governed separately by the
[OpenAI Services Agreement](https://openai.com/policies/services-agreement/) and
[API data controls](https://developers.openai.com/api/docs/guides/your-data).
The operator must review applicable retention, abuse-monitoring, residency, and
account settings. Demo mode makes no OpenAI request.

## Optional live-data services

Demo and offline modes make no live-data request. Network access is an explicit
operator opt-in. When enabled, the router may use the providers below and the UI
must preserve its linked provider attribution, as-of time, freshness, and
limitations.

| Provider | Use | Clearance note |
| --- | --- | --- |
| Frankfurter / ECB reference data | FX context | Confirm Frankfurter terms; preserve underlying ECB acknowledgement. |
| European Central Bank Data API | Official FX baseline | Acknowledge the ECB as source under the [ECB statistics reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html). |
| CoinGecko API | Digital-market proxy | Attribution and redistribution conditions vary by plan. Review the active [API terms and plan](https://www.coingecko.com/en/api/pricing) before commercial use. |
| Hacker News Firebase API | Technology-community attention | Follow the official [API documentation](https://github.com/HackerNews/API), rate expectations, and applicable site terms. |
| World Bank Indicators API | Structural indicators | The [summary terms](https://data.worldbank.org/summary-terms-of-use) generally require attribution and warn that some indicators have separate third-party restrictions. |
| Eurostat dissemination API | Euro-area inflation | Preserve EU/Eurostat source acknowledgement and verify the [reuse notice](https://ec.europa.eu/eurostat/about-us/policies/copyright). |
| U.S. BLS, Treasury, Federal Register, USGS, NWS, CISA, NOAA, NASA and openFDA | U.S. public-sector context | Public access does not imply endorsement. Follow each API policy, rate limit, disclaimer, and any third-party-data exception. |
| TED / Publications Office of the EU | Procurement notices | Preserve EU source attribution and verify the [TED API terms](https://docs.ted.europa.eu/api/latest/index.html) for the deployment. |
| GitHub REST API | Open-source momentum | Follow the [GitHub API terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#api-terms) and rate limits. |
| Stack Exchange API | Skill-demand signal | Visible source attribution is required by the [API terms](https://engineering.stackexchange.com/legal/api-terms-of-use). |
| Nager.Date API | U.S. calendar context | Community-service license and availability require deployment-specific verification. |

Yahoo endpoints and Yahoo-derived runtime labels were removed; the application
does not rely on Yahoo data.

## Assets and marks

No third-party font, logo, image, or JavaScript bundle is shipped. Existing
project SVG provenance remains an open rights item. Provider and package names
are used only for identification; no endorsement or partnership is implied.
