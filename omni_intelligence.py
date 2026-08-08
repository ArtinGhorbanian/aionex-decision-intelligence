"""Free, keyless and cost-bounded external intelligence for AIONEX.

The router in this module never sends user text to a third party.  It selects
fixed, public endpoints locally, fetches only the branches relevant to a request,
and turns their output into a bounded evidence brief before any model call.

Every adapter is optional and failure-isolated.  A source outage lowers coverage
instead of blocking an analysis.  Per-source caches and stale-if-error windows
also keep the service polite to free public APIs.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Literal

import httpx


Tier = Literal["B2C", "B2B"]
Fetcher = Callable[[httpx.AsyncClient], Awaitable[dict[str, Any]]]

OMNI_HTTP_PROXY = os.getenv("OMNI_HTTP_PROXY")
INGEST_TIMEOUT = httpx.Timeout(7.0, connect=4.0)


def _safe_positive_int(
    name: str, default: int, minimum: int = 1, maximum: int = 86_400
) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


INTELLIGENCE_CACHE_SECONDS = _safe_positive_int(
    "OMNI_INTELLIGENCE_CACHE_SECONDS", 300, 30, 3_600
)
MAX_SELECTED_SOURCES = _safe_positive_int(
    "OMNI_MAX_SELECTED_FREE_SOURCES", 8, 5, 10
)
AI_EVIDENCE_MAX_CHARS = _safe_positive_int(
    "OMNI_AI_EVIDENCE_MAX_CHARS", 4_000, 2_000, 4_000
)
SOURCE_FETCH_HARD_TIMEOUT_SECONDS = _safe_positive_int(
    "OMNI_SOURCE_FETCH_HARD_TIMEOUT_SECONDS", 8, 3, 10
)
MAX_RESPONSE_BYTES = _safe_positive_int(
    "OMNI_SOURCE_MAX_RESPONSE_BYTES", 2_000_000, 250_000, 2_000_000
)

APP_UA = "AIONEX-Decision-Intelligence/3.0 (public-data)"
DEMO_NETWORK_OPT_IN_ENV = "OMNI_DEMO_ALLOW_NETWORK"
_TRUE_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def _env_enabled(name: str) -> bool:
    """Read a security-sensitive boolean without accepting ambiguous values."""
    return str(os.getenv(name, "")).strip().casefold() in _TRUE_ENV_VALUES


def _network_disabled_mode() -> tuple[str, str] | None:
    """Return the deterministic no-network mode selected by the operator."""
    if _env_enabled("OMNI_OFFLINE_MODE"):
        return ("offline", "operator_offline_mode")
    demo_enabled = _env_enabled("OMNI_DEMO_MODE") or _env_enabled(
        "OMNI_AI_DEMO_MODE"
    )
    if demo_enabled and not _env_enabled(DEMO_NETWORK_OPT_IN_ENV):
        return ("demo", "demo_network_disabled")
    return None


class SourceResponseTooLarge(httpx.RequestError):
    """Raised before an unexpectedly large public response reaches a parser."""


class _BoundedAsyncClient(httpx.AsyncClient):
    """Async client that caps decoded bodies while preserving the httpx API."""

    async def send(
        self, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        caller_requested_stream = bool(kwargs.get("stream", False))
        kwargs["stream"] = True
        response = await super().send(request, **kwargs)
        if caller_requested_stream:
            return response

        content = bytearray()
        try:
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise SourceResponseTooLarge(
                        f"public response exceeded {MAX_RESPONSE_BYTES} bytes",
                        request=request,
                    )
        finally:
            await response.aclose()
        decoded_headers = [
            (name, value)
            for name, value in response.headers.multi_items()
            if name.casefold()
            not in {"content-encoding", "content-length", "transfer-encoding"}
        ]
        return httpx.Response(
            status_code=response.status_code,
            headers=decoded_headers,
            content=bytes(content),
            extensions=response.extensions,
            history=response.history,
            request=response.request,
        )


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _latest_period(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in entries:
        if isinstance(entry, dict) and entry.get("value") is not None:
            return entry
    return None


async def _ingest_macro(http: httpx.AsyncClient) -> dict[str, Any]:
    """ECB reference FX with a real 30-day EUR/USD change via Frankfurter."""
    latest = await http.get(
        "https://api.frankfurter.app/latest", params={"from": "EUR", "to": "USD"}
    )
    latest.raise_for_status()
    latest_j = latest.json()
    spot = float(latest_j["rates"]["USD"])
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    series = await http.get(
        f"https://api.frankfurter.app/{start.isoformat()}..{end.isoformat()}",
        params={"from": "EUR", "to": "USD"},
    )
    series.raise_for_status()
    rates = series.json().get("rates", {})
    ordered = sorted(rates)
    momentum = None
    if ordered:
        first = _finite_number((rates.get(ordered[0]) or {}).get("USD"))
        if first:
            momentum = round(((spot - first) / first) * 100, 2)
    return {
        "metrics": {
            "eur_usd_spot": round(spot, 4),
            "eur_usd_30d_change_pct": momentum,
        },
        "as_of": latest_j.get("date"),
        "summary": (
            f"EUR/USD {spot:.4f}; 30-day change {momentum:+.2f}%"
            if momentum is not None
            else f"EUR/USD {spot:.4f}"
        ),
    }


async def _ingest_ecb_fx(http: httpx.AsyncClient) -> dict[str, Any]:
    """Direct ECB observation used as an authority cross-check for the FX layer."""
    response = await http.get(
        "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A",
        params={"lastNObservations": 2, "format": "jsondata"},
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    data_sets = payload.get("dataSets") or []
    series_map = (data_sets[0].get("series") if data_sets else None) or {}
    time_values: list[dict[str, Any]] = []
    for dimension in (
        ((payload.get("structure") or {}).get("dimensions") or {}).get(
            "observation"
        )
        or []
    ):
        if dimension.get("id") == "TIME_PERIOD":
            time_values = dimension.get("values") or []
            break
    observations: list[tuple[str, float]] = []
    for series in series_map.values():
        for raw_index, item in (series.get("observations") or {}).items():
            value = _finite_number(item[0] if isinstance(item, list) and item else item)
            if value is not None:
                try:
                    time_index = int(str(raw_index).split(":")[-1])
                    period = str(time_values[time_index].get("id") or raw_index)
                except (IndexError, TypeError, ValueError):
                    period = str(raw_index)
                observations.append((period, value))
    if not observations:
        raise ValueError("ECB response contained no numeric observation")
    observations.sort(key=lambda item: item[0])
    latest_period, latest = observations[-1]
    change = None
    if len(observations) > 1 and observations[-2][1]:
        previous = observations[-2][1]
        change = round(((latest - previous) / previous) * 100, 4)
    return {
        "metrics": {"eur_usd_reference": round(latest, 5), "period_change_pct": change},
        "as_of": latest_period,
        "summary": f"Official ECB EUR/USD reference {latest:.5f} on {latest_period}",
    }


async def _ingest_markets(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": "bitcoin,ethereum,pax-gold",
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        },
    )
    response.raise_for_status()
    payload = response.json()

    def pack(identifier: str) -> dict[str, Any]:
        item = payload.get(identifier) or {}
        change = _finite_number(item.get("usd_24h_change"))
        return {
            "usd": _finite_number(item.get("usd")),
            "change_24h_pct": round(change, 2) if change is not None else None,
        }

    btc, eth, gold = pack("bitcoin"), pack("ethereum"), pack("pax-gold")
    updated_timestamps = [
        _finite_number((payload.get(identifier) or {}).get("last_updated_at"))
        for identifier in ("bitcoin", "ethereum", "pax-gold")
    ]
    updated_at = max((item for item in updated_timestamps if item), default=None)
    return {
        "metrics": {"btc": btc, "eth": eth, "gold_proxy_paxg": gold},
        "as_of": (
            datetime.fromtimestamp(updated_at, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            if updated_at
            else None
        ),
        "summary": (
            f"BTC {btc['change_24h_pct']}%; ETH {eth['change_24h_pct']}%; "
            f"PAXG {gold['change_24h_pct']}% over 24h"
        ),
    }


async def _disabled_market_quote(
    http: httpx.AsyncClient, symbol: str, label: str
) -> dict[str, Any] | None:
    del http, symbol, label
    raise RuntimeError("unofficial automated market endpoint is disabled")


async def _disabled_market_basket(
    http: httpx.AsyncClient, symbols: list[tuple[str, str]]
) -> dict[str, Any]:
    quotes = await asyncio.gather(
        *[_disabled_market_quote(http, symbol, label) for symbol, label in symbols]
    )
    available = [item for item in quotes if item]
    if not available:
        raise RuntimeError("all public market-chart symbols failed")
    metrics = {
        item["symbol"]: {
            "label": item["label"],
            "price": item["price"],
            "change_30d_pct": item["change_30d_pct"],
        }
        for item in available
    }
    summary = " | ".join(
        f"{item['label']} {item['price']}"
        + (
            f" ({item['change_30d_pct']:+.2f}% 30d)"
            if item["change_30d_pct"] is not None
            else ""
        )
        for item in available
    )
    observed = sorted(
        str(item["as_of"]) for item in available if item.get("as_of")
    )
    return {
        "metrics": metrics,
        "as_of": observed[-1] if observed else None,
        "summary": summary,
    }


async def _ingest_rates_risk(http: httpx.AsyncClient) -> dict[str, Any]:
    return await _disabled_market_basket(
        http,
        [("^TNX", "US 10Y"), ("^VIX", "VIX"), ("DX-Y.NYB", "Dollar index")],
    )


async def _ingest_supply_chain(http: httpx.AsyncClient) -> dict[str, Any]:
    return await _disabled_market_basket(
        http,
        [("BZ=F", "Brent"), ("HG=F", "Copper"), ("GC=F", "Gold")],
    )


async def _ingest_attention(http: httpx.AsyncClient) -> dict[str, Any]:
    ids_response = await http.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json"
    )
    ids_response.raise_for_status()
    ids = [item for item in ids_response.json()[:8] if isinstance(item, int)]
    responses = await asyncio.gather(
        *[
            http.get(f"https://hacker-news.firebaseio.com/v0/item/{item}.json")
            for item in ids
        ],
        return_exceptions=True,
    )
    stories = []
    for response in responses:
        if isinstance(response, Exception):
            continue
        try:
            response.raise_for_status()
            item = response.json() or {}
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if item.get("title"):
            stories.append(
                {
                    "title": str(item["title"])[:180],
                    "score": item.get("score"),
                    "published_at": item.get("time"),
                }
            )
    if not stories:
        raise ValueError("Hacker News returned no readable top story")
    stories.sort(key=lambda item: item.get("score") or 0, reverse=True)
    top = stories[:5]
    published_times = [
        value
        for value in (
            _finite_number(item.get("published_at")) for item in stories
        )
        if value is not None
    ]
    newest = max(published_times, default=None)
    return {
        "metrics": {"top_story_count": len(stories), "top_headlines": top},
        "as_of": (
            datetime.fromtimestamp(newest, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            if newest
            else None
        ),
        "summary": "; ".join(item["title"] for item in top[:3]) or "No top stories",
    }


async def _ingest_world_bank(http: httpx.AsyncClient) -> dict[str, Any]:
    indicators = {
        "global_gdp_growth_pct": "NY.GDP.MKTP.KD.ZG",
        "global_inflation_pct": "FP.CPI.TOTL.ZG",
        "global_unemployment_pct": "SL.UEM.TOTL.ZS",
    }

    async def one(name: str, code: str) -> tuple[str, dict[str, Any] | None]:
        response = await http.get(
            f"https://api.worldbank.org/v2/country/WLD/indicator/{code}",
            params={"format": "json", "per_page": 8},
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        latest = _latest_period(rows if isinstance(rows, list) else [])
        if not latest:
            return name, None
        return name, {"value": round(float(latest["value"]), 2), "year": latest.get("date")}

    outcomes = await asyncio.gather(
        *(one(name, code) for name, code in indicators.items()),
        return_exceptions=True,
    )
    values: dict[str, dict[str, Any] | None] = {}
    for outcome in outcomes:
        if isinstance(outcome, Exception):
            continue
        name, value = outcome
        values[name] = value
    available = {key: value for key, value in values.items() if value is not None}
    if not available:
        raise ValueError("World Bank returned no recent global indicator")
    summary = "; ".join(
        f"{key.replace('_', ' ')} {value['value']} ({value['year']})"
        for key, value in available.items()
    )
    years = [str(value.get("year") or "") for value in available.values()]
    return {
        "metrics": available,
        "as_of": max((year for year in years if year), default=None),
        "summary": summary,
    }


async def _ingest_us_labor(http: httpx.AsyncClient) -> dict[str, Any]:
    year = datetime.now(timezone.utc).year
    response = await http.post(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        json={
            "seriesid": ["CUUR0000SA0", "LNS14000000"],
            "startyear": str(max(2000, year - 2)),
            "endyear": str(year),
        },
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError("BLS public API did not complete")
    output: dict[str, Any] = {}
    latest_periods: list[str] = []
    for series in ((payload.get("Results") or {}).get("series") or []):
        series_id = str(series.get("seriesID") or "")
        monthly = [
            item
            for item in (series.get("data") or [])
            if re.fullmatch(r"M(?:0[1-9]|1[0-2])", str(item.get("period") or ""))
            and _finite_number(item.get("value")) is not None
        ]
        latest = _latest_period(monthly)
        if not latest:
            continue
        period_code = str(latest.get("period") or "")
        month_number = period_code.removeprefix("M")
        period = f"{latest.get('year')}-{month_number}"
        latest_periods.append(period)
        if series_id == "CUUR0000SA0":
            latest_value = _finite_number(latest.get("value"))
            latest_year = str(latest.get("year") or "")
            prior = next(
                (
                    item
                    for item in monthly
                    if latest_year.isdigit()
                    and str(item.get("year")) == str(int(latest_year) - 1)
                    and item.get("period") == period_code
                ),
                None,
            )
            prior_value = _finite_number((prior or {}).get("value"))
            yoy = None
            if latest_value is not None and prior_value:
                yoy = round(((latest_value - prior_value) / prior_value) * 100, 2)
            output["us_cpi_u_all_items_not_seasonally_adjusted"] = {
                "index": latest_value,
                "year_over_year_pct": yoy,
                "period": period,
            }
        elif series_id == "LNS14000000":
            output["us_unemployment_rate_seasonally_adjusted_pct"] = {
                "value": _finite_number(latest.get("value")),
                "period": period,
            }
    if not output:
        raise ValueError("BLS returned no recent series value")
    summary_parts: list[str] = []
    cpi = output.get("us_cpi_u_all_items_not_seasonally_adjusted")
    if cpi:
        cpi_signal = (
            f"YoY {cpi['year_over_year_pct']}%"
            if cpi.get("year_over_year_pct") is not None
            else f"index {cpi.get('index')}"
        )
        summary_parts.append(f"US CPI-U all items {cpi_signal} ({cpi['period']})")
    unemployment = output.get("us_unemployment_rate_seasonally_adjusted_pct")
    if unemployment:
        summary_parts.append(
            "US seasonally adjusted unemployment "
            f"{unemployment.get('value')}% ({unemployment['period']})"
        )
    return {
        "metrics": output,
        "as_of": max(latest_periods, default=None),
        "summary": "Official BLS snapshot: " + "; ".join(summary_parts),
    }


async def _ingest_eurostat(http: httpx.AsyncClient) -> dict[str, Any]:
    """Euro-area HICP annual rate from the official Eurostat JSON-stat API."""
    start = (datetime.now(timezone.utc).date() - timedelta(days=550)).strftime("%Y-%m")
    endpoint = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/"
        "data/prc_hicp_manr"
    )
    # EA21 is the current official aggregate from 2026. EA20 is retained as a
    # bounded historical fallback for deployments whose mirror has not caught up.
    aggregate_candidates = ("EA21", "EA20", "EA")
    last_error: Exception | None = None
    for aggregate in aggregate_candidates:
        try:
            response = await http.get(
                endpoint,
                params={
                    "lang": "en",
                    "geo": aggregate,
                    "coicop": "CP00",
                    "unit": "RCH_A",
                    "sinceTimePeriod": start,
                },
            )
            response.raise_for_status()
            payload = response.json()
            raw_values = payload.get("value") or {}
            values = (
                {str(index): value for index, value in enumerate(raw_values)}
                if isinstance(raw_values, list)
                else raw_values
            )
            time_category = (
                ((payload.get("dimension") or {}).get("time") or {}).get(
                    "category"
                )
                or {}
            )
            time_index = time_category.get("index") or {}
            labels_by_index = {
                int(index): label
                for label, index in time_index.items()
                if str(index).isdigit()
            }
            observations = []
            for raw_index, raw_value in values.items():
                if not str(raw_index).isdigit():
                    continue
                value = _finite_number(raw_value)
                if value is not None:
                    index = int(raw_index)
                    observations.append(
                        (index, labels_by_index.get(index, str(index)), value)
                    )
            if not observations:
                raise ValueError(
                    f"Eurostat returned no HICP observation for {aggregate}"
                )
            observations.sort()
            _, period, latest = observations[-1]
            previous = observations[-2][2] if len(observations) > 1 else None
            geo_category = (
                ((payload.get("dimension") or {}).get("geo") or {}).get(
                    "category"
                )
                or {}
            )
            aggregate_label = (geo_category.get("label") or {}).get(
                aggregate, aggregate
            )
            return {
                "metrics": {
                    "euro_area_hicp_annual_pct": latest,
                    "previous_month_pct": previous,
                    "aggregate_code": aggregate,
                    "aggregate_label": aggregate_label,
                    "current_aggregate": aggregate == "EA21",
                },
                "as_of": period,
                "summary": (
                    f"{aggregate} euro-area annual HICP {latest}% in {period}"
                    + (
                        " (current official aggregate)"
                        if aggregate == "EA21"
                        else " (historical aggregate fallback)"
                    )
                ),
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            last_error = exc
    raise ValueError("Eurostat returned no current or fallback HICP aggregate") from last_error


async def _ingest_treasury(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates",
        params={
            "filter": "security_desc:eq:Treasury Bills",
            "fields": (
                "record_date,security_type_desc,security_desc,"
                "avg_interest_rate_amt"
            ),
            "page[size]": 1,
            "sort": "-record_date",
        },
    )
    response.raise_for_status()
    rows = response.json().get("data") or []
    if not rows:
        raise ValueError("Treasury returned no interest-rate record")
    selected = rows[0]
    latest_date = selected.get("record_date")
    if selected.get("security_desc") != "Treasury Bills":
        raise ValueError("Treasury response did not contain the requested bill series")
    rate = _finite_number(selected.get("avg_interest_rate_amt"))
    return {
        "metrics": {
            "record_date": latest_date,
            "security_type": selected.get("security_type_desc"),
            "security": selected.get("security_desc"),
            "average_interest_rate_pct": rate,
        },
        "as_of": latest_date,
        "summary": (
            "Official US Treasury average interest rate on outstanding "
            f"Treasury Bills: {rate}% ({latest_date}); this is not a new-issue yield"
        ),
    }


async def _ingest_regulations(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://www.federalregister.gov/api/v1/documents.json",
        params={"per_page": 5, "order": "newest"},
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") or []
    documents = [
        {
            "title": str(item.get("title") or "")[:180],
            "type": item.get("type"),
            "publication_date": item.get("publication_date"),
            "url": item.get("html_url"),
        }
        for item in results[:5]
        if item.get("title")
    ]
    if not documents:
        raise ValueError("Federal Register returned no recent document")
    return {
        "metrics": {"total_documents": payload.get("count"), "latest": documents},
        "as_of": documents[0].get("publication_date"),
        "summary": (
            f"{len(documents)} newest broad US federal notices in the official "
            "snapshot; filter the register by agency and topic before relying on it"
        ),
    }


async def _ingest_eu_tenders(http: httpx.AsyncClient) -> dict[str, Any]:
    since = (datetime.now(timezone.utc).date() - timedelta(days=14)).strftime("%Y%m%d")
    response = await http.post(
        "https://api.ted.europa.eu/v3/notices/search",
        json={
            "query": f"publication-date >= {since}",
            "fields": [
                "publication-number",
                "publication-date",
                "notice-title",
                "organisation-name-buyer",
            ],
            "page": 1,
            "limit": 5,
            "scope": "ACTIVE",
            "onlyLatestVersions": True,
        },
    )
    response.raise_for_status()
    payload = response.json()
    notices = []
    for item in (payload.get("notices") or [])[:5]:
        titles = item.get("notice-title") or {}
        title = titles.get("eng") if isinstance(titles, dict) else titles
        if not title and isinstance(titles, dict) and titles:
            title = next(iter(titles.values()))
        buyers = item.get("organisation-name-buyer") or {}
        buyer = buyers.get("eng") if isinstance(buyers, dict) else buyers
        if not buyer and isinstance(buyers, dict) and buyers:
            buyer = next(iter(buyers.values()))
        if isinstance(buyer, list):
            buyer = buyer[0] if buyer else None
        number = str(item.get("publication-number") or "")
        notices.append(
            {
                "publication_number": number,
                "publication_date": item.get("publication-date"),
                "title": str(title or "")[:180],
                "buyer": str(buyer or "")[:120],
                "url": f"https://ted.europa.eu/en/notice/-/detail/{number}" if number else None,
            }
        )
    notices.sort(
        key=lambda item: str(item.get("publication_date") or ""), reverse=True
    )
    if not notices:
        raise ValueError("TED returned no recent active notice")
    return {
        "metrics": {
            "active_notice_count": payload.get("totalNoticeCount"),
            "recent_notices": notices,
        },
        "as_of": notices[0].get("publication_date"),
        "summary": (
            f"{payload.get('totalNoticeCount')} active recent EU notices in a broad "
            "official snapshot; filter TED by country, deadline and CPV before use"
        ),
    }


async def _ingest_usgs(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson"
    )
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features") or []
    top = sorted(
        features,
        key=lambda item: _finite_number((item.get("properties") or {}).get("mag")) or 0,
        reverse=True,
    )[:3]
    events = [
        {
            "magnitude": (item.get("properties") or {}).get("mag"),
            "place": (item.get("properties") or {}).get("place"),
            "alert": (item.get("properties") or {}).get("alert"),
        }
        for item in top
    ]
    return {
        "metrics": {"significant_30d_count": len(features), "largest": events},
        "as_of": (
            datetime.fromtimestamp(
                float(((payload.get("metadata") or {}).get("generated") or 0))
                / 1_000,
                timezone.utc,
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            if ((payload.get("metadata") or {}).get("generated"))
            else None
        ),
        "summary": f"{len(features)} significant earthquakes in 30 days"
        + (f"; largest M{events[0]['magnitude']} {events[0]['place']}" if events else ""),
    }


async def _ingest_nasa_eonet(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://eonet.gsfc.nasa.gov/api/v3/events",
        params={"status": "open", "limit": 25},
    )
    response.raise_for_status()
    events = response.json().get("events") or []
    categories: dict[str, int] = {}
    observation_dates: list[str] = []
    for event in events:
        for category in event.get("categories") or []:
            title = str(category.get("title") or "Unknown")
            categories[title] = categories.get(title, 0) + 1
        for geometry in event.get("geometry") or []:
            if geometry.get("date"):
                observation_dates.append(str(geometry["date"]))
    return {
        "metrics": {"open_event_count": len(events), "categories": categories},
        "as_of": max(observation_dates, default=None),
        "summary": f"{len(events)} open NASA EONET natural events; "
        + ", ".join(f"{key}={value}" for key, value in sorted(categories.items())[:5]),
    }


async def _ingest_nws_alerts(http: httpx.AsyncClient) -> dict[str, Any]:
    """US operational-weather warning benchmark; fixed geography, no user data."""
    response = await http.get(
        "https://api.weather.gov/alerts/active",
        params={"area": "CA", "status": "actual"},
        headers={"User-Agent": APP_UA, "Accept": "application/geo+json"},
    )
    response.raise_for_status()
    features = response.json().get("features") or []
    severities: dict[str, int] = {}
    events: dict[str, int] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        severity = str(properties.get("severity") or "Unknown")
        event = str(properties.get("event") or "Unknown")
        severities[severity] = severities.get(severity, 0) + 1
        events[event] = events.get(event, 0) + 1
    top_events = dict(sorted(events.items(), key=lambda item: (-item[1], item[0]))[:5])
    return {
        "metrics": {
            "jurisdiction": "US-CA",
            "active_alert_count": len(features),
            "severity_counts": severities,
            "top_events": top_events,
        },
        "as_of": _utc_stamp(),
        "summary": f"{len(features)} active NWS alerts in California; "
        + ", ".join(f"{key}={value}" for key, value in top_events.items()),
    }


async def _ingest_cyber(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    )
    response.raise_for_status()
    payload = response.json()
    vulnerabilities = payload.get("vulnerabilities") or []
    recent = sorted(
        (item for item in vulnerabilities if isinstance(item, dict)),
        key=lambda item: str(item.get("dateAdded") or ""),
        reverse=True,
    )[:5]
    vendors: dict[str, int] = {}
    for item in recent:
        vendor = str(item.get("vendorProject") or "Unknown")
        vendors[vendor] = vendors.get(vendor, 0) + 1
    return {
        "metrics": {
            "catalog_count": payload.get("count", len(vulnerabilities)),
            "catalog_version": payload.get("catalogVersion"),
            "recent_vendors": vendors,
            "recently_added": [
                {
                    "cve": item.get("cveID"),
                    "vendor": item.get("vendorProject"),
                    "date_added": item.get("dateAdded"),
                }
                for item in recent
            ],
        },
        "as_of": payload.get("dateReleased") or (
            recent[0].get("dateAdded") if recent else None
        ),
        "summary": (
            f"CISA KEV catalog has {payload.get('count', len(vulnerabilities))} "
            "known exploited vulnerabilities; newest additions dated "
            f"{recent[0].get('dateAdded') if recent else 'unknown'}"
        ),
    }


async def _ingest_noaa_space_weather(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    )
    response.raise_for_status()
    rows = response.json()
    values = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            value = _finite_number(row.get("Kp"))
            time_tag = row.get("time_tag")
            if value is not None:
                values.append((time_tag, value))
        elif isinstance(row, list) and len(row) > 1:
            value = _finite_number(row[1])
            if value is not None:
                values.append((row[0], value))
    if not values:
        raise ValueError("NOAA returned no planetary K-index")
    latest_time, latest = values[-1]
    peak = max(value for _, value in values)
    return {
        "metrics": {"planetary_k_latest": latest, "planetary_k_recent_peak": peak},
        "as_of": latest_time,
        "summary": f"Planetary K-index {latest}; recent feed peak {peak}",
    }


async def _ingest_github(http: httpx.AsyncClient) -> dict[str, Any]:
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
    response = await http.get(
        "https://api.github.com/search/repositories",
        params={"q": f"created:>={cutoff} stars:>=20", "sort": "stars", "order": "desc", "per_page": 5},
        headers={"Accept": "application/vnd.github+json", "User-Agent": APP_UA},
    )
    response.raise_for_status()
    payload = response.json()
    items = [
        {
            "name": item.get("full_name"),
            "stars": item.get("stargazers_count"),
            "language": item.get("language"),
        }
        for item in (payload.get("items") or [])[:5]
    ]
    if not items:
        raise ValueError("GitHub search returned no repository")
    return {
        "metrics": {"new_repository_matches": payload.get("total_count"), "leaders": items},
        "as_of": _utc_stamp(),
        "summary": "Fast-rising new repositories: " + ", ".join(str(item["name"]) for item in items[:3]),
    }


async def _ingest_stackoverflow(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://api.stackexchange.com/2.3/questions",
        params={
            "site": "stackoverflow",
            "order": "desc",
            "sort": "hot",
            "pagesize": 30,
            "filter": "default",
        },
    )
    response.raise_for_status()
    payload = response.json()
    questions = payload.get("items") or []
    tags: dict[str, int] = {}
    for question in questions:
        for tag in question.get("tags") or []:
            tags[str(tag)] = tags.get(str(tag), 0) + 1
    leaders = sorted(tags.items(), key=lambda item: (-item[1], item[0]))[:8]
    return {
        "metrics": {
            "hot_question_count": len(questions),
            "top_tags": dict(leaders),
            "quota_remaining": payload.get("quota_remaining"),
        },
        "as_of": _utc_stamp(),
        "summary": "Hot Stack Overflow tags: " + ", ".join(f"{tag} ({count})" for tag, count in leaders[:5]),
    }


async def _ingest_holidays(http: httpx.AsyncClient) -> dict[str, Any]:
    year = datetime.now(timezone.utc).year
    response = await http.get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/US")
    response.raise_for_status()
    today = datetime.now(timezone.utc).date()
    future = []
    for item in response.json():
        try:
            day = datetime.strptime(item["date"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            continue
        if day >= today:
            future.append({"date": item["date"], "name": item.get("name")})
    future.sort(key=lambda item: item["date"])
    return {
        "metrics": {"jurisdiction": "US", "next_holidays": future[:5]},
        "as_of": _utc_stamp(),
        "summary": (
            f"Next US public holiday: {future[0]['name']} on {future[0]['date']}"
            if future
            else "No remaining US public holiday in current year"
        ),
    }


async def _ingest_openfda(http: httpx.AsyncClient) -> dict[str, Any]:
    response = await http.get(
        "https://api.fda.gov/food/enforcement.json",
        params={"limit": 5, "sort": "report_date:desc"},
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") or []
    recent = [
        {
            "classification": item.get("classification"),
            "product": str(item.get("product_description") or "")[:140],
            "reason": str(item.get("reason_for_recall") or "")[:160],
            "report_date": item.get("report_date"),
        }
        for item in results[:5]
    ]
    if not recent:
        raise ValueError("openFDA returned no enforcement record")
    return {
        "metrics": {"recent_food_enforcement": recent},
        "as_of": recent[0].get("report_date"),
        "summary": f"{len(recent)} recent US food enforcement records; newest class {recent[0]['classification']}",
    }


@dataclass(frozen=True)
class SourceSpec:
    key: str
    label: str
    layer: str
    source: str
    source_url: str
    fetcher: Fetcher
    tags: frozenset[str]
    ttl_seconds: int
    stale_seconds: int
    authority: Literal["official", "public", "community"] = "official"
    limitation: str = "Global context only; verify applicability to the user's jurisdiction."

    @property
    def provider(self) -> str:
        """Canonical provider attribution; ``source`` remains API-compatible."""
        return self.source


def _spec(
    key: str,
    label: str,
    layer: str,
    source: str,
    source_url: str,
    fetcher: Fetcher,
    tags: tuple[str, ...],
    ttl: int,
    stale: int,
    authority: Literal["official", "public", "community"] = "official",
    limitation: str = "Global context only; verify applicability to the user's jurisdiction.",
) -> SourceSpec:
    return SourceSpec(
        key, label, layer, source, source_url, fetcher, frozenset(tags), ttl, stale,
        authority, limitation,
    )


SOURCE_SPECS: tuple[SourceSpec, ...] = (
    _spec("macro", "FX Momentum", "macro", "Frankfurter / ECB reference data", "https://www.frankfurter.app/", _ingest_macro, ("fx", "macro"), 43_200, 172_800, "public"),
    _spec("ecb_fx", "Official ECB FX Baseline", "macro", "European Central Bank Data API", "https://data.ecb.europa.eu/help/api/overview", _ingest_ecb_fx, ("core", "fx", "macro"), 43_200, 172_800),
    _spec("markets", "Digital Markets & Gold Proxy", "markets", "CoinGecko public API", "https://docs.coingecko.com/reference/simple-price", _ingest_markets, ("markets", "finance", "crypto"), 600, 3_600, "public", "Public-market proxy; not an execution price or investment recommendation."),
    _spec("attention", "Technology Attention", "demand", "Hacker News official Firebase API", "https://github.com/HackerNews/API", _ingest_attention, ("technology", "startup", "demand"), 600, 3_600, "public", "Technology-community attention is not representative of the whole market."),
    _spec("world_bank", "Global Structural Indicators", "macro", "World Bank Indicators API", "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392", _ingest_world_bank, ("macro", "international", "trade", "strategic"), 43_200, 604_800),
    _spec("eurostat_inflation", "Euro-area Inflation", "macro", "Eurostat dissemination API", "https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction", _ingest_eurostat, ("macro", "inflation", "pricing", "trade", "strategic"), 43_200, 2_592_000, "official", "Euro-area HICP benchmark; it is not the user's local inflation rate."),
    _spec("us_labor", "US Labor & Inflation", "labor", "U.S. Bureau of Labor Statistics Public Data API", "https://www.bls.gov/developers/", _ingest_us_labor, ("labor", "macro", "hiring", "pricing"), 43_200, 604_800, "official", "United States series; use only as a global benchmark outside the US."),
    _spec("treasury_fiscal", "US Fiscal Rate Context", "rates", "U.S. Treasury Fiscal Data API", "https://fiscaldata.treasury.gov/api-documentation/", _ingest_treasury, ("rates", "finance", "macro", "capital"), 21_600, 172_800, "official", "United States fiscal context; not a local borrowing quote."),
    _spec("regulations", "Regulatory Change Monitor", "regulation", "U.S. Federal Register API", "https://www.federalregister.gov/developers/documentation/api/v1", _ingest_regulations, ("regulation", "compliance", "b2b", "strategic"), 3_600, 86_400, "official", "US-only notice stream; local legal review remains necessary."),
    _spec("eu_tenders", "EU Public Procurement", "opportunity", "TED Search API / Publications Office of the EU", "https://docs.ted.europa.eu/api/latest/search.html", _ingest_eu_tenders, ("procurement", "geography_eu", "b2b", "opportunity"), 1_800, 21_600, "official", "Broad EU snapshot only; filter official TED results by CPV, country, eligibility and deadline before use."),
    _spec("earthquakes", "Seismic Operations Risk", "hazards", "U.S. Geological Survey GeoJSON feed", "https://earthquake.usgs.gov/earthquakes/feed/", _ingest_usgs, ("hazards", "seismic"), 300, 3_600),
    _spec("natural_events", "Global Natural Events", "hazards", "NASA EONET v3", "https://eonet.gsfc.nasa.gov/docs/v3", _ingest_nasa_eonet, ("hazards", "natural_hazard"), 900, 21_600),
    _spec("us_weather_alerts", "California Weather Operations Alerts", "hazards", "U.S. National Weather Service API", "https://www.weather.gov/documentation/services-web-api", _ingest_nws_alerts, ("hazards", "weather", "geography_california"), 300, 1_800, "official", "California-only alert feed; use it only for California operations and verify the exact county in NWS."),
    _spec("cyber_risk", "Known Exploited Cyber Risk", "cyber", "CISA Known Exploited Vulnerabilities", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", _ingest_cyber, ("cyber", "technology", "software", "b2b", "operations"), 21_600, 604_800),
    _spec("space_weather", "Infrastructure Space Weather", "hazards", "NOAA Space Weather Prediction Center", "https://www.swpc.noaa.gov/products/planetary-k-index", _ingest_noaa_space_weather, ("hazards", "space_weather", "infrastructure"), 900, 21_600),
    _spec("github_demand", "Open-source Technology Momentum", "technology", "GitHub REST API", "https://docs.github.com/en/rest/search/search", _ingest_github, ("technology", "software", "skills", "startup", "demand"), 3_600, 43_200, "public"),
    _spec("stackoverflow_skills", "Technology Skill Demand", "skills", "Stack Exchange API", "https://api.stackexchange.com/docs", _ingest_stackoverflow, ("technology", "software", "skills", "career", "demand"), 3_600, 43_200, "public"),
    _spec("business_calendar", "US Business Calendar", "calendar", "Nager.Date public API", "https://date.nager.at/Api", _ingest_holidays, ("calendar", "geography_us"), 43_200, 604_800, "community", "US calendar only; confirm the user's state and local closures."),
    _spec("food_safety", "Food Safety Enforcement", "compliance", "openFDA enforcement API", "https://open.fda.gov/apis/food/enforcement/", _ingest_openfda, ("food_safety", "geography_us", "compliance"), 3_600, 86_400, "official", "US food-enforcement data only; it is not legal, medical or product-safety advice."),
)
SOURCE_BY_KEY = {spec.key: spec for spec in SOURCE_SPECS}


TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "technology": (
        "software", "app", "saas", "ai", "tech", "artificial intelligence",
        "machine learning", "developer*", "coding", "web app", "mobile app",
        "tech startup",
    ),
    "crypto": ("crypto", "cryptocurrency", "bitcoin", "ethereum", "digital asset*"),
    "skills": ("skill*", "learn*", "career", "freelanc*", "job"),
    "supply": ("supply chain", "supplier*", "inventory", "shipping", "logistics"),
    "trade": ("import*", "export*", "tariff*", "international trade"),
    "finance": (
        "invest*", "capital", "financial market*", "currency", "loan*", "funding",
    ),
    "rates": ("interest rate*", "yield*", "treasury bill*", "bond*"),
    "labor": ("hire", "hiring", "salary", "employee*", "labor", "workforce", "payroll"),
    "regulation": ("law", "legal", "regulat*", "license", "licensing", "compliance"),
    "risk": ("risk", "low risk", "risk management"),
    "natural_hazard": (
        "natural disaster*", "natural hazard*", "wildfire*", "flood*", "hurricane*",
        "disaster recovery",
    ),
    "seismic": ("earthquake*", "seismic"),
    "weather": ("weather alert*", "weather disruption*", "storm*", "california weather"),
    "space_weather": (
        "space weather", "solar storm*", "geomagnetic", "satellite disruption*",
        "gps disruption*",
    ),
    "food": ("food", "restaurant*"),
    "food_safety": ("food safety", "food recall*", "fda recall*", "food contamination"),
    "sales": ("sales", "customer*", "client*", "marketing", "retail", "email campaign*"),
    "procurement": (
        "public procurement", "tender*", "request for proposal", "rfp",
        "government bid*",
    ),
    "cyber": ("cyber", "cybersecurity", "ransomware", "vulnerabilit*", "known exploited"),
    "calendar": ("public holiday*", "business calendar", "bank holiday*"),
    "macro": ("gdp", "economic growth", "macroeconomic*", "economy"),
    "inflation": ("inflation", "consumer price*", "hicp"),
    "pricing": ("pricing", "price benchmark*"),
    "fx": ("exchange rate*", "forex", "eur/usd", "currency conversion"),
    "manufacturing": ("manufactur*", "factory", "production line"),
    "infrastructure": ("critical infrastructure", "power grid", "satellite", "gps"),
    "startup": ("startup", "venture"),
    "strategic": ("strateg*", "long term", "long-term"),
    "geography_us": ("united states", "u.s.", "usa", "california", "new york", "texas"),
    "geography_california": ("california",),
    "geography_eu": (
        "european union", "europe*", "eu", "euro area", "eurozone", "germany",
        "berlin", "france", "spain", "italy", "netherlands", "sweden", "poland",
    ),
}


def _matches_routing_pattern(text: str, pattern: str) -> bool:
    """Match exact tokens/phrases; a trailing * explicitly permits a suffix."""
    normalized_pattern = re.sub(r"\s+", " ", pattern.casefold()).strip()
    wildcard = normalized_pattern.endswith("*")
    stem = normalized_pattern[:-1] if wildcard else normalized_pattern
    if not stem:
        return False
    suffix = r"\w*" if wildcard else ""
    expression = rf"(?<!\w){re.escape(stem)}{suffix}(?!\w)"
    return re.search(expression, text, flags=re.UNICODE) is not None


def infer_routing_tags(
    query: str,
    tier: Tier,
    horizon: str = "instant",
    routing_context: str = "",
) -> list[str]:
    # Both fields stay local. Only the inferred taxonomy is exposed or sent to
    # fixed upstream endpoints; raw user text never enters an external API DSL.
    raw_routing_text = f"{str(query or '')} {str(routing_context or '')}"
    normalized = re.sub(r"\s+", " ", raw_routing_text.casefold()).strip()
    tags = {"core", "b2b" if tier == "B2B" else "b2c"}
    if re.search(r"(?<![\w])US(?![\w])", raw_routing_text):
        tags.add("geography_us")
    if horizon == "strategic":
        tags.add("strategic")
    for tag, patterns in TAG_PATTERNS.items():
        if any(_matches_routing_pattern(normalized, pattern) for pattern in patterns):
            tags.add(tag)
    return sorted(tags)


def _source_route_score(spec: SourceSpec, tags: set[str], tier: Tier) -> int:
    """Return zero for an ineligible branch, otherwise a deterministic score."""
    key = spec.key
    if key == "macro":
        return 5 if "fx" in tags else 0
    if key == "markets":
        return 6 if "crypto" in tags else 0
    if key == "attention":
        return 5 if "technology" in tags else 0
    if key == "world_bank":
        return 5 if tags & {"macro", "strategic", "trade"} else 0
    if key == "eurostat_inflation":
        return 6 if "inflation" in tags or ({"geography_eu", "pricing"} <= tags) else 0
    if key == "us_labor":
        return 6 if {"labor", "geography_us"} <= tags else 0
    if key == "treasury_fiscal":
        return 6 if "rates" in tags and "geography_eu" not in tags else 0
    if key == "regulations":
        return 7 if {"regulation", "geography_us"} <= tags else 0
    if key == "eu_tenders":
        return 8 if tier == "B2B" and {"procurement", "geography_eu"} <= tags else 0
    if key == "earthquakes":
        return 8 if "seismic" in tags else 0
    if key == "natural_events":
        return 7 if "natural_hazard" in tags else 0
    if key == "us_weather_alerts":
        return 8 if {"weather", "geography_california"} <= tags else 0
    if key == "cyber_risk":
        return 8 if "cyber" in tags else 0
    if key == "space_weather":
        return 8 if "space_weather" in tags else 0
    if key == "github_demand":
        return 5 if "technology" in tags else 0
    if key == "stackoverflow_skills":
        return 7 if {"technology", "skills"} <= tags else 0
    if key == "business_calendar":
        return 7 if {"calendar", "geography_us"} <= tags else 0
    if key == "food_safety":
        return 8 if {"food_safety", "geography_us"} <= tags else 0
    return 0


def select_source_specs(
    query: str = "",
    tier: Tier = "B2C",
    horizon: str = "instant",
    routing_context: str = "",
) -> tuple[list[SourceSpec], list[str]]:
    tags = infer_routing_tags(query, tier, horizon, routing_context)
    tag_set = set(tags)
    # The only universal baseline is the official ECB observation. Community
    # market proxies and HN must earn selection through explicit user intent.
    core_order = ["ecb_fx"]
    selected = [SOURCE_BY_KEY["ecb_fx"]]
    candidates = [spec for spec in SOURCE_SPECS if spec.key not in core_order]
    ranked = sorted(
        candidates,
        key=lambda spec: (
            -_source_route_score(spec, tag_set, tier),
            0 if spec.authority == "official" else 1,
            -len(spec.tags & tag_set),
            spec.key,
        ),
    )
    used_layers = {spec.layer for spec in selected}
    deferred: list[SourceSpec] = []
    for spec in ranked:
        if len(selected) >= MAX_SELECTED_SOURCES:
            break
        if _source_route_score(spec, tag_set, tier) <= 0:
            continue
        if spec.layer in used_layers:
            deferred.append(spec)
            continue
        selected.append(spec)
        used_layers.add(spec.layer)
    # Fill any remaining slots only after maximizing evidence-layer diversity.
    for spec in deferred:
        if len(selected) >= MAX_SELECTED_SOURCES:
            break
        selected.append(spec)
    return selected, tags


_SOURCE_CACHE: dict[str, dict[str, Any]] = {}
_SOURCE_LOCKS: dict[str, asyncio.Lock] = {}
_SOURCE_FAILURES: dict[str, dict[str, Any]] = {}


class SourceBackoffOpen(RuntimeError):
    """A recent source failure opened a short in-memory retry backoff."""


def _cache_attribution(status: str) -> dict[str, Any]:
    served_from_cache: bool | None
    if status in {"fresh", "stale"}:
        served_from_cache = True
    elif status in {"miss", "bypassed", "unavailable"}:
        served_from_cache = False
    else:
        served_from_cache = None
    return {
        "status": status,
        "served_from_cache": served_from_cache,
        "stale": status == "stale",
    }


def _set_cache_status(item: dict[str, Any], status: str) -> dict[str, Any]:
    item["cache_status"] = status
    item["cache"] = _cache_attribution(status)
    return item


def _source_lock(key: str) -> asyncio.Lock:
    lock = _SOURCE_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _SOURCE_LOCKS[key] = lock
    return lock


async def _fetch_one(http: httpx.AsyncClient, spec: SourceSpec) -> dict[str, Any]:
    now = time.monotonic()
    cached = _SOURCE_CACHE.get(spec.key)
    if cached and now - float(cached.get("at", 0)) < max(
        INTELLIGENCE_CACHE_SECONDS, spec.ttl_seconds
    ):
        item = dict(cached["data"])
        item.pop("stale", None)
        return _set_cache_status(item, "fresh")
    failure = _SOURCE_FAILURES.get(spec.key)
    if failure and now < float(failure.get("circuit_open_until", 0)):
        if cached and now - float(cached.get("at", 0)) < spec.stale_seconds:
            item = dict(cached["data"])
            item.update(
                {
                    "stale": True,
                    "circuit_open": True,
                }
            )
            return _set_cache_status(item, "stale")
        raise SourceBackoffOpen("source retry backoff is active")
    async with _source_lock(spec.key):
        now = time.monotonic()
        cached = _SOURCE_CACHE.get(spec.key)
        if cached and now - float(cached.get("at", 0)) < max(
            INTELLIGENCE_CACHE_SECONDS, spec.ttl_seconds
        ):
            item = dict(cached["data"])
            item.pop("stale", None)
            return _set_cache_status(item, "fresh")
        failure = _SOURCE_FAILURES.get(spec.key)
        if failure and now < float(failure.get("circuit_open_until", 0)):
            if cached and now - float(cached.get("at", 0)) < spec.stale_seconds:
                item = dict(cached["data"])
                item.update(
                    {
                        "stale": True,
                        "circuit_open": True,
                    }
                )
                return _set_cache_status(item, "stale")
            raise SourceBackoffOpen("source retry backoff is active")
        try:
            # httpx timeouts apply per operation. The outer wall-clock timeout
            # also bounds adapters that make multiple sequential requests.
            raw = await asyncio.wait_for(
                spec.fetcher(http), timeout=SOURCE_FETCH_HARD_TIMEOUT_SECONDS
            )
            item = {
                **raw,
                "key": spec.key,
                "label": spec.label,
                "layer": spec.layer,
                "source": spec.source,
                "provider": spec.provider,
                "source_url": spec.source_url,
                "authority": spec.authority,
                "api_cost_usd": 0,
                "requires_api_key": False,
                "limitation": spec.limitation,
            }
            _set_cache_status(item, "miss")
            _SOURCE_CACHE[spec.key] = {"at": now, "data": dict(item)}
            _SOURCE_FAILURES.pop(spec.key, None)
            return item
        except Exception as exc:
            previous_failures = int(
                (_SOURCE_FAILURES.get(spec.key) or {}).get("failure_count", 0)
            )
            failure_count = min(previous_failures + 1, 8)
            backoff_seconds = min(300, 15 * (2 ** (failure_count - 1)))
            _SOURCE_FAILURES[spec.key] = {
                "failure_count": failure_count,
                "circuit_open_until": now + backoff_seconds,
                "error": type(exc).__name__,
            }
            if cached and now - float(cached.get("at", 0)) < spec.stale_seconds:
                item = dict(cached["data"])
                item.update(
                    {
                        "stale": True,
                        "circuit_open": True,
                    }
                )
                return _set_cache_status(item, "stale")
            raise


def _metric_completeness(metrics: Any) -> float:
    values: list[Any] = []

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 3:
            return
        if isinstance(value, dict):
            for nested in value.values():
                walk(nested, depth + 1)
        elif isinstance(value, list):
            if not value:
                values.append(None)
            else:
                for nested in value[:8]:
                    walk(nested, depth + 1)
        else:
            values.append(value)

    walk(metrics)
    return sum(value is not None and value != "" for value in values) / len(values) if values else 0.0


_OBSERVATION_FRESHNESS_DAYS: dict[str, int] = {
    "macro": 7,
    "ecb_fx": 7,
    "markets": 2,
    "attention": 2,
    "world_bank": 1_095,
    "eurostat_inflation": 90,
    "us_labor": 90,
    "treasury_fiscal": 62,
    "regulations": 30,
    "eu_tenders": 21,
    "earthquakes": 2,
    "natural_events": 14,
    "us_weather_alerts": 2,
    "cyber_risk": 45,
    "space_weather": 2,
    "github_demand": 2,
    "stackoverflow_skills": 2,
    "business_calendar": 2,
    "food_safety": 365,
}


def _parse_observation_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if re.fullmatch(r"\d{4}", text):
            return datetime(int(text), 12, 31, tzinfo=timezone.utc)
        if re.fullmatch(r"\d{4}-\d{2}", text):
            year, month = (int(part) for part in text.split("-"))
            next_month = (
                datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                if month == 12
                else datetime(year, month + 1, 1, tzinfo=timezone.utc)
            )
            return next_month - timedelta(microseconds=1)
        if re.fullmatch(r"\d{8}", text):
            return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[+-]\d{2}:\d{2})?", text):
            return datetime.strptime(text[:10], "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        fractional = re.search(r"\.(\d+)(?=Z$|[+-]\d{2}:?\d{2}$)", text)
        if fractional:
            normalized_fraction = fractional.group(1)[:6].ljust(6, "0")
            text = (
                text[: fractional.start(1)]
                + normalized_fraction
                + text[fractional.end(1) :]
            )
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(
            timezone.utc
        )
    except (OverflowError, TypeError, ValueError):
        return None


def _observation_freshness(
    spec: SourceSpec, item: dict[str, Any]
) -> tuple[float, float | None]:
    observed = _parse_observation_time(item.get("as_of"))
    if observed is None:
        score = 0.55
        return (round(score * 0.7, 2), None) if item.get("stale") else (score, None)
    age_days = max(
        0.0, (datetime.now(timezone.utc) - observed).total_seconds() / 86_400
    )
    window = _OBSERVATION_FRESHNESS_DAYS.get(spec.key, 30)
    if age_days <= window:
        score = 1.0
    elif age_days <= window * 2:
        score = 0.85
    elif age_days <= window * 4:
        score = 0.7
    else:
        score = 0.5
    if item.get("stale"):
        score *= 0.7
    return round(score, 2), round(age_days, 1)


def _freshness_attribution(
    item: dict[str, Any], score: float, observation_age_days: float | None
) -> dict[str, Any]:
    if item.get("stale"):
        status = "stale_cache"
    elif _parse_observation_time(item.get("as_of")) is None:
        status = "unknown"
    elif score >= 0.85:
        status = "current"
    elif score >= 0.7:
        status = "aging"
    else:
        status = "old"
    return {
        "status": status,
        "score": score,
        "observation_age_days": observation_age_days,
    }


def _evidence_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    status = str(item.get("status") or "degraded")
    quality = item.get("quality") or {}
    status_rank = {"live": 0, "partial": 1, "stale": 2, "degraded": 3}.get(
        status, 3
    )
    authority_rank = {"official": 0, "public": 1, "community": 2}.get(
        str(item.get("authority") or "community"), 2
    )
    return (
        status_rank,
        authority_rank,
        -float(quality.get("relevance") or 0),
        -float(quality.get("freshness") or 0),
        -float(quality.get("weighted") or 0),
        str(item.get("key") or ""),
    )


def assemble_intelligence(
    results: list[Any], specs: list[SourceSpec] | None = None, routing_tags: list[str] | None = None
) -> dict[str, Any]:
    selected = specs or list(SOURCE_SPECS[: len(results)])
    streams: list[dict[str, Any]] = []
    live = 0.0
    routing_tag_set = set(routing_tags or []) - {"core", "b2c", "b2b"}
    for spec, result in zip(selected, results):
        if isinstance(result, Exception):
            streams.append(
                {
                    "key": spec.key,
                    "label": spec.label,
                    "layer": spec.layer,
                    "status": "degraded",
                    "source": spec.source,
                    "provider": spec.provider,
                    "source_url": spec.source_url,
                    "authority": spec.authority,
                    "api_cost_usd": 0,
                    "requires_api_key": False,
                    "as_of": None,
                    "cache_status": "unavailable",
                    "cache": _cache_attribution("unavailable"),
                    "freshness": {
                        "status": "unavailable",
                        "score": 0.0,
                        "observation_age_days": None,
                    },
                    "observation_age_days": None,
                    "metrics": None,
                    "completeness": 0.0,
                    "quality": {
                        "authority": {
                            "official": 1.0,
                            "public": 0.9,
                            "community": 0.75,
                        }.get(spec.authority, 0.75),
                        "freshness": 0.0,
                        "completeness": 0.0,
                        "relevance": 0.0,
                        "weighted": 0.0,
                    },
                    "summary": "Live feed unavailable; the branch degraded safely.",
                    "limitation": spec.limitation,
                    "error": type(result).__name__,
                }
            )
            continue
        item = dict(result)
        item.update(
            {
                "key": spec.key,
                "label": spec.label,
                "layer": spec.layer,
                "source": spec.source,
                "provider": spec.provider,
                "source_url": spec.source_url,
                "authority": spec.authority,
                "api_cost_usd": 0,
                "requires_api_key": False,
                "limitation": spec.limitation,
            }
        )
        _set_cache_status(item, str(item.get("cache_status") or "untracked"))
        completeness = round(_metric_completeness(item.get("metrics")), 2)
        authority_score = {"official": 1.0, "public": 0.9, "community": 0.75}.get(
            spec.authority, 0.75
        )
        freshness_score, observation_age_days = _observation_freshness(spec, item)
        matching_tags = len(spec.tags & routing_tag_set)
        relevance_score = (
            0.9
            if "core" in spec.tags
            else min(1.0, 0.75 + (matching_tags * 0.2))
        )
        quality_score = round(
            completeness * authority_score * freshness_score * relevance_score, 3
        )
        item["completeness"] = completeness
        item["quality"] = {
            "authority": authority_score,
            "freshness": freshness_score,
            "completeness": completeness,
            "relevance": relevance_score,
            "weighted": quality_score,
        }
        item["observation_age_days"] = observation_age_days
        item["freshness"] = _freshness_attribution(
            item, freshness_score, observation_age_days
        )
        item["status"] = (
            "stale"
            if item.get("stale")
            else "live"
            if completeness >= 0.8
            else "partial"
            if completeness > 0
            else "degraded"
        )
        live += quality_score
        streams.append(item)
    streams.sort(key=_evidence_sort_key)
    total = len(selected)
    live = round(live, 2)
    label_live: int | float = int(live) if live.is_integer() else live
    catalog = [
        {
            "key": spec.key,
            "label": spec.label,
            "layer": spec.layer,
            "source": spec.source,
            "provider": spec.provider,
            "source_url": spec.source_url,
            "authority": spec.authority,
            "api_cost_usd": 0,
            "requires_api_key": False,
            "selected": spec in selected,
            "limitation": spec.limitation,
        }
        for spec in SOURCE_SPECS
    ]
    return {
        "coverage_live": live,
        "coverage_total": total,
        "coverage_label": f"{label_live}/{total}",
        "captured_at": _utc_stamp(),
        "streams": streams,
        "routing_tags": routing_tags or [],
        "selected_source_count": total,
        "available_source_count": len(SOURCE_SPECS),
        "layer_count": len({spec.layer for spec in SOURCE_SPECS}),
        "all_external_apis_free": True,
        "external_api_cost_usd": 0,
        "source_catalog": catalog,
    }


def _network_disabled_envelope(
    specs: list[SourceSpec], routing_tags: list[str], mode: str, reason: str
) -> dict[str, Any]:
    """Build a stable degraded result without consulting HTTP or source caches."""
    result = assemble_intelligence(
        [RuntimeError(reason) for _ in specs], specs, routing_tags
    )
    summary = (
        "External intelligence was not fetched because offline mode is enabled."
        if mode == "offline"
        else "External intelligence was not fetched because demo mode disables network access by default."
    )
    error = "OfflineModeActive" if mode == "offline" else "DemoNetworkDisabled"
    for stream in result["streams"]:
        stream.update(
            {
                "summary": summary,
                "error": error,
                "cache_status": "bypassed",
                "cache": _cache_attribution("bypassed"),
                "freshness": {
                    "status": "not_fetched",
                    "score": 0.0,
                    "observation_age_days": None,
                },
            }
        )
    result.update(
        {
            "captured_at": None,
            "cache_status": "bypassed",
            "mode": mode,
            "offline": True,
            "network_status": "disabled",
            "network_requests_made": 0,
            "degraded_reason": reason,
        }
    )
    return result


async def gather_market_intelligence(
    query: str = "",
    tier: Tier = "B2C",
    horizon: str = "instant",
    routing_context: str = "",
) -> dict[str, Any]:
    specs, routing_tags = select_source_specs(
        query, tier, horizon, routing_context
    )
    disabled_mode = _network_disabled_mode()
    if disabled_mode is not None:
        mode, reason = disabled_mode
        return _network_disabled_envelope(specs, routing_tags, mode, reason)
    async with _BoundedAsyncClient(
        timeout=INGEST_TIMEOUT,
        proxy=OMNI_HTTP_PROXY or None,
        follow_redirects=False,
        headers={"User-Agent": APP_UA, "Accept": "application/json"},
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
    ) as http:
        results = await asyncio.gather(
            *[_fetch_one(http, spec) for spec in specs], return_exceptions=True
        )
    result = assemble_intelligence(list(results), specs, routing_tags)
    result["cache_status"] = (
        "hit"
        if result["streams"] and all(item.get("cache_status") == "fresh" for item in result["streams"])
        else "mixed"
    )
    return result


def _safe_compact(value: Any, limit: int) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


def compact_intelligence_for_ai(
    intelligence: dict[str, Any], max_chars: int = AI_EVIDENCE_MAX_CHARS
) -> dict[str, Any]:
    """Build a source-attributed evidence packet with a hard serialized ceiling."""
    max_chars = max(2_000, min(AI_EVIDENCE_MAX_CHARS, int(max_chars)))
    packet: dict[str, Any] = {
        "captured_at": intelligence.get("captured_at"),
        "quality_weighted_coverage": intelligence.get("coverage_label"),
        "routing_tags": list(intelligence.get("routing_tags") or [])[:12],
        "cost": {"external_api_cost_usd": 0, "additional_model_calls": 0},
        "evidence": [],
    }
    all_streams = list(intelligence.get("streams") or [])
    usable_streams = [
        stream
        for stream in sorted(all_streams, key=_evidence_sort_key)
        if str(stream.get("status") or "degraded") != "degraded"
        and str(stream.get("summary") or "").strip()
    ]
    for stream in usable_streams:
        entry = {
            "key": str(stream.get("key") or "")[:64],
            "layer": str(stream.get("layer") or "")[:48],
            "status": str(stream.get("status") or "degraded")[:16],
            "as_of": str(stream.get("as_of") or "unknown")[:40],
            "observation": str(stream.get("summary") or "")[:360],
            "source": str(stream.get("source") or "")[:120],
            "authority": str(stream.get("authority") or "public")[:16],
            "quality": round(
                float((stream.get("quality") or {}).get("weighted") or 0), 3
            ),
            "limitation": str(stream.get("limitation") or "")[:220],
        }
        candidate = {**packet, "evidence": [*packet["evidence"], entry]}
        if len(_safe_compact(candidate, max_chars + 1)) > max_chars:
            break
        packet["evidence"].append(entry)
    packet["omitted_selected_sources"] = max(
        0, len(all_streams) - len(packet["evidence"])
    )
    # Defensive final shrink for unusual timestamps/source labels.
    while len(_safe_compact(packet, max_chars + 1)) > max_chars and packet["evidence"]:
        packet["evidence"].pop()
        packet["omitted_selected_sources"] += 1
    return packet


def build_live_feed_text(intelligence: dict[str, Any]) -> str:
    """Backwards-compatible bounded representation used by diagnostics/tests."""
    return _safe_compact(compact_intelligence_for_ai(intelligence), AI_EVIDENCE_MAX_CHARS)


__all__ = [
    "AI_EVIDENCE_MAX_CHARS",
    "SOURCE_SPECS",
    "assemble_intelligence",
    "build_live_feed_text",
    "compact_intelligence_for_ai",
    "gather_market_intelligence",
    "infer_routing_tags",
    "select_source_specs",
]
