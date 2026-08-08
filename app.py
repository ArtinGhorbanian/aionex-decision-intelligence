from fastapi import FastAPI, Request, HTTPException, status, Query
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse
from collections import defaultdict
import time
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator
import uvicorn
import asyncio
import httpx
import os
import uuid
import hashlib
import hmac
import secrets
import re
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import urlsplit
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)
import omni_store as store  # noqa: E402 - storage reads OMNI_DB_PATH at import time
from omni_intake import build_questions, extract_facts_from_query, validate_answers  # noqa: E402
from omni_ai import OmniAIGateway, OmniAIError  # noqa: E402 - env must load before settings
from omni_intelligence import (  # noqa: E402
    compact_intelligence_for_ai,
    gather_market_intelligence as gather_free_intelligence,
)
from omni_resources import build_execution_kit  # noqa: E402

AI_GATEWAY = OmniAIGateway()


def _safe_positive_int(name: str, default: int, minimum: int = 1, maximum: int = 86400) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


PREDICTION_SWEEP_INTERVAL_SECONDS = _safe_positive_int("OMNI_SWEEP_INTERVAL", 900, 60, 86400)
SESSION_COOKIE = "omni_session"
SESSION_ID_RE = re.compile(r"^[a-f0-9]{32}$")
MAX_REQUEST_BYTES = _safe_positive_int("OMNI_MAX_REQUEST_BYTES", 128_000, 8_192, 1_000_000)
HTTP_STATUS_CONTENT_TOO_LARGE = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)
MAX_ANALYSES_PER_DAY = _safe_positive_int("OMNI_MAX_ANALYSES_PER_DAY", 20, 1, 1000)
MAX_CHAT_MESSAGES_PER_DAY = _safe_positive_int("OMNI_MAX_CHAT_MESSAGES_PER_DAY", 80, 1, 5000)
MAX_DEEP_DIVES_PER_DAY = _safe_positive_int("OMNI_MAX_DEEP_DIVES_PER_DAY", 40, 1, 2000)
GLOBAL_MAX_ANALYSES_PER_DAY = _safe_positive_int(
    "OMNI_GLOBAL_MAX_ANALYSES_PER_DAY", MAX_ANALYSES_PER_DAY, 1, 100_000
)
GLOBAL_MAX_CHAT_MESSAGES_PER_DAY = _safe_positive_int(
    "OMNI_GLOBAL_MAX_CHAT_MESSAGES_PER_DAY", MAX_CHAT_MESSAGES_PER_DAY, 1, 500_000
)
GLOBAL_MAX_DEEP_DIVES_PER_DAY = _safe_positive_int(
    "OMNI_GLOBAL_MAX_DEEP_DIVES_PER_DAY", MAX_DEEP_DIVES_PER_DAY, 1, 200_000
)
COOKIE_SECURE = os.getenv("OMNI_SECURE_COOKIE", "0") == "1"
LEGACY_CLAIM_TOKEN = os.getenv("OMNI_LEGACY_CLAIM_TOKEN", "").strip()


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse an explicit boolean environment switch with a safe fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


# Prediction resolution performs outbound requests. Keep it opt-in and make
# demo, CI, and explicit offline runs authoritative so local verification never
# surprises the operator with background network traffic.
OFFLINE_MODE = _env_flag(
    "OMNI_OFFLINE_MODE",
    _env_flag(
        "OMNI_OFFLINE",
        AI_GATEWAY.settings.demo_mode or bool(os.getenv("CI", "").strip()),
    ),
)
PREDICTION_NETWORK_ENABLED = (
    _env_flag("OMNI_PREDICTION_NETWORK_ENABLED") and not OFFLINE_MODE
)
PREDICTION_SWEEPER_ENABLED = (
    _env_flag("OMNI_PREDICTION_SWEEPER_ENABLED")
    and PREDICTION_NETWORK_ENABLED
)


def _generation_ttl_seconds() -> int:
    """Outlive bounded queue wait + provider timeout, with a cancellation margin."""
    return max(120, min(900, int(AI_GATEWAY.settings.timeout_seconds * 2 + 35)))


def _load_session_secret() -> bytes:
    configured = os.getenv("OMNI_SESSION_SECRET", "").strip()
    if configured:
        if len(configured) < 32:
            raise RuntimeError("OMNI_SESSION_SECRET must contain at least 32 characters.")
        return configured.encode("utf-8")
    path = BASE_DIR / ".omni_session_secret"
    try:
        if path.exists():
            stored = path.read_text(encoding="utf-8").strip()
            if len(stored) >= 32:
                return stored.encode("utf-8")
        generated = secrets.token_hex(32)
        path.write_text(generated, encoding="utf-8")
        return generated.encode("utf-8")
    except OSError:
        return secrets.token_bytes(32)


SESSION_SECRET = _load_session_secret()


def _session_token(client_id: str) -> str:
    signature = hmac.new(SESSION_SECRET, client_id.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{client_id}.{signature}"


def _verify_session_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    client_id, signature = token.split(".", 1)
    if not SESSION_ID_RE.fullmatch(client_id):
        return None
    expected = hmac.new(SESSION_SECRET, client_id.encode("ascii"), hashlib.sha256).hexdigest()
    return client_id if hmac.compare_digest(signature, expected) else None


async def _prediction_sweeper_loop() -> None:
    while True:
        try:
            await resolve_due_predictions()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Prediction Sweeper Error: {type(exc).__name__}")
        await asyncio.sleep(PREDICTION_SWEEP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init_db()
    task = (
        asyncio.create_task(_prediction_sweeper_loop())
        if PREDICTION_SWEEPER_ENABLED
        else None
    )
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await AI_GATEWAY.close()


docs_enabled = os.getenv("OMNI_DISABLE_DOCS", "1") != "1"
app = FastAPI(
    title="AIONEX Strategy Engine",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
)


ERROR_TRANSLATIONS: dict[str, tuple[str, str]] = {
    "درخواست از حد مجاز بزرگ‌تر است.": ("The request exceeds the allowed size.", "request_too_large"),
    "تعداد درخواست‌های شفاف‌سازی بیش از حد مجاز است.": ("Too many clarification requests. Please wait briefly.", "intake_rate_limited"),
    "کمی صبر کنید و دوباره تلاش کنید.": ("Please wait briefly and try again.", "rate_limited"),
    "کمی صبر کنید.": ("Please wait briefly.", "rate_limited"),
    "جلسهٔ شفاف‌سازی پیدا نشد.": ("The clarification session was not found.", "intake_not_found"),
    "همین تحلیل در حال ساخته‌شدن است؛ چند لحظه بعد تاریخچه را باز کنید.": ("This analysis is already being generated. Open history again in a few moments.", "analysis_in_progress"),
    "سقف روزانهٔ تحلیل برای محافظت از هزینه تکمیل شده است.": ("The daily analysis budget has been reached to protect cost.", "analysis_budget_reached"),
    "تحلیل پیدا نشد.": ("The analysis was not found.", "analysis_not_found"),
    "پاسخ همین سؤال در حال ساخته‌شدن است.": ("An answer to this question is already being generated.", "chat_in_progress"),
    "سقف روزانهٔ گفت‌وگوی AI تکمیل شده است.": ("The daily AI conversation budget has been reached.", "chat_budget_reached"),
    "گام انتخاب‌شده پیدا نشد.": ("The selected step was not found.", "step_not_found"),
    "جزئیات این گام در حال ساخته‌شدن است.": ("The details for this step are already being generated.", "deep_dive_in_progress"),
    "سقف روزانهٔ جزئیات AI تکمیل شده است.": ("The daily AI deep-dive budget has been reached.", "deep_dive_budget_reached"),
    "انتقال Vault قدیمی فعال نیست.": ("Legacy vault transfer is not enabled.", "legacy_transfer_disabled"),
    "مجوز انتقال Vault نامعتبر است.": ("The legacy vault transfer credential is invalid.", "legacy_transfer_forbidden"),
    "هدف پیدا نشد.": ("The goal was not found.", "goal_not_found"),
}


def _request_locale(request: Request) -> Literal["fa", "en"]:
    """The product UI and API are English-only; user content may be multilingual."""
    return "en"


def _localized_message(request: Request, fa: str, en: str) -> str:
    return en


@app.exception_handler(HTTPException)
async def localized_http_exception(request: Request, exc: HTTPException):
    """Return stable error codes and localize route errors without a model call."""
    detail = exc.detail
    if isinstance(detail, str):
        english, code = ERROR_TRANSLATIONS.get(
            detail,
            (detail, f"http_{exc.status_code}"),
        )
        detail = {"code": code, "message": english}
    localized = HTTPException(status_code=exc.status_code, detail=detail, headers=exc.headers)
    return await http_exception_handler(request, localized)


def _request_too_large_response(request: Request) -> JSONResponse:
    return _secure_response(
        request,
        JSONResponse(
            status_code=HTTP_STATUS_CONTENT_TOO_LARGE,
            content={
                "status": "error",
                "code": "request_too_large",
                "message": "The request exceeds the allowed size.",
            },
        ),
    )


async def _buffer_bounded_request_body(request: Request) -> bool:
    """Cache a bounded mutation body and drain oversized chunked uploads.

    Draining after the limit is crossed prevents unread ASGI events from
    stalling the response, while clearing retained chunks keeps memory bounded.
    """
    chunks: list[bytes] = []
    received_bytes = 0
    too_large = False
    async for chunk in request.stream():
        received_bytes += len(chunk)
        if received_bytes > MAX_REQUEST_BYTES:
            too_large = True
            chunks.clear()
            continue
        if chunk and not too_large:
            chunks.append(chunk)
    if too_large:
        return False
    request._body = b"".join(chunks)
    return True


def _secure_response(request: Request, response: Any):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        # FastAPI's opt-in developer documentation is generated with inline
        # bootstrap code and CDN assets.  This relaxed policy is scoped only to
        # those routes; the product UI below keeps the strict self-only policy.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "font-src 'self' https://fonts.gstatic.com; connect-src 'self'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
            "script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'"
        )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def security_and_session_middleware(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex[:16]
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            parsed_content_length = int(content_length)
            if parsed_content_length < 0:
                raise ValueError
            if parsed_content_length > MAX_REQUEST_BYTES:
                return _request_too_large_response(request)
        except ValueError:
            return _secure_response(
                request,
                JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "code": "invalid_content_length",
                        "message": "Content-Length is invalid.",
                    },
                ),
            )

    session_path = request.url.path == "/" or request.url.path.startswith("/api/")
    client_id = _verify_session_token(request.cookies.get(SESSION_COOKIE))
    is_new = client_id is None and session_path
    if client_id is None:
        # Non-stateful static/404 requests receive no cookie and never create a
        # database client. Stateful store functions create the row on demand.
        client_id = uuid.uuid4().hex
    request.state.client_id = client_id

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if not await _buffer_bounded_request_body(request):
            return _request_too_large_response(request)

    response = await call_next(request)
    if is_new:
        response.set_cookie(
            SESSION_COOKIE,
            _session_token(client_id),
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    return _secure_response(request, response)


user_request_log = defaultdict(list)
deep_dive_request_log = defaultdict(list)


def _check_sliding_limit(log: dict[str, list[float]], key: str, maximum: int) -> bool:
    now = time.monotonic()
    recent = [stamp for stamp in log[key] if now - stamp < 60]
    if len(recent) >= maximum:
        log[key] = recent
        return False
    recent.append(now)
    log[key] = recent
    if len(log) > 10_000:
        stale = [item for item, stamps in log.items() if not stamps or now - stamps[-1] >= 60]
        for item in stale[:1000]:
            log.pop(item, None)
    return True


def _remote_id(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode("utf-8", errors="ignore")).hexdigest()[:20]


def check_rate_limit(client_id: str, remote_id: str) -> bool:
    client_allowed = _check_sliding_limit(user_request_log, f"client:{client_id}", 4)
    remote_allowed = _check_sliding_limit(user_request_log, f"remote:{remote_id}", 16)
    return client_allowed and remote_allowed


def check_deep_dive_rate_limit(client_id: str, remote_id: str) -> bool:
    client_allowed = _check_sliding_limit(deep_dive_request_log, f"client:{client_id}", 12)
    remote_allowed = _check_sliding_limit(deep_dive_request_log, f"remote:{remote_id}", 60)
    return client_allowed and remote_allowed


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EnglishProductRequest(StrictModel):
    """Accept the legacy locale field while enforcing English product output."""

    locale: Literal["en"] = "en"

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_product_locale(cls, value: Any) -> Any:
        if value is None or str(value).strip().casefold() in {"en", "fa"}:
            return "en"
        return value


class IntakeRequest(EnglishProductRequest):
    query: str = Field(min_length=8, max_length=3000)
    tier: Literal["B2C", "B2B"]
    horizon: Literal["instant", "strategic"] = "instant"


class QueryRequest(EnglishProductRequest):
    session_id: str = Field(min_length=32, max_length=32, pattern=r"^[a-f0-9]{32}$")
    answers: dict[str, Any] = Field(default_factory=dict)
    force_refresh: bool = False


class DeepDiveRequest(EnglishProductRequest):
    analysis_id: str = Field(min_length=8, max_length=64)
    step_id: str = Field(min_length=1, max_length=80)


class ChatRequest(EnglishProductRequest):
    analysis_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=2, max_length=2000)


class GoalFromAnalysisRequest(EnglishProductRequest):
    analysis_id: str = Field(min_length=8, max_length=64)


class ManualGoalRequest(EnglishProductRequest):
    tier: Literal["B2C", "B2B"] = "B2C"
    title: str = Field(min_length=3, max_length=160)
    target: str = Field(min_length=3, max_length=500)
    deadline: date | None = None
    weekly_time: str | None = Field(default=None, max_length=80)
    budget: str | None = Field(default=None, max_length=100)


class GoalUpdateRequest(StrictModel):
    progress: int | None = Field(default=None, ge=0, le=100)
    status: Literal["active", "paused", "completed", "archived"] | None = None
    next_check_in: str | None = Field(default=None, max_length=40)


class MemoryConfirmationRequest(StrictModel):
    tier: Literal["B2C", "B2B"]
    category: Literal["preference", "constraint", "resource", "skill", "goal"]
    content: str = Field(min_length=2, max_length=800)

# ════════════════════════════════════════════════════════════════
# ░░ OMNI-INGESTION PIPELINE ░░
# لولهٔ دریافت دادهٔ زنده: سه جریان مستقل (اقتصاد کلان، بازار/کالا، توجه/سنتیمنت)
# که با asyncio.gather به‌صورت کاملاً موازی و ناهمگام جمع‌آوری می‌شوند.
# هر جریان به‌صورت ایزوله شکست می‌خورد (Graceful Degradation): قطعیِ یک منبع،
# کل تحلیل را متوقف نمی‌کند؛ صرفاً سهم آن منبع از «پوشش داده» کم می‌شود.
# ════════════════════════════════════════════════════════════════

# پراکسی عبور از فایروال (در صورت تنظیم در محیط) برای محیط‌های محدودشده
OMNI_HTTP_PROXY = os.getenv("OMNI_HTTP_PROXY")

# سقف زمانی سخت‌گیرانه برای هر منبع تا یک منبع کند، کل خط لوله را گروگان نگیرد
INGEST_TIMEOUT = httpx.Timeout(6.0, connect=4.0)


def _utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def gather_market_intelligence(
    query: str = "",
    tier: Literal["B2C", "B2B"] = "B2C",
    horizon: str = "instant",
    routing_context: str | None = None,
) -> dict:
    """Stable test seam over the context-aware, local-only source router."""
    return await gather_free_intelligence(
        query=query,
        tier=tier,
        horizon=horizon,
        routing_context=routing_context or "",
    )


def _confidence_band(text):
    """اولین کلیدواژهٔ باندِ اطمینان (Low/Moderate/High) که در متن ظاهر شود را برمی‌گرداند."""
    t = (text or "").strip().lower()
    token = ""
    tokens = []
    for ch in t:
        if ch.isalpha():
            token += ch
        elif token:
            tokens.append(token)
            token = ""
    if token:
        tokens.append(token)
    for tok in tokens:
        if tok == "high":
            return "high"
        if tok in ("moderate", "medium"):
            return "moderate"
        if tok == "low":
            return "low"
    return "unknown"


# آستانه‌های شفاف گاردریل صداقت بر مبنای «منابع مستقل قابل‌استفاده ÷ منابع انتخاب‌شده».
# با رشد تعداد جریان‌ها، منطق دیگر همه‌یا‌هیچ نیست؛ نسبتی و پلکانی است. این دو عدد را
# آزادانه تنظیم کن: سخت‌گیرتر (مثلاً 0.90) یا نرم‌تر (مثلاً 0.66) بسته به ریسک‌پذیریت.
CONF_HIGH_MIN_RATIO = 0.80      # High فقط با پوششِ ~80٪+ مجاز است
CONF_MODERATE_MIN_RATIO = 0.50  # زیر ~50٪ پوشش، حتی Moderate هم به Low سقف می‌خورد


def _rank_band(band):
    """رتبهٔ عددیِ باند برای مقایسهٔ «آیا از سقفِ مجاز فراتر رفته؟»."""
    return {"low": 1, "moderate": 2, "high": 3}.get(band, 0)


def enforce_confidence_integrity(confidence, usable_source_count, selected_source_count):
    """
    گاردریلِ صداقت با نسبت پوشش و حداقل تعداد منبع مستقل.
      - High: دست‌کم ۳ منبع مستقل قابل‌استفاده و نسبت پوشش ≥ ۸۰٪.
      - Moderate: دست‌کم ۲ منبع مستقل قابل‌استفاده و نسبت پوشش ≥ ۵۰٪.
      - در غیر این صورت سقف Low است، حتی اگر تنها منبع موجود ۱۰۰٪ کامل باشد.
    این تنها تضمینِ واقعیِ صداقت است و به پیرویِ مدل از پرامپت اتکا نمی‌کند. تابع خالص می‌ماند
    تا کاملاً قابل‌تست باشد.
    """
    original = confidence if isinstance(confidence, str) else str(confidence or "")
    band = _confidence_band(original)
    try:
        usable = max(0, int(usable_source_count or 0))
    except (TypeError, ValueError, OverflowError):
        usable = 0
    try:
        total = max(0, int(selected_source_count or 0))
    except (TypeError, ValueError, OverflowError):
        total = 0
    usable = min(usable, total)
    ratio = (usable / total) if total else 0.0
    pct = round(ratio * 100)

    # A perfect ratio over one source is still thin external evidence.
    if usable >= 3 and ratio >= CONF_HIGH_MIN_RATIO:
        ceiling = "high"
    elif usable >= 2 and ratio >= CONF_MODERATE_MIN_RATIO:
        ceiling = "moderate"
    else:
        ceiling = "low"
    evidence_note = None
    if ceiling != "high":
        evidence_note = (
            "External evidence is limited: "
            f"{usable}/{total} independent usable sources ({pct}%), "
            f"so confidence cannot exceed {ceiling.capitalize()}."
        )

    if band in ("low", "moderate", "high") and _rank_band(band) > _rank_band(ceiling):
        enforced = ceiling.capitalize()
        note = (
            f"Confidence hard-capped to {enforced} by the integrity guardrail: "
            f"independent usable-source coverage is incomplete ({usable}/{total}, {pct}%). "
            f"At this coverage, '{band.capitalize()}' conviction is not permitted — "
            "not even in Long-Term Strategy mode."
        )
        return {
            "confidence": enforced,
            "capped": True,
            "note": note,
            "evidence_note": evidence_note,
            "original_confidence": original,
        }
    return {
        "confidence": original,
        "capped": False,
        "note": None,
        "evidence_note": evidence_note,
        "original_confidence": original,
    }


def _usable_independent_source_count(intelligence: dict[str, Any]) -> int:
    """Count usable evidence providers once, even when one provider has many streams."""
    if not isinstance(intelligence, dict):
        return 0
    providers: set[str] = set()
    for stream in intelligence.get("streams") or []:
        if not isinstance(stream, dict):
            continue
        if str(stream.get("status") or "degraded").casefold() == "degraded":
            continue
        if not str(stream.get("summary") or "").strip():
            continue
        source_url = str(stream.get("source_url") or "").strip()
        hostname = urlsplit(source_url).hostname if source_url else None
        identity = (hostname or str(stream.get("source") or "").strip()).casefold()
        if identity.startswith("www."):
            identity = identity[4:]
        if not identity:
            identity = str(stream.get("key") or "").strip().casefold()
        if identity:
            providers.add(identity)
    return len(providers)


# ════════════════════════════════════════════════════════════════
# ░░ CALIBRATION ENGINE ░░ — حلقهٔ نمره‌دهیِ مکانیکیِ پیش‌بینی‌ها.
# سیستم در لحظهٔ تولدِ هر سیگنال، چند «پیش‌بینیِ افتادنیِ قابلِ‌سنجش» تولید می‌کند که
# به متریک‌هایی گره خورده‌اند که خط‌لوله همین حالا می‌خوانَد. baseline از همان snapshotِ
# زنده ثبت می‌شود (نه از مدل). بعداً یک resolver، مقدارِ واقعیِ فعلی را می‌گیرد و نتیجه را
# کاملاً مکانیکی (بدونِ قضاوتِ هوش مصنوعی) تعیین می‌کند. این تنها راهِ صادقانهٔ اثباتِ نرخِ بُرد است.
# ════════════════════════════════════════════════════════════════

# متریک‌های مجاز برای پیش‌بینی — دقیقاً همان‌هایی که خط‌لوله می‌خوانَد (پس baseline و حل، رایگان و عینی است).
METRIC_KEYS = ["eur_usd", "btc", "eth", "gold_cg", "us10y", "vix", "dxy", "brent", "copper", "gold"]

METRIC_LABELS = {
    "eur_usd": "EUR/USD", "btc": "BTC", "eth": "ETH", "gold_cg": "Gold (PAXG proxy)",
    "us10y": "US 10Y Yield", "vix": "VIX", "dxy": "Dollar Index",
    "brent": "Brent Crude", "copper": "Copper", "gold": "Gold (futures)",
}

# Metrics that can be resolved through the opt-in CoinGecko request.
CG_METRIC_KEYS = {"btc", "eth", "gold_cg"}


async def append_predictions(records, client_id: str, analysis_id: str | None = None):
    """Persist predictions transactionally in the user-scoped SQLite store."""
    await asyncio.to_thread(store.append_predictions, records, client_id, analysis_id)


def extract_metric_baseline(intel, metric_key):
    """
    مقدارِ پایهٔ یک متریک را مستقیماً از snapshotِ زندهٔ همان لحظه بیرون می‌کشد (نه از مدل).
    اگر جریانِ مربوطه زنده نباشد، (None, None) برمی‌گرداند تا آن پیش‌بینی صادقانه رد شود.
    """
    streams = {s.get("key"): s for s in (intel.get("streams") or [])
               if isinstance(s, dict) and s.get("status") == "live"}

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    if metric_key == "eur_usd":
        s = streams.get("macro")
        if s:
            v = num((s.get("metrics") or {}).get("eur_usd_spot"))
            if v is not None:
                return v, "Frankfurter (ECB)"
        s = streams.get("ecb_fx")
        if s:
            v = num((s.get("metrics") or {}).get("eur_usd_reference"))
            if v is not None:
                return v, "European Central Bank"
    elif metric_key in CG_METRIC_KEYS:
        s = streams.get("markets")
        if s:
            node = {"btc": "btc", "eth": "eth", "gold_cg": "gold_proxy_paxg"}[metric_key]
            v = num(((s.get("metrics") or {}).get(node) or {}).get("usd"))
            if v is not None:
                return v, "CoinGecko"
    return None, None


def build_predictions_from_ai(ai_data, intel, original_query: str, tier: str):
    """
    پیش‌بینی‌های خامِ مدل را اعتبارسنجی می‌کند و رکوردهای سرور-معتبر می‌سازد:
    متریکِ مجاز، جهتِ up/down، افقِ ۳ تا ۴۵ روز، و baselineِ گرفته‌شده از snapshotِ زنده.
    هر موردی که قابلِ baseline‌گیریِ صادقانه نباشد، رد می‌شود.
    """
    raw = ai_data.get("predictions")
    out = []
    if not isinstance(raw, list):
        return out
    band_token = _confidence_band(ai_data.get("confidence")) or "unknown"
    now = datetime.now(timezone.utc)
    seen_metrics = set()
    for item in raw[:3]:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric", "")).strip().lower()
        direction = str(item.get("direction", "")).strip().lower()
        if metric not in METRIC_KEYS or direction not in ("up", "down") or metric in seen_metrics:
            continue
        try:
            hd = int(item.get("horizon_days"))
        except (TypeError, ValueError):
            hd = 14
        hd = max(3, min(45, hd))
        base, src = extract_metric_baseline(intel, metric)
        if base is None:
            continue
        seen_metrics.add(metric)
        out.append({
            "id": uuid.uuid4().hex,
            "created_at": _utc_stamp(),
            "resolve_at": (now + timedelta(days=hd)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "metric": metric,
            "metric_label": METRIC_LABELS.get(metric, metric),
            "direction": direction,
            "horizon_days": hd,
            "baseline_value": round(float(base), 6),
            "baseline_source": src,
            "rationale": item.get("rationale") or "",
            "invalidation_condition": item.get("invalidation_condition") or "",
            "status": "pending",
            "signal_name": ai_data.get("signal_name"),
            "original_query": original_query,
            "tier": tier,
            "horizon_mode": ai_data.get("horizon_mode"),
            "confidence": ai_data.get("confidence"),
            "confidence_band": band_token,
            "data_coverage": ai_data.get("data_coverage"),
            "lang_dir": ai_data.get("lang_dir"),
        })
    return out


async def _current_eur_usd(http):
    """آخرین EUR/USD از Frankfurter (برای حل‌وفصل)."""
    r = await http.get("https://api.frankfurter.app/latest",
                       params={"from": "EUR", "to": "USD"})
    r.raise_for_status()
    return float(r.json()["rates"]["USD"])


async def _current_coingecko(http):
    """آخرین قیمتِ BTC/ETH/PAXG از CoinGecko (یک فراخوانی برای هر سه)."""
    r = await http.get("https://api.coingecko.com/api/v3/simple/price",
                       params={"ids": "bitcoin,ethereum,pax-gold", "vs_currencies": "usd"})
    r.raise_for_status()
    j = r.json()
    return {"btc": j.get("bitcoin", {}).get("usd"),
            "eth": j.get("ethereum", {}).get("usd"),
            "gold_cg": j.get("pax-gold", {}).get("usd")}


async def fetch_current_metric_values(metric_keys) -> dict:
    """
    Resolve supported metrics only when outbound prediction networking is enabled.

    Metrics without an approved resolver remain ``None`` instead of triggering
    an undocumented background request.
    """
    keys = set(k for k in metric_keys if k in METRIC_KEYS)
    out = {k: None for k in keys}
    if not keys or not PREDICTION_NETWORK_ENABLED:
        return out
    if "eur_usd" not in keys and not (keys & CG_METRIC_KEYS):
        return out
    order = []
    coros = []
    async with httpx.AsyncClient(timeout=INGEST_TIMEOUT, proxy=OMNI_HTTP_PROXY or None,
                                 follow_redirects=True,
                                 headers={"User-Agent": "AIONEX-Decision-Intelligence/3.0"}) as http:
        if "eur_usd" in keys:
            order.append(("eur_usd", "single"))
            coros.append(_current_eur_usd(http))
        if keys & CG_METRIC_KEYS:
            order.append(("__cg__", "cg"))
            coros.append(_current_coingecko(http))
        results = await asyncio.gather(*coros, return_exceptions=True)
    for (key, kind), res in zip(order, results):
        if isinstance(res, Exception):
            continue
        if kind == "cg":
            if isinstance(res, dict):
                for mk in CG_METRIC_KEYS:
                    if mk in keys and res.get(mk) is not None:
                        try:
                            out[mk] = float(res[mk])
                        except (TypeError, ValueError):
                            pass
        else:
            if res is not None:
                try:
                    out[key] = float(res)
                except (TypeError, ValueError):
                    pass
    return out


def _is_due(pred, now_dt):
    """آیا زمانِ سررسیدِ یک پیش‌بینی فرا رسیده؟"""
    ra = pred.get("resolve_at")
    if not ra:
        return False
    try:
        dt = datetime.strptime(ra, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return now_dt >= dt


def _resolve_one(pred, current_value):
    """
    خالص و مکانیکی: یک پیش‌بینیِ سررسید‌شده را با مقدارِ واقعیِ فعلی می‌سنجد.
    حرکتِ کمتر از ~۰٫۰۵٪ «flat» شمرده می‌شود و از نرخِ بُرد کنار می‌رود (انصاف).
    اگر فعلاً قابلِ حل نباشد (baseline/مقدار غایب)، None برمی‌گرداند تا pending بماند.
    """
    base = pred.get("baseline_value")
    if base is None or current_value is None:
        return None
    try:
        base = float(base)
        cur = float(current_value)
    except (TypeError, ValueError):
        return None
    if base == 0:
        return None
    move_pct = (cur - base) / base * 100.0
    direction = pred.get("direction")
    # A single universal epsilon made a 0.06% BTC move and a 0.06% FX move
    # equally meaningful.  Use conservative, metric-aware noise bands instead.
    FLAT_EPS_BY_METRIC = {
        "eur_usd": 0.05, "btc": 0.30, "eth": 0.35, "gold_cg": 0.15,
        "us10y": 0.20, "vix": 0.50, "dxy": 0.08,
        "brent": 0.25, "copper": 0.20, "gold": 0.15,
    }
    flat_eps = FLAT_EPS_BY_METRIC.get(str(pred.get("metric")), 0.10)
    if abs(move_pct) < flat_eps:
        outcome = "flat"
    elif direction == "up":
        outcome = "correct" if cur > base else "incorrect"
    elif direction == "down":
        outcome = "correct" if cur < base else "incorrect"
    else:
        return None
    return {"status": outcome, "resolved_value": round(cur, 6),
            "move_pct": round(move_pct, 3), "resolved_at": _utc_stamp()}


async def resolve_due_predictions() -> dict:
    """
    همهٔ پیش‌بینی‌های سررسید‌شدهٔ pending را با دادهٔ واقعیِ فعلی حل می‌کند.
    شبکه را بیرونِ قفل می‌زند و پیش از نوشتن، فایل را دوباره می‌خواند تا با append همزمان تداخل نکند.
    """
    now = datetime.now(timezone.utc)
    due = await asyncio.to_thread(store.list_predictions, None, 1000, _utc_stamp())
    if not due:
        return {
            "resolved": 0,
            "checked": 0,
            "network_enabled": PREDICTION_NETWORK_ENABLED,
        }
    if not PREDICTION_NETWORK_ENABLED:
        return {
            "resolved": 0,
            "checked": len(due),
            "network_enabled": False,
            "reason": "offline" if OFFLINE_MODE else "network_not_enabled",
        }
    metric_keys = {p.get("metric") for p in due if p.get("metric")}
    currents = await fetch_current_metric_values(metric_keys)
    resolved = 0
    for target in due:
        result = _resolve_one(target, currents.get(target.get("metric")))
        if result is None:
            continue
        target.update(result)
        target["resolution_lag_seconds"] = max(
            0,
            int((now - datetime.strptime(target["resolve_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()),
        )
        if await asyncio.to_thread(store.update_prediction, target):
            resolved += 1
    return {
        "resolved": resolved,
        "checked": len(due),
        "network_enabled": True,
    }


def _winrate(b):
    """نرخِ بُرد = درست ÷ (درست + غلط)؛ flat و pending در مخرج نمی‌آیند. اگر مخرج صفر بود، None."""
    decided = b.get("correct", 0) + b.get("incorrect", 0)
    return round(b["correct"] / decided * 100, 1) if decided else None


def compute_calibration(preds):
    """
    خالص: از روی پیش‌بینی‌ها، کارنامهٔ واقعی را می‌سازد — کلی، به‌تفکیکِ باندِ اطمینان، و به‌تفکیکِ متریک.
    «نرخِ بُرد به‌تفکیکِ باند» مهم‌ترین عدد است: آیا وقتی High می‌گوییم، واقعاً بیشتر درست بوده‌ایم؟
    """
    def blank():
        return {"correct": 0, "incorrect": 0, "flat": 0, "pending": 0}

    overall = blank()
    by_band = {"High": blank(), "Moderate": blank(), "Low": blank()}
    by_metric = {}
    band_map = {"high": "High", "moderate": "Moderate", "low": "Low"}

    for p in preds:
        st = p.get("status", "pending")
        if st not in ("correct", "incorrect", "flat", "pending"):
            st = "pending"
        overall[st] += 1

        band_raw = p.get("confidence_band") or _confidence_band(p.get("confidence"))
        band = band_map.get(band_raw)
        if band:
            by_band[band][st] += 1

        mk = p.get("metric")
        if mk:
            if mk not in by_metric:
                by_metric[mk] = blank()
                by_metric[mk]["label"] = p.get("metric_label", mk)
            by_metric[mk][st] += 1

    resolved = overall["correct"] + overall["incorrect"] + overall["flat"]
    result = {
        "total": len(preds),
        "resolved": resolved,
        "pending": overall["pending"],
        "correct": overall["correct"],
        "incorrect": overall["incorrect"],
        "flat": overall["flat"],
        "win_rate": _winrate(overall),
        "by_band": {},
        "by_metric": {},
        "generated_at": _utc_stamp(),
    }
    for band, b in by_band.items():
        result["by_band"][band] = {
            "correct": b["correct"], "incorrect": b["incorrect"],
            "flat": b["flat"], "pending": b["pending"], "win_rate": _winrate(b),
        }
    for mk, b in by_metric.items():
        result["by_metric"][mk] = {
            "label": b.get("label", mk),
            "correct": b["correct"], "incorrect": b["incorrect"],
            "flat": b["flat"], "pending": b["pending"], "win_rate": _winrate(b),
        }
    return result


class ApiEnvelope(StrictModel):
    status: Literal["success", "error"]
    data: Any | None = None
    message: str | None = None
    intelligence: dict[str, Any] | None = None
    cached: bool | None = None


def _client_id(request: Request) -> str:
    return request.state.client_id


def _answer_labels(questions: list[dict[str, Any]], answers: dict[str, str]) -> dict[str, str]:
    labeled: dict[str, str] = {}
    by_id = {question.get("id"): question for question in questions}
    for key, value in answers.items():
        question = by_id.get(key) or {}
        option = next(
            (item for item in question.get("options", []) if str(item.get("value")) == value),
            None,
        )
        if value == "unknown":
            translations = question.get("translations") or {}
            english = translations.get("en") if isinstance(translations, dict) else {}
            labeled[key] = str(
                (english or {}).get("unknown_label")
                if isinstance(english, dict)
                else ""
            ) or "Not sure yet; validation is required"
        else:
            translations = option.get("translations") if isinstance(option, dict) else {}
            english_label = (
                translations.get("en") if isinstance(translations, dict) else None
            )
            labeled[key] = str(english_label or option.get("label")) if option else value
    return labeled


def _memory_entries(memory: dict[str, Any]) -> list[dict[str, str]]:
    facts = memory.get("facts") if isinstance(memory, dict) else {}
    fact_entries = [
        {"category": str(key)[:64], "content": str(value)[:400]}
        for key, value in list(facts.items())[-12:]
    ] if isinstance(facts, dict) else []
    contexts = memory.get("recent_contexts") if isinstance(memory, dict) else []
    context_entries = [
        {"category": "recent_context", "content": str(value)[:300]}
        for value in list(contexts)[-3:]
        if str(value).strip()
    ] if isinstance(contexts, list) else []
    return (fact_entries + context_entries)[-15:]


def _bounded_context_text(value: Any, limit: int) -> str:
    """Normalize user-owned context without changing its meaning."""
    return " ".join(str(value or "").replace("\x00", " ").split())[:limit]


def _decision_context(
    query: str,
    answers: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
    *,
    current_message: str | None = None,
    selected_step: Any | None = None,
) -> str:
    """Build bounded local routing/resource context from already-known facts."""
    sections = [f"Original request: {_bounded_context_text(query, 1_500)}"]
    if isinstance(answers, dict) and answers:
        answer_lines = [
            f"{_bounded_context_text(key, 80)}={_bounded_context_text(value, 300)}"
            for key, value in list(answers.items())[-20:]
            if _bounded_context_text(value, 300)
        ]
        if answer_lines:
            sections.append("Clarification answers: " + "; ".join(answer_lines))
    facts = memory.get("facts") if isinstance(memory, dict) else {}
    if isinstance(facts, dict) and facts:
        fact_lines = [
            f"{_bounded_context_text(key, 80)}={_bounded_context_text(value, 300)}"
            for key, value in list(facts.items())[-24:]
            if _bounded_context_text(value, 300)
        ]
        if fact_lines:
            sections.append("Remembered facts: " + "; ".join(fact_lines))
    if current_message:
        sections.append(
            f"Current follow-up: {_bounded_context_text(current_message, 1_000)}"
        )
    if selected_step:
        if isinstance(selected_step, dict):
            step_text = " ".join(
                _bounded_context_text(selected_step.get(key), 400)
                for key in ("title", "objective", "success_metric")
                if selected_step.get(key)
            )
        else:
            step_text = _bounded_context_text(selected_step, 1_000)
        if step_text:
            sections.append(f"Selected step: {step_text}")
    return "\n".join(sections)[:6_000]


async def _gather_with_context(
    query: str,
    tier: Literal["B2C", "B2B"],
    horizon: str,
    routing_context: str,
) -> dict[str, Any]:
    """Send bounded intake/memory context only to the local source router."""
    return await gather_market_intelligence(
        query=query,
        tier=tier,
        horizon=horizon,
        routing_context=routing_context,
    )


def _compact_history_for_ai(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Keep conversational continuity without replaying stored metadata."""
    return [
        {
            "role": str(item.get("role") or "")[:16],
            "content": str(item.get("content") or "")[:1_200],
        }
        for item in history[-8:]
        if isinstance(item, dict) and item.get("content")
    ]


def _compact_strategy_for_ai(data: dict[str, Any]) -> dict[str, Any]:
    """Bound follow-up context and exclude UI-only execution enrichment."""
    if not isinstance(data, dict):
        return {}

    def text(key: str, limit: int) -> str:
        return str(data.get(key) or "")[:limit]

    steps = []
    for raw in (data.get("action_steps") or [])[:6]:
        if not isinstance(raw, dict):
            continue
        steps.append(
            {
                "step_id": str(raw.get("step_id") or "")[:80],
                "sequence": raw.get("sequence"),
                "title": str(raw.get("title") or "")[:240],
                "objective": str(raw.get("objective") or "")[:500],
                "timebox": str(raw.get("timebox") or "")[:80],
                "estimated_cost": str(raw.get("estimated_cost") or "")[:80],
                "success_metric": str(raw.get("success_metric") or "")[:500],
            }
        )
    evidence = []
    for raw in (data.get("evidence") or [])[:5]:
        if isinstance(raw, dict):
            evidence.append(
                {
                    "source_key": str(raw.get("source_key") or "")[:80],
                    "observation": str(raw.get("observation") or "")[:500],
                    "relevance": str(raw.get("relevance") or "")[:400],
                    "limitation": str(raw.get("limitation") or "")[:300],
                }
            )
    blueprint = data.get("goal_blueprint") or {}
    goal = {}
    if isinstance(blueprint, dict):
        goal = {
            key: blueprint.get(key)
            for key in (
                "goal_title",
                "desired_outcome",
                "target_metric",
                "target_value",
                "deadline",
                "capital_ceiling",
                "loss_ceiling",
                "weekly_time_commitment",
                "review_cadence",
                "stop_conditions",
            )
            if blueprint.get(key)
        }
        goal["milestones"] = [
            {
                key: item.get(key)
                for key in ("title", "due_window", "target_metric")
                if item.get(key)
            }
            for item in (blueprint.get("milestones") or [])[:4]
            if isinstance(item, dict)
        ]
    risk_raw = data.get("risk_assessment") or {}
    risk = {}
    if isinstance(risk_raw, dict):
        risk = {
            key: risk_raw.get(key)
            for key in (
                "overall_level",
                "capital_at_risk",
                "worst_case",
                "legal_compliance_note",
                "stop_conditions",
            )
            if risk_raw.get(key)
        }
        risk["key_risks"] = [
            {
                key: item.get(key)
                for key in ("risk", "early_warning", "mitigation")
                if item.get(key)
            }
            for item in (risk_raw.get("key_risks") or [])[:3]
            if isinstance(item, dict)
        ]
    audience_detail = {
        key: data.get(key)
        for key in (
            "personalized_fit",
            "first_revenue_path",
            "decision_statement",
            "organization_fit",
            "financial_case",
        )
        if data.get(key)
    }
    return {
        "audience": data.get("audience") or data.get("tier"),
        "horizon_mode": data.get("horizon_mode"),
        "signal_name": text("signal_name", 240),
        "executive_summary": text("executive_summary", 1_500),
        "root_cause": text("root_cause", 1_200),
        "confidence": data.get("confidence"),
        "confidence_reason": text("confidence_reason", 500),
        "assumptions": [str(item)[:400] for item in (data.get("assumptions") or [])[:5]],
        "data_gaps": [str(item)[:400] for item in (data.get("data_gaps") or [])[:5]],
        "evidence": evidence,
        "action_steps": steps,
        "goal": goal,
        "risk": risk,
        "audience_detail": audience_detail,
    }


def _without_execution_kit(data: dict[str, Any]) -> dict[str, Any]:
    """Keep deterministic response-time enrichment out of persistent payloads."""
    clean = dict(data) if isinstance(data, dict) else {}
    clean.pop("execution_kit", None)
    return clean


def _with_execution_kit(
    data: dict[str, Any],
    context: str,
    tier: Literal["B2C", "B2B"],
    locale: Literal["fa", "en"],
    action_steps: list[Any] | None = None,
    *,
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Always rebuild trusted local enrichment for the current response locale."""
    enriched = _without_execution_kit(data)
    steps = action_steps if action_steps is not None else enriched.get("action_steps") or []
    enriched["execution_kit"] = build_execution_kit(
        context,
        tier,
        action_steps=steps,
        context=context,
        facts=facts,
        locale=locale,
    )
    return enriched


def _chat_actions(data: dict[str, Any]) -> list[Any]:
    message = data.get("message") if isinstance(data, dict) else {}
    metadata = message.get("metadata") if isinstance(message, dict) else {}
    actions = metadata.get("recommended_actions") if isinstance(metadata, dict) else []
    return actions if isinstance(actions, list) else []


def _vault_intelligence_summary(intelligence: dict[str, Any]) -> dict[str, Any]:
    """Retain the source-card contract while omitting bulky raw metrics/catalogs."""
    if not isinstance(intelligence, dict):
        return {}
    summary = {
        key: intelligence.get(key)
        for key in (
            "coverage_live",
            "coverage_total",
            "coverage_label",
            "captured_at",
            "cache_status",
            "routing_tags",
            "selected_source_count",
            "available_source_count",
            "layer_count",
            "all_external_apis_free",
            "external_api_cost_usd",
        )
        if intelligence.get(key) is not None
    }
    summary["streams"] = [
        {
            key: stream.get(key)
            for key in (
                "key",
                "label",
                "layer",
                "status",
                "completeness",
                "source",
                "as_of",
                "summary",
                "authority",
                "quality",
            )
            if stream.get(key) is not None
        }
        for stream in (intelligence.get("streams") or [])
        if isinstance(stream, dict)
    ]
    return summary


def _vault_analysis_summary(row: dict[str, Any], locale: Literal["fa", "en"]) -> dict[str, Any]:
    """Return only fields needed to render/filter one Vault list row."""
    analysis = row.get("data") if isinstance(row.get("data"), dict) else {}
    analysis_id = str(row.get("id") or analysis.get("analysis_id") or "")[:64]
    tier = str(row.get("tier") or analysis.get("tier") or analysis.get("audience") or "B2C")
    created_at = row.get("created_at") or analysis.get("created_at")
    return {
        "analysis_id": analysis_id,
        "signal_name": str(analysis.get("signal_name") or analysis.get("title") or "")[:240],
        "original_query": str(row.get("query") or analysis.get("original_query") or "")[:3_000],
        "tier": "B2B" if tier == "B2B" else "B2C",
        "horizon_mode": str(row.get("horizon") or analysis.get("horizon_mode") or "instant")[:24],
        "confidence": str(analysis.get("confidence") or "")[:40],
        "lang_dir": "ltr" if analysis.get("lang_dir") == "ltr" else "rtl",
        "created_at": created_at,
        "timestamp": created_at,
        "response_locale": locale,
        "intelligence_snapshot": _vault_intelligence_summary(row.get("intelligence") or {}),
        "detail_available": bool(analysis_id),
        "summary_version": 1,
    }


async def _record_ai_result(client_id: str, result: Any) -> None:
    usage = result.usage
    await asyncio.to_thread(
        store.record_usage,
        client_id,
        result.operation,
        result.model,
        usage.input_tokens,
        usage.output_tokens,
        result.demo_mode,
    )


async def _record_ai_failure(client_id: str, endpoint: str, model: str, exc: OmniAIError) -> None:
    """Count provider responses that include usage, even when parsing later fails."""
    if exc.usage is None:
        return
    await asyncio.to_thread(
        store.record_usage,
        client_id,
        endpoint,
        model,
        exc.usage.input_tokens,
        exc.usage.output_tokens,
        False,
    )


def _raise_ai_error(exc: OmniAIError) -> None:
    raise HTTPException(status_code=exc.http_status, detail=exc.public_dict()) from exc


def _fallback_goal_blueprint(
    data: dict[str, Any], locale: Literal["fa", "en"] = "en"
) -> dict[str, Any]:
    english = True
    copy = {
        "milestone": "Milestone" if english else "نقطهٔ عطف",
        "evidence_accepted": "Evidence accepted" if english else "شواهد پذیرفته شد",
        "week": "Week" if english else "هفته",
        "step_completed": (
            "Step completed with evidence"
            if english
            else "گام همراه با شواهد تکمیل شد"
        ),
        "staged_validation": "Staged validation" if english else "اعتبارسنجی مرحله‌ای",
        "measurable_evidence": (
            "One measurable piece of evidence"
            if english
            else "یک شاهد قابل‌اندازه‌گیری"
        ),
        "actual_result": (
            "The actual result and data are recorded."
            if english
            else "نتیجه و دادهٔ واقعی ثبت شده باشد."
        ),
        "new_goal": "New goal" if english else "هدف جدید",
        "execute_plan": "Execute the plan" if english else "اجرای برنامه",
        "target_metric": (
            "Complete milestones with real evidence"
            if english
            else "تکمیل milestoneها با شواهد واقعی"
        ),
        "target_value": (
            "100% of verified milestones"
            if english
            else "۱۰۰٪ milestoneهای تأییدشده"
        ),
        "deadline": "90 days" if english else "۹۰ روز",
        "capital_ceiling": (
            "According to the analysis constraints"
            if english
            else "مطابق محدودیت تحلیل"
        ),
        "loss_ceiling": (
            "Stop at the first invalidation condition"
            if english
            else "توقف در اولین شرط ابطال"
        ),
        "weekly_time": (
            "According to the user's intake"
            if english
            else "مطابق intake کاربر"
        ),
        "review_cadence": "Weekly" if english else "هفتگی",
        "weekly_progress": "Weekly progress" if english else "پیشرفت هفتگی",
        "validation_evidence": (
            "Validation evidence" if english else "شاهد اعتبارسنجی"
        ),
        "loss_stop": "Loss ceiling breached" if english else "نقض سقف زیان",
        "assumption_stop": (
            "Core assumption rejected" if english else "رد شدن فرض اصلی"
        ),
    }
    steps = data.get("action_steps") if isinstance(data.get("action_steps"), list) else []
    milestones = []
    for index, step in enumerate(steps[:6], start=1):
        if isinstance(step, dict):
            title = str(
                step.get("title")
                or step.get("objective")
                or f"{copy['milestone']} {index}"
            )
            metric = str(step.get("success_metric") or copy["evidence_accepted"])
            due = str(step.get("timebox") or f"{copy['week']} {index}")
        else:
            title = str(step)
            metric = copy["step_completed"]
            due = f"{copy['week']} {index}"
        milestones.append(
            {
                "milestone_id": f"m{index}", "sequence": index, "title": title,
                "due_window": due, "target_metric": metric, "completion_evidence": metric,
            }
        )
    while len(milestones) < 2:
        index = len(milestones) + 1
        milestones.append(
            {
                "milestone_id": f"m{index}", "sequence": index,
                "title": copy["staged_validation"],
                "due_window": f"{copy['week']} {index}",
                "target_metric": copy["measurable_evidence"],
                "completion_evidence": copy["actual_result"],
            }
        )
    return {
        "goal_title": str(data.get("signal_name") or copy["new_goal"]),
        "desired_outcome": str(
            data.get("executive_summary")
            or data.get("root_cause")
            or copy["execute_plan"]
        ),
        "target_metric": copy["target_metric"],
        "target_value": copy["target_value"],
        "deadline": copy["deadline"],
        "capital_ceiling": copy["capital_ceiling"],
        "loss_ceiling": copy["loss_ceiling"],
        "weekly_time_commitment": copy["weekly_time"],
        "review_cadence": copy["review_cadence"],
        "milestones": milestones,
        "leading_indicators": [copy["weekly_progress"], copy["validation_evidence"]],
        "stop_conditions": [copy["loss_stop"], copy["assumption_stop"]],
    }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def v2_read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/health", response_model=ApiEnvelope)
async def health_check():
    provider_configured = bool(
        os.getenv(AI_GATEWAY.settings.api_key_env_name, "").strip()
    )
    ai_ready = AI_GATEWAY.settings.demo_mode or provider_configured
    storage_health = await asyncio.to_thread(store.storage_health)
    ready = bool(storage_health.get("ready")) and ai_ready
    return {
        "status": "success",
        "data": {
            "service": "aionex",
            "version": "3.0.0",
            "operational_status": "ready" if ready else "degraded",
            "ready": ready,
            "storage_ready": bool(storage_health.get("ready")),
            "ai_ready": ai_ready,
            "ai_provider_configured": provider_configured,
            "generation_mode": (
                "demo"
                if AI_GATEWAY.settings.demo_mode
                else "provider" if provider_configured else "unavailable"
            ),
            "demo_mode": AI_GATEWAY.settings.demo_mode,
            "offline_mode": OFFLINE_MODE,
            "prediction_resolution": {
                "network_enabled": PREDICTION_NETWORK_ENABLED,
                "sweeper_enabled": PREDICTION_SWEEPER_ENABLED,
            },
        },
    }


@app.post("/api/intake", response_model=ApiEnvelope)
async def create_intake(payload: IntakeRequest, request: Request):
    client_id = _client_id(request)
    if not check_deep_dive_rate_limit(f"intake:{client_id}", _remote_id(request)):
        raise HTTPException(status_code=429, detail="تعداد درخواست‌های شفاف‌سازی بیش از حد مجاز است.", headers={"Retry-After": "60"})
    await asyncio.to_thread(store.ensure_client, client_id, payload.locale)
    profile = await asyncio.to_thread(store.get_profile, client_id, payload.tier)
    questions, extracted = build_questions(
        payload.query,
        payload.tier,
        payload.horizon,
        profile.get("memory") or {},
        locale=payload.locale,
    )
    session = await asyncio.to_thread(
        store.create_intake_session,
        client_id,
        payload.tier,
        payload.horizon,
        payload.query,
        questions,
    )
    remembered = (profile.get("memory") or {}).get("facts") or {}
    known = {**remembered, **extracted}
    return {
        "status": "success",
        "data": {
            "session_id": session["id"],
            "phase": "clarifying" if questions else "ready",
            "questions": questions,
            "known_facts": extracted,
            "memory_used": known,
            "locale": payload.locale,
            "model_calls": 0,
        },
    }


@app.post("/api/analyze", response_model=ApiEnvelope)
async def v2_analyze(payload: QueryRequest, request: Request):
    client_id = _client_id(request)
    await asyncio.to_thread(store.ensure_client, client_id, payload.locale)
    if not check_rate_limit(client_id, _remote_id(request)):
        raise HTTPException(status_code=429, detail="کمی صبر کنید و دوباره تلاش کنید.", headers={"Retry-After": "60"})
    session = await asyncio.to_thread(store.get_intake_session, payload.session_id, client_id)
    if not session:
        raise HTTPException(status_code=404, detail="جلسهٔ شفاف‌سازی پیدا نشد.")
    try:
        cleaned = validate_answers(session["questions"], payload.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    answers = _answer_labels(session["questions"], cleaned)
    await asyncio.to_thread(store.complete_intake_session, payload.session_id, client_id, answers)

    profile = await asyncio.to_thread(store.get_profile, client_id, session["tier"])
    stored_memory = profile.get("memory") or {}
    extracted = extract_facts_from_query(session["query"], session["tier"])
    memory_answers = {
        key: value for key, value in answers.items() if cleaned.get(key) != "unknown"
    }
    merged_facts = {**extracted, **memory_answers}
    # Current intake facts are valid context for this analysis, but they are
    # not durable profile memory. Only the explicit /api/profile/memory route
    # may persist a user fact.
    stored_facts = (
        stored_memory.get("facts")
        if isinstance(stored_memory.get("facts"), dict)
        else {}
    )
    stored_contexts = (
        stored_memory.get("recent_contexts")
        if isinstance(stored_memory.get("recent_contexts"), list)
        else []
    )
    memory = {
        "facts": {**stored_facts, **merged_facts},
        "recent_contexts": list(stored_contexts),
    }
    decision_context = _decision_context(
        session["query"], answers, memory
    )
    kit_facts = {**(memory.get("facts") or {}), **answers}

    fingerprint_context: dict[str, Any] = {
        "facts": kit_facts,
        "recent_contexts": memory.get("recent_contexts") or [],
    }
    fingerprint_context["locale"] = "en"
    fingerprint = store.analysis_fingerprint(
        session["query"],
        session["tier"],
        session["horizon"],
        fingerprint_context,
    )
    if not payload.force_refresh:
        cached = await asyncio.to_thread(store.find_cached_analysis, client_id, fingerprint, 24)
        if cached:
            await asyncio.to_thread(store.record_usage, client_id, "analysis", "local-cache", 0, 0, True)
            return {
                "status": "success",
                "data": _with_execution_kit(
                    cached["data"],
                    decision_context,
                    session["tier"],
                    payload.locale,
                    facts=kit_facts,
                ),
                "intelligence": cached["intelligence"], "cached": True,
            }

    lease_id = await asyncio.to_thread(
        store.acquire_generation_lease,
        client_id,
        fingerprint,
        _generation_ttl_seconds(),
    )
    if not lease_id:
        cached = await asyncio.to_thread(store.find_cached_analysis, client_id, fingerprint, 24)
        if cached:
            await asyncio.to_thread(
                store.record_usage, client_id, "analysis", "local-cache", 0, 0, True
            )
            return {
                "status": "success",
                "data": _with_execution_kit(
                    cached["data"],
                    decision_context,
                    session["tier"],
                    payload.locale,
                    facts=kit_facts,
                ),
                "intelligence": cached["intelligence"], "cached": True,
            }
        raise HTTPException(
            status_code=409,
            detail="همین تحلیل در حال ساخته‌شدن است؛ چند لحظه بعد تاریخچه را باز کنید.",
            headers={"Retry-After": "5"},
        )

    reservation_id: str | None = None
    try:
        if not AI_GATEWAY.settings.demo_mode:
            reservation_id = await asyncio.to_thread(
                store.reserve_budget,
                client_id,
                "analysis",
                MAX_ANALYSES_PER_DAY,
                GLOBAL_MAX_ANALYSES_PER_DAY,
                24,
                _generation_ttl_seconds(),
            )
            if not reservation_id:
                raise HTTPException(
                    status_code=429,
                    detail="سقف روزانهٔ تحلیل برای محافظت از هزینه تکمیل شده است.",
                    headers={"Retry-After": "3600"},
                )
        intelligence = await _gather_with_context(
            query=session["query"],
            tier=session["tier"],
            horizon=session["horizon"],
            routing_context=decision_context,
        )
        ai_evidence = compact_intelligence_for_ai(intelligence)
        started = time.perf_counter()
        try:
            result = await AI_GATEWAY.analyze(
                query=session["query"],
                tier=session["tier"],
                horizon=session["horizon"],
                profile=memory.get("facts") or {},
                clarification_answers=answers,
                live_intelligence=ai_evidence,
                memory=_memory_entries(memory),
                current_date=datetime.now(timezone.utc).date(),
                language_hint="English (en, left-to-right)",
            )
        except OmniAIError as exc:
            await _record_ai_failure(
                client_id, "analysis", AI_GATEWAY.settings.analysis_model, exc
            )
            _raise_ai_error(exc)
        await _record_ai_result(client_id, result)
        ai_data = result.data.model_dump(mode="json")
        usable_source_count = _usable_independent_source_count(intelligence)
        selected_source_count = max(
            0,
            int(intelligence.get("selected_source_count") or intelligence.get("coverage_total") or 0),
        )
        integrity = enforce_confidence_integrity(
            ai_data.get("confidence"),
            usable_source_count,
            selected_source_count,
        )
        if integrity.get("evidence_note"):
            total = selected_source_count
            external_reason = (
                f"External evidence remains limited ({usable_source_count}/{total} independent usable sources); "
                f"the server therefore limits confidence to {integrity['confidence']} "
                "even when the user's own context is complete."
            )
            ai_data["confidence_reason"] = (
                f"{str(ai_data.get('confidence_reason') or '').strip()} {external_reason}"
            ).strip()[:1_200]
        ai_data.update(
            {
                "analysis_id": uuid.uuid4().hex,
                "original_query": session["query"],
                "tier": session["tier"],
                "horizon_mode": session["horizon"],
                "data_coverage": intelligence.get("coverage_label"),
                "confidence": integrity["confidence"],
                "confidence_capped": integrity["capped"],
                "confidence_note": integrity["note"],
                "confidence_original": integrity["original_confidence"],
                "usable_independent_source_count": usable_source_count,
                "selected_source_count": selected_source_count,
                "execution_time": f"{time.perf_counter() - started:.2f}s",
                "ai_meta": {
                    "model": result.model, "response_id": result.response_id,
                    "latency_ms": result.latency_ms, "demo_mode": result.demo_mode,
                },
            }
        )
        predictions = build_predictions_from_ai(
            ai_data, intelligence, session["query"], session["tier"]
        )
        ai_data["predictions"] = predictions
        stored_data = _without_execution_kit(ai_data)
        analysis_id = await asyncio.to_thread(
            store.save_analysis,
            client_id,
            payload.session_id,
            session["tier"],
            session["horizon"],
            session["query"],
            answers,
            stored_data,
            intelligence,
            fingerprint,
        )
        await append_predictions(predictions, client_id, analysis_id)
        return {
            "status": "success",
            "data": _with_execution_kit(
                stored_data,
                decision_context,
                session["tier"],
                payload.locale,
                facts=kit_facts,
            ),
            "intelligence": intelligence, "cached": False,
        }
    finally:
        if reservation_id:
            await asyncio.to_thread(store.release_budget, reservation_id, client_id)
        await asyncio.to_thread(
            store.release_generation_lease, client_id, fingerprint, lease_id
        )


@app.get("/api/analyses/{analysis_id}", response_model=ApiEnvelope)
async def get_analysis(analysis_id: str, request: Request):
    client_id = _client_id(request)
    row = await asyncio.to_thread(store.get_analysis, analysis_id, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="تحلیل پیدا نشد.")
    profile = await asyncio.to_thread(store.get_profile, client_id, row["tier"])
    facts = {
        **((profile.get("memory") or {}).get("facts") or {}),
        **(row.get("answers") or {}),
    }
    context = _decision_context(
        row["query"], row.get("answers") or {}, profile.get("memory") or {}
    )
    return {
        "status": "success",
        "data": _with_execution_kit(
            row["data"],
            context,
            row["tier"],
            _request_locale(request),
            facts=facts,
        ),
        "intelligence": row["intelligence"],
    }


@app.get("/api/analyses/{analysis_id}/messages", response_model=ApiEnvelope)
async def get_analysis_messages(analysis_id: str, request: Request):
    client_id = _client_id(request)
    if not await asyncio.to_thread(store.get_analysis, analysis_id, client_id):
        raise HTTPException(status_code=404, detail="تحلیل پیدا نشد.")
    messages = await asyncio.to_thread(store.list_messages, analysis_id, client_id, 30)
    return {"status": "success", "data": messages}


@app.post("/api/chat", response_model=ApiEnvelope)
async def chat_about_analysis(payload: ChatRequest, request: Request):
    client_id = _client_id(request)
    await asyncio.to_thread(store.ensure_client, client_id, payload.locale)
    if not check_deep_dive_rate_limit(f"chat:{client_id}", _remote_id(request)):
        raise HTTPException(status_code=429, detail="کمی صبر کنید.", headers={"Retry-After": "60"})
    analysis = await asyncio.to_thread(store.get_analysis, payload.analysis_id, client_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="تحلیل پیدا نشد.")

    history, goals, profile = await asyncio.gather(
        asyncio.to_thread(store.list_messages, payload.analysis_id, client_id, 10),
        asyncio.to_thread(store.list_goals, client_id, False),
        asyncio.to_thread(store.get_profile, client_id, analysis["tier"]),
    )
    related_goal = next(
        (goal for goal in goals if goal.get("analysis_id") == payload.analysis_id),
        None,
    )
    memory = profile.get("memory") or {}
    kit_facts = {**(memory.get("facts") or {}), **(analysis.get("answers") or {})}
    kit_context = _decision_context(
        analysis["query"],
        analysis.get("answers") or {},
        memory,
        current_message=payload.message,
    )
    normalized_message = " ".join(payload.message.casefold().split())
    history_for_key = history
    if (
        len(history) >= 2
        and history[-2].get("role") == "user"
        and history[-1].get("role") == "assistant"
        and " ".join(str(history[-2].get("content") or "").casefold().split())
        == normalized_message
    ):
        # Treat an immediate retry of the exact prior turn as idempotent. Other
        # conversation changes become part of the cache version below.
        history_for_key = history[:-2]
    context_version = "\0".join(
        f"{item.get('id')}:{item.get('role')}:{item.get('content')}"
        for item in history_for_key
    )
    if related_goal:
        context_version += (
            f"\0goal:{related_goal.get('id')}:{related_goal.get('updated_at')}:"
            f"{related_goal.get('progress')}:{related_goal.get('status')}"
        )
    context_version += f"\0profile:{profile.get('updated_at')}"
    locale_cache_token = "\0locale:en"
    cache_key = "chat:" + hashlib.sha256(
        f"{payload.analysis_id}\0{normalized_message}\0{context_version}{locale_cache_token}".encode("utf-8")
    ).hexdigest()
    cached = await asyncio.to_thread(store.get_deep_dive, cache_key)
    if cached:
        await asyncio.to_thread(store.record_usage, client_id, "chat", "local-cache", 0, 0, True)
        return {
            "status": "success",
            "data": _with_execution_kit(
                cached,
                kit_context,
                analysis["tier"],
                payload.locale,
                _chat_actions(cached),
                facts=kit_facts,
            ),
            "cached": True,
        }
    chat_lease_id = await asyncio.to_thread(
        store.acquire_generation_lease,
        client_id,
        cache_key,
        _generation_ttl_seconds(),
    )
    if not chat_lease_id:
        cached = await asyncio.to_thread(store.get_deep_dive, cache_key)
        if cached:
            await asyncio.to_thread(
                store.record_usage, client_id, "chat", "local-cache", 0, 0, True
            )
            return {
                "status": "success",
                "data": _with_execution_kit(
                    cached,
                    kit_context,
                    analysis["tier"],
                    payload.locale,
                    _chat_actions(cached),
                    facts=kit_facts,
                ),
                "cached": True,
            }
        raise HTTPException(status_code=409, detail="پاسخ همین سؤال در حال ساخته‌شدن است.")

    reservation_id: str | None = None
    try:
        if not AI_GATEWAY.settings.demo_mode:
            reservation_id = await asyncio.to_thread(
                store.reserve_budget,
                client_id,
                "chat",
                MAX_CHAT_MESSAGES_PER_DAY,
                GLOBAL_MAX_CHAT_MESSAGES_PER_DAY,
                24,
                _generation_ttl_seconds(),
            )
            if not reservation_id:
                raise HTTPException(status_code=429, detail="سقف روزانهٔ گفت‌وگوی AI تکمیل شده است.")
        try:
            result = await AI_GATEWAY.chat(
                user_message=payload.message,
                tier=analysis["tier"],
                horizon=analysis["horizon"],
                strategy=_compact_strategy_for_ai(analysis["data"]),
                history=_compact_history_for_ai(history),
                memory=_memory_entries(memory),
                goal=related_goal or {},
                live_intelligence=compact_intelligence_for_ai(
                    analysis["intelligence"]
                ),
                language_hint="English (en, left-to-right)",
            )
        except OmniAIError as exc:
            await _record_ai_failure(
                client_id, "chat", AI_GATEWAY.settings.chat_model, exc
            )
            _raise_ai_error(exc)
        await _record_ai_result(client_id, result)
        details = result.data.model_dump(mode="json")
        await asyncio.to_thread(
            store.add_message, payload.analysis_id, client_id, "user", payload.message, {}
        )
        message = await asyncio.to_thread(
            store.add_message,
            payload.analysis_id,
            client_id,
            "assistant",
            details["answer"],
            details,
        )
        envelope = {
            "message": message,
            "suggestions": details.get("follow_up_questions", []),
            "memory_candidates": details.get("memory_candidates", []),
        }
        stored_envelope = _without_execution_kit(envelope)
        await asyncio.to_thread(
            store.save_deep_dive, cache_key, payload.analysis_id, stored_envelope
        )
        return {
            "status": "success",
            "data": _with_execution_kit(
                stored_envelope,
                kit_context,
                analysis["tier"],
                payload.locale,
                details.get("recommended_actions") or [],
                facts=kit_facts,
            ),
            "cached": False,
        }
    finally:
        if reservation_id:
            await asyncio.to_thread(store.release_budget, reservation_id, client_id)
        await asyncio.to_thread(
            store.release_generation_lease, client_id, cache_key, chat_lease_id
        )


@app.post("/api/deep-dive", response_model=ApiEnvelope)
async def v2_deep_dive(payload: DeepDiveRequest, request: Request):
    client_id = _client_id(request)
    await asyncio.to_thread(store.ensure_client, client_id, payload.locale)
    if not check_deep_dive_rate_limit(f"deep:{client_id}", _remote_id(request)):
        raise HTTPException(status_code=429, detail="کمی صبر کنید.", headers={"Retry-After": "60"})
    analysis = await asyncio.to_thread(store.get_analysis, payload.analysis_id, client_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="تحلیل پیدا نشد.")
    steps = analysis["data"].get("action_steps") or []
    selected = None
    for index, step in enumerate(steps):
        step_identifier = str(step.get("step_id") if isinstance(step, dict) else index)
        if step_identifier == payload.step_id:
            selected = step
            break
    if selected is None:
        raise HTTPException(status_code=404, detail="گام انتخاب‌شده پیدا نشد.")
    profile = await asyncio.to_thread(store.get_profile, client_id, analysis["tier"])
    kit_facts = {
        **((profile.get("memory") or {}).get("facts") or {}),
        **(analysis.get("answers") or {}),
    }
    kit_context = _decision_context(
        analysis["query"],
        analysis.get("answers") or {},
        profile.get("memory") or {},
        selected_step=selected,
    )
    locale_cache_token = "\0locale:en"
    cache_key = "deep:" + hashlib.sha256(
        f"{payload.analysis_id}\0{payload.step_id}{locale_cache_token}".encode("utf-8")
    ).hexdigest()
    cached = await asyncio.to_thread(store.get_deep_dive, cache_key)
    if cached:
        await asyncio.to_thread(store.record_usage, client_id, "deep_dive", "local-cache", 0, 0, True)
        return {
            "status": "success",
            "data": _with_execution_kit(
                cached,
                kit_context,
                analysis["tier"],
                payload.locale,
                [selected],
                facts=kit_facts,
            ),
            "cached": True,
        }
    deep_lease_id = await asyncio.to_thread(
        store.acquire_generation_lease,
        client_id,
        cache_key,
        _generation_ttl_seconds(),
    )
    if not deep_lease_id:
        cached = await asyncio.to_thread(store.get_deep_dive, cache_key)
        if cached:
            await asyncio.to_thread(
                store.record_usage, client_id, "deep_dive", "local-cache", 0, 0, True
            )
            return {
                "status": "success",
                "data": _with_execution_kit(
                    cached,
                    kit_context,
                    analysis["tier"],
                    payload.locale,
                    [selected],
                    facts=kit_facts,
                ),
                "cached": True,
            }
        raise HTTPException(status_code=409, detail="جزئیات این گام در حال ساخته‌شدن است.")
    reservation_id: str | None = None
    try:
        if not AI_GATEWAY.settings.demo_mode:
            reservation_id = await asyncio.to_thread(
                store.reserve_budget,
                client_id,
                "deep_dive",
                MAX_DEEP_DIVES_PER_DAY,
                GLOBAL_MAX_DEEP_DIVES_PER_DAY,
                24,
                _generation_ttl_seconds(),
            )
            if not reservation_id:
                raise HTTPException(status_code=429, detail="سقف روزانهٔ جزئیات AI تکمیل شده است.")
        try:
            result = await AI_GATEWAY.deep_dive(
                step=selected,
                tier=analysis["tier"],
                horizon=analysis["horizon"],
                strategy_summary=_compact_strategy_for_ai(analysis["data"]),
                original_query=analysis["query"],
                live_intelligence=compact_intelligence_for_ai(
                    analysis["intelligence"]
                ),
                language_hint="English (en, left-to-right)",
            )
        except OmniAIError as exc:
            await _record_ai_failure(
                client_id, "deep_dive", AI_GATEWAY.settings.deep_dive_model, exc
            )
            _raise_ai_error(exc)
        await _record_ai_result(client_id, result)
        data = result.data.model_dump(mode="json")
        # The trusted route selection is authoritative even if a model/demo
        # echoes a different identifier in otherwise valid structured output.
        data["step_id"] = payload.step_id
        stored_data = _without_execution_kit(data)
        await asyncio.to_thread(
            store.save_deep_dive, cache_key, payload.analysis_id, stored_data
        )
        return {
            "status": "success",
            "data": _with_execution_kit(
                stored_data,
                kit_context,
                analysis["tier"],
                payload.locale,
                [selected],
                facts=kit_facts,
            ),
            "cached": False,
        }
    finally:
        if reservation_id:
            await asyncio.to_thread(store.release_budget, reservation_id, client_id)
        await asyncio.to_thread(
            store.release_generation_lease, client_id, cache_key, deep_lease_id
        )


@app.get("/api/vault", response_model=ApiEnvelope)
async def v2_get_vault(request: Request, limit: int = Query(default=30, ge=1, le=100)):
    client_id = _client_id(request)
    rows = await asyncio.to_thread(store.list_analyses, client_id, limit, False)
    locale = _request_locale(request)
    data = []
    for row in rows:
        # Up to 100 rows may be returned. Never echo complete analyses here;
        # one explicit detail request hydrates the selected row on demand.
        data.append(_vault_analysis_summary(row, locale))
    return {"status": "success", "data": data}


@app.post("/api/admin/claim-legacy", response_model=ApiEnvelope)
async def claim_legacy_vault(request: Request):
    """Explicit, token-protected one-time ownership migration for the old JSON vault."""
    supplied = request.headers.get("x-omni-legacy-token", "")
    if not LEGACY_CLAIM_TOKEN:
        raise HTTPException(status_code=404, detail="انتقال Vault قدیمی فعال نیست.")
    if not hmac.compare_digest(supplied, LEGACY_CLAIM_TOKEN):
        raise HTTPException(status_code=403, detail="مجوز انتقال Vault نامعتبر است.")
    claimed = await asyncio.to_thread(store.claim_legacy_analyses, _client_id(request))
    return {"status": "success", "data": {"claimed": claimed}}


@app.get("/api/profile", response_model=ApiEnvelope)
async def get_profile(request: Request, tier: Literal["B2C", "B2B"] = Query(default="B2C")):
    profile = await asyncio.to_thread(store.get_profile, _client_id(request), tier)
    return {"status": "success", "data": profile}


@app.post("/api/profile/memory", response_model=ApiEnvelope)
async def confirm_profile_memory(payload: MemoryConfirmationRequest, request: Request):
    """Persist one explicitly confirmed chat memory without another model call."""
    digest = hashlib.sha256(payload.content.casefold().encode("utf-8")).hexdigest()[:12]
    key = f"{payload.category}:{digest}"
    memory = await asyncio.to_thread(
        store.update_profile_memory,
        _client_id(request),
        payload.tier,
        {key: payload.content},
        None,
    )
    return {
        "status": "success",
        "data": {"tier": payload.tier, "key": key, "memory": memory},
    }


@app.delete("/api/profile", response_model=ApiEnvelope)
async def forget_profile(request: Request, tier: Literal["B2C", "B2B"] = Query(default="B2C")):
    deleted = await asyncio.to_thread(store.clear_profile_memory, _client_id(request), tier)
    return {"status": "success", "data": {"tier": tier, "cleared": deleted}}


@app.get("/api/goals", response_model=ApiEnvelope)
async def get_goals(request: Request):
    goals = await asyncio.to_thread(store.list_goals, _client_id(request), False)
    return {"status": "success", "data": goals}


@app.post("/api/goals", response_model=ApiEnvelope)
async def create_manual_goal(payload: ManualGoalRequest, request: Request):
    """Create a measurable goal locally; this path deliberately makes no AI call."""
    await asyncio.to_thread(store.ensure_client, _client_id(request), payload.locale)
    english = True
    deadline = payload.deadline.isoformat() if payload.deadline else (
        "No fixed deadline" if english else "بدون تاریخ قطعی"
    )
    copy = {
        "unspecified": "Not specified" if english else "تعیین نشده",
        "loss_ceiling": (
            "Define before committing funds"
            if english
            else "پیش از هزینه‌کرد مشخص شود"
        ),
        "review_cadence": "Weekly" if english else "هفتگی",
        "baseline_title": (
            "Define the baseline and next action"
            if english
            else "تعریف خط مبنا و اقدام بعدی"
        ),
        "first_week": "First week" if english else "هفتهٔ اول",
        "baseline_metric": (
            "Baseline and first action are recorded"
            if english
            else "خط مبنا و اولین اقدام ثبت شود"
        ),
        "baseline_evidence": (
            "One verifiable piece of evidence is recorded"
            if english
            else "یک شاهد قابل بررسی ثبت شده باشد"
        ),
        "review_title": (
            "Review progress against the target"
            if english
            else "بازبینی پیشرفت نسبت به هدف"
        ),
        "review_evidence": (
            "The outcome is compared with the target criterion"
            if english
            else "نتیجه با معیار هدف مقایسه شده باشد"
        ),
        "weekly_progress": "Weekly progress" if english else "پیشرفت هفتگی",
        "measurable_evidence": (
            "Measurable evidence" if english else "شاهد قابل‌اندازه‌گیری"
        ),
        "budget_stop": (
            "Budget ceiling is exceeded" if english else "عبور از سقف بودجه"
        ),
        "assumption_stop": (
            "The core assumption is invalidated"
            if english
            else "نامعتبر شدن فرض اصلی"
        ),
    }
    blueprint = {
        "goal_title": payload.title,
        "desired_outcome": payload.target,
        "target_metric": payload.target,
        "target_value": payload.target,
        "deadline": deadline,
        "weekly_time_commitment": payload.weekly_time or copy["unspecified"],
        "capital_ceiling": payload.budget or copy["unspecified"],
        "loss_ceiling": copy["loss_ceiling"],
        "review_cadence": copy["review_cadence"],
        "milestones": [
            {
                "milestone_id": "m1", "sequence": 1,
                "title": copy["baseline_title"],
                "due_window": copy["first_week"],
                "target_metric": copy["baseline_metric"],
                "completion_evidence": copy["baseline_evidence"],
            },
            {
                "milestone_id": "m2", "sequence": 2,
                "title": copy["review_title"],
                "due_window": deadline,
                "target_metric": payload.target,
                "completion_evidence": copy["review_evidence"],
            },
        ],
        "leading_indicators": [copy["weekly_progress"], copy["measurable_evidence"]],
        "stop_conditions": [copy["budget_stop"], copy["assumption_stop"]],
        "next_check_in": (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat(),
        "source": "manual",
    }
    goal = await asyncio.to_thread(
        store.create_goal,
        _client_id(request),
        None,
        payload.tier,
        payload.title,
        blueprint,
    )
    return {"status": "success", "data": goal}


@app.post("/api/goals/from-analysis", response_model=ApiEnvelope)
async def goal_from_analysis(payload: GoalFromAnalysisRequest, request: Request):
    client_id = _client_id(request)
    analysis = await asyncio.to_thread(store.get_analysis, payload.analysis_id, client_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="تحلیل پیدا نشد.")
    data = analysis["data"]
    blueprint = data.get("goal_blueprint") if isinstance(data.get("goal_blueprint"), dict) else None
    blueprint = dict(blueprint or _fallback_goal_blueprint(data, payload.locale))
    blueprint.setdefault("next_check_in", (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat())
    goal = await asyncio.to_thread(
        store.create_goal,
        client_id,
        payload.analysis_id,
        analysis["tier"],
        str(
            blueprint.get("goal_title")
            or data.get("signal_name")
            or "New goal"
        ),
        blueprint,
    )
    return {"status": "success", "data": goal}


@app.patch("/api/goals/{goal_id}", response_model=ApiEnvelope)
async def patch_goal(goal_id: str, payload: GoalUpdateRequest, request: Request):
    goal = await asyncio.to_thread(
        store.update_goal,
        goal_id,
        _client_id(request),
        payload.progress,
        payload.status,
        payload.next_check_in,
    )
    if not goal:
        raise HTTPException(status_code=404, detail="هدف پیدا نشد.")
    return {"status": "success", "data": goal}


@app.get("/api/usage", response_model=ApiEnvelope)
async def get_usage(request: Request, days: int = Query(default=30, ge=1, le=365)):
    summary = await asyncio.to_thread(store.usage_summary, _client_id(request), days)
    summary["limits"] = {
        "analyses_per_day": MAX_ANALYSES_PER_DAY,
        "chat_messages_per_day": MAX_CHAT_MESSAGES_PER_DAY,
        "deep_dives_per_day": MAX_DEEP_DIVES_PER_DAY,
        "global": {
            "analyses_per_day": GLOBAL_MAX_ANALYSES_PER_DAY,
            "chat_messages_per_day": GLOBAL_MAX_CHAT_MESSAGES_PER_DAY,
            "deep_dives_per_day": GLOBAL_MAX_DEEP_DIVES_PER_DAY,
        },
    }
    return {"status": "success", "data": summary}


@app.get("/api/calibration", response_model=ApiEnvelope)
async def v2_get_calibration(request: Request):
    predictions = await asyncio.to_thread(store.list_predictions, _client_id(request), 1000, None)
    data = compute_calibration(predictions)
    data["methodology"] = "directional_hit_rate"
    data["warning"] = _localized_message(
        request,
        "نمونهٔ کوچک و نتایج flat معیار عملکرد مالی یا تضمین سود نیستند.",
        "A small sample and flat outcomes do not measure financial performance or guarantee profit.",
    )
    return {"status": "success", "data": data}


@app.get("/api/predictions", response_model=ApiEnvelope)
async def v2_get_predictions(request: Request, limit: int = Query(default=100, ge=1, le=200)):
    predictions = await asyncio.to_thread(store.list_predictions, _client_id(request), limit, None)
    return {"status": "success", "data": predictions}


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.getenv("OMNI_HOST", "127.0.0.1"),
        port=_safe_positive_int("OMNI_PORT", 8000, 1, 65535),
        reload=os.getenv("OMNI_RELOAD", "0") == "1",
    )
