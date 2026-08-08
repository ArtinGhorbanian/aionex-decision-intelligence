"""Zero-token intake and clarification engine.

Questions are selected deterministically from missing decision variables.  The
user therefore gets a Claude-like clarification pass without an extra model
call or a second charge on every analysis.
"""

from __future__ import annotations

import re
from typing import Any


PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
RTL_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f]")

# Stable identity/capability facts can safely skip a repeated question.  Budget,
# time, current goal and constraints are decision-specific, so old values remain
# useful model context but do not silently replace a fresh clarification.
DURABLE_MEMORY_KEYS = {
    "skills", "market_access", "risk_tolerance", "validation_style",
    "decision_owner", "industry", "company_scale", "operating_markets",
    "risk_priority",
}


def is_rtl(text: str) -> bool:
    return bool(RTL_RE.search(text or ""))


def normalize_digits(text: str) -> str:
    return (text or "").translate(PERSIAN_DIGITS)


def _single(
    key: str,
    prompt: str,
    help_text: str,
    options: list[tuple[str, str]],
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": key,
        "type": "single",
        "prompt": prompt,
        "help": help_text,
        "required": required,
        "options": [{"value": value, "label": label} for value, label in options],
    }


def _text(
    key: str,
    prompt: str,
    help_text: str,
    placeholder: str,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": key,
        "type": "text",
        "prompt": prompt,
        "help": help_text,
        "placeholder": placeholder,
        "required": required,
        "max_length": 500,
    }


def extract_facts_from_query(query: str, tier: str) -> dict[str, str]:
    """Extract only high-confidence facts; ambiguous interpretation stays with the user."""
    raw = normalize_digits(query)
    low = raw.lower()
    facts: dict[str, str] = {}

    money_patterns = [
        r"(?:\$|usd\s*)([\d,.]+\s*[kKmM]?)",
        r"([\d,.]+\s*[kKmM]?)\s*(?:dollars?|دلار)",
        r"([\d,.]+)\s*(?:هزار|میلیون)\s*(?:دلار|تومان|ریال)",
        r"([\d,.]+)\s*(?:میلیون|هزار)\s*(?:تومان|ریال)",
    ]
    for pattern in money_patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            facts["capital"] = match.group(0).strip()
            break

    time_patterns = [
        r"([\d.]+)\s*(?:hours?|hrs?|ساعت)\s*(?:a|per|در|هر)?\s*(?:day|daily|روز|روزی)?",
        r"(?:روزی|روزانه)\s*([\d.]+)\s*ساعت",
    ]
    for pattern in time_patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            facts["available_time"] = match.group(0).strip()
            break

    if any(token in low for token in ("low risk", "ریسک کم", "کم ریسک", "safe", "امن")):
        facts["risk_tolerance"] = "conservative"
    elif any(token in low for token in ("high risk", "ریسک بالا", "تهاجمی")):
        facts["risk_tolerance"] = "aggressive"

    if tier == "B2B":
        industries = {
            "software": ("software", "saas", "نرم افزار", "فناوری"),
            "manufacturing": ("manufactur", "factory", "کارخانه", "تولید"),
            "retail": ("retail", "فروشگاه", "خرده"),
            "logistics": ("logistic", "shipping", "حمل", "زنجیره تامین"),
            "finance": ("bank", "finance", "مالی", "بانک"),
        }
        for name, tokens in industries.items():
            if any(token in low for token in tokens):
                facts["industry"] = name
                break
    return facts


def _fa_b2c_questions() -> list[dict[str, Any]]:
    return [
        _single(
            "primary_goal",
            "دقیقاً می‌خواهی این تصمیم چه نتیجه‌ای برایت بسازد؟",
            "هدف اصلی، نوع فرصت و معیار موفقیت را عوض می‌کند.",
            [
                ("income", "درآمد ماهانهٔ بیشتر"),
                ("business", "ساخت کسب‌وکار پایدار"),
                ("skill", "یادگیری مهارت درآمدزا"),
                ("capital_growth", "رشد سرمایه با کنترل ریسک"),
            ],
        ),
        _text(
            "skills",
            "الان چه مهارت‌ها، تجربه‌ها یا مزیت‌هایی داری؟",
            "حتی مهارت متوسط، زبان، شبکهٔ ارتباطی یا تجربهٔ صنعتی مهم است.",
            "مثلاً فروش، طراحی، برنامه‌نویسی، انگلیسی متوسط، تجربهٔ بازار پوشاک…",
        ),
        _single(
            "capital_range",
            "چه مقدار سرمایه واقعاً قابل استفاده است؟",
            "پولی را انتخاب کن که از دست رفتن بخشی از آن زندگی‌ات را مختل نمی‌کند.",
            [
                ("under_500", "کمتر از ۵۰۰ دلار"),
                ("500_2000", "۵۰۰ تا ۲٬۰۰۰ دلار"),
                ("2000_10000", "۲٬۰۰۰ تا ۱۰٬۰۰۰ دلار"),
                ("over_10000", "بیشتر از ۱۰٬۰۰۰ دلار"),
            ],
        ),
        _single(
            "available_time",
            "در یک هفته چند ساعت می‌توانی پایدار وقت بگذاری؟",
            "زمان پایدار مهم‌تر از هیجان هفتهٔ اول است.",
            [
                ("under_5h", "کمتر از ۵ ساعت"),
                ("5_10h", "۵ تا ۱۰ ساعت"),
                ("10_20h", "۱۰ تا ۲۰ ساعت"),
                ("over_20h", "بیشتر از ۲۰ ساعت"),
            ],
        ),
        _single(
            "risk_tolerance",
            "اگر مسیر طبق برنامه پیش نرفت، چه میزان ریسک قابل تحمل است؟",
            "این پاسخ روی اندازهٔ آزمایش، ذخیرهٔ نقدی و نقاط توقف اثر می‌گذارد.",
            [
                ("conservative", "محافظه‌کار؛ حفظ سرمایه اولویت اول"),
                ("balanced", "متعادل؛ ریسک محدود برای رشد"),
                ("aggressive", "تهاجمی؛ نوسان بیشتر برای بازده بالقوه"),
            ],
        ),
        _text(
            "market_access",
            "به کدام بازار، کشور یا گروه مشتری دسترسی واقعی داری؟",
            "دسترسی پرداخت، زبان و شبکهٔ تو می‌تواند یک فرصت را عملی یا غیرعملی کند.",
            "مثلاً ایران و امارات، مشتری فارسی‌زبان، امکان دریافت پرداخت بین‌المللی…",
        ),
        _single(
            "validation_style",
            "ترجیح می‌دهی با چه مدل اجرایی شروع کنی؟",
            "این انتخاب برنامهٔ ۷ روز اول را مشخص می‌کند.",
            [
                ("service_first", "خدمت کم‌هزینه و رسیدن سریع به اولین مشتری"),
                ("product_first", "ساخت محصول یا دارایی دیجیتال"),
                ("hybrid", "آزمایش ترکیبی و انتخاب بر اساس داده"),
            ],
        ),
    ]


def _fa_b2b_questions() -> list[dict[str, Any]]:
    return [
        _text(
            "decision_owner",
            "این تحلیل قرار است به تصمیم کدام تیم یا مدیر کمک کند؟",
            "خروجی برای مدیرعامل، عملیات، مالی و تدارکات معیارهای متفاوتی دارد.",
            "مثلاً مدیر عملیات برای تصمیم تأمین‌کنندهٔ فصل آینده…",
        ),
        _text(
            "industry",
            "صنعت، محصول اصلی و مدل درآمدی سازمان چیست؟",
            "بدون اقتصاد واحد محصول و ساختار صنعت، توصیهٔ B2B سطحی می‌شود.",
            "مثلاً تولید تجهیزات پزشکی B2B با فروش قراردادی…",
        ),
        _single(
            "company_scale",
            "مقیاس فعلی عملیات چقدر است؟",
            "مقیاس، تحمل ریسک و امکان اجرای راه‌حل را تعیین می‌کند.",
            [
                ("startup", "استارتاپ / کمتر از ۲۰ نفر"),
                ("smb", "کسب‌وکار متوسط / ۲۰ تا ۲۵۰ نفر"),
                ("enterprise", "سازمان بزرگ / بیش از ۲۵۰ نفر"),
                ("multi_entity", "گروه چندشرکتی یا چندکشوری"),
            ],
        ),
        _single(
            "decision_type",
            "نوع تصمیم سازمانی چیست؟",
            "موتور B2B بر اساس نوع تصمیم، ریسک و سنجه‌های متفاوتی می‌سازد.",
            [
                ("supply_chain", "ریسک زنجیرهٔ تأمین و تأمین‌کننده"),
                ("growth", "ورود به بازار یا رشد درآمد"),
                ("cost", "کاهش هزینه و بهبود حاشیه"),
                ("capital", "تخصیص سرمایه یا سرمایه‌گذاری"),
                ("resilience", "تاب‌آوری عملیاتی و سناریوهای بحران"),
            ],
        ),
        _text(
            "operating_markets",
            "کشورها، ارزها و وابستگی‌های کلیدی عملیات کدام‌اند؟",
            "ریسک ارزی، لجستیک، تحریم و تمرکز تأمین از همین نقشه به دست می‌آید.",
            "مثلاً فروش در ایران، تأمین از چین، تسویه با درهم…",
        ),
        _text(
            "constraints",
            "مهم‌ترین محدودیت غیرقابل‌مذاکره چیست؟",
            "بودجه، قانون، SLA، ظرفیت تیم یا قراردادهای موجود را شفاف کن.",
            "مثلاً توقف تولید مجاز نیست، بودجهٔ آزمایش ۳۰ هزار دلار، مهلت ۶۰ روز…",
        ),
        _single(
            "risk_priority",
            "کدام ریسک باید بیشترین وزن را بگیرد؟",
            "Sentinel تحلیل را با اولویت ریسک واقعی سازمان تنظیم می‌کند.",
            [
                ("cash", "نقدینگی و حاشیهٔ سود"),
                ("continuity", "تداوم عملیات و SLA"),
                ("regulatory", "حقوقی، مقررات و اعتبار برند"),
                ("concentration", "تمرکز مشتری یا تأمین‌کننده"),
            ],
        ),
    ]


def _en_b2c_questions() -> list[dict[str, Any]]:
    return [
        _single("primary_goal", "What outcome matters most?", "This changes the opportunity and success metric.", [
            ("income", "Increase monthly income"), ("business", "Build a durable business"),
            ("skill", "Learn a monetizable skill"), ("capital_growth", "Grow capital with controlled risk")]),
        _text("skills", "What skills, experience, or unfair advantages do you already have?", "Include languages, networks, and industry exposure.", "Sales, design, Python, an audience, supplier access…"),
        _single("capital_range", "How much capital is genuinely available?", "Exclude money you cannot afford to put at risk.", [
            ("under_500", "Under $500"), ("500_2000", "$500–$2,000"),
            ("2000_10000", "$2,000–$10,000"), ("over_10000", "Over $10,000")]),
        _single("available_time", "How many sustainable hours can you commit each week?", "Use a realistic repeatable number.", [
            ("under_5h", "Under 5 hours"), ("5_10h", "5–10 hours"),
            ("10_20h", "10–20 hours"), ("over_20h", "20+ hours")]),
        _single("risk_tolerance", "What downside can you tolerate?", "This controls experiment size and stop rules.", [
            ("conservative", "Conservative — preserve capital"), ("balanced", "Balanced — limited risk"),
            ("aggressive", "Aggressive — accept more volatility")]),
        _text("market_access", "Which customers, countries, or payment rails can you realistically access?", "Access often decides whether an idea is executable.", "US clients, Persian speakers, UAE suppliers, Stripe access…"),
        _single("validation_style", "Which execution model should you test first?", "This choice shapes the first seven days.", [
            ("service_first", "Low-cost service and a fast first customer"),
            ("product_first", "Build a product or digital asset"),
            ("hybrid", "Run both tests and choose from evidence")]),
    ]


def _en_b2b_questions() -> list[dict[str, Any]]:
    return [
        _text("decision_owner", "Which decision owner will use this analysis?", "A CEO, CFO, and operations lead need different evidence.", "Operations lead deciding next quarter's supplier mix…"),
        _text("industry", "What are the industry, core product, and revenue model?", "Unit economics and industry structure are essential.", "B2B medical-device manufacturer on annual contracts…"),
        _single("company_scale", "What is the current operating scale?", "Scale determines feasible controls and risk capacity.", [
            ("startup", "Startup / under 20 people"), ("smb", "Mid-market / 20–250"),
            ("enterprise", "Enterprise / 250+"), ("multi_entity", "Multi-entity or multinational")]),
        _single("decision_type", "What type of enterprise decision is this?", "Each path uses different metrics and risks.", [
            ("supply_chain", "Supply-chain / vendor risk"), ("growth", "Market entry / revenue growth"),
            ("cost", "Cost and margin"), ("capital", "Capital allocation"), ("resilience", "Operational resilience")]),
        _text("operating_markets", "Which countries, currencies, and critical dependencies are involved?", "This maps FX, logistics, regulation, and concentration exposure.", "Sell in Germany, source in Taiwan, settle in USD…"),
        _text("constraints", "What constraint is non-negotiable?", "Name budget, regulation, SLA, team capacity, or deadline.", "No production interruption; $30k pilot cap; 60-day deadline…"),
        _single("risk_priority", "Which risk deserves the highest weight?", "Sentinel will anchor scenarios to this priority.", [
            ("cash", "Cash flow and margin"), ("continuity", "Continuity and SLA"),
            ("regulatory", "Legal, regulation, reputation"), ("concentration", "Customer or supplier concentration")]),
    ]


def build_questions(
    query: str,
    tier: str,
    horizon: str,
    memory: dict[str, Any] | None = None,
    max_questions: int = 5,
    locale: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return the highest-value unanswered questions plus facts found in the query."""
    # User-authored text may use any supported script, but product-generated
    # clarification copy is always English.
    _ = locale
    bank = _en_b2c_questions() if tier == "B2C" else _en_b2b_questions()
    extracted = extract_facts_from_query(query, tier)
    remembered = ((memory or {}).get("facts") or {}) if isinstance(memory, dict) else {}
    durable_remembered: dict[str, Any] = {}
    if isinstance(remembered, dict):
        for key, value in remembered.items():
            canonical_key = (
                "skills" if str(key).startswith("skill:") else str(key)
            )
            if canonical_key in DURABLE_MEMORY_KEYS:
                durable_remembered[canonical_key] = value
    known = {**durable_remembered, **extracted}

    # Extraction keeps the literal amount under ``capital`` so it remains useful
    # context for the model.  The intake bank asks for a coarse ``capital_range``;
    # a confidently extracted literal amount already answers that question.
    if known.get("capital"):
        known["capital_range"] = known["capital"]

    selected = [question for question in bank if question["id"] not in known]
    # Strategic decisions prioritize durability, invalidation and downside.  The
    # instant path keeps the bank's execution-first order, so horizon is a real
    # decision workflow rather than a prompt label.
    if horizon == "strategic":
        priority = (
            ["primary_goal", "skills", "validation_style", "risk_tolerance", "capital_range"]
            if tier == "B2C"
            else ["decision_owner", "industry", "constraints", "risk_priority", "decision_type"]
        )
        priority_index = {key: index for index, key in enumerate(priority)}
        original_index = {question["id"]: index for index, question in enumerate(selected)}
        selected.sort(
            key=lambda question: (
                priority_index.get(question["id"], len(priority)),
                original_index[question["id"]],
            )
        )
    selected = selected[: max(2, min(max_questions, 6))]
    unknown_label = "Not sure yet"
    en_by_id = {
        item["id"]: item
        for item in (_en_b2c_questions() if tier == "B2C" else _en_b2b_questions())
    }
    for question in selected:
        question["allow_unknown"] = True
        question["unknown_label"] = unknown_label
        en_question = en_by_id.get(question["id"], question)
        question["translations"] = {
            "fa": {
                "prompt": en_question.get("prompt"),
                "help": en_question.get("help"),
                "placeholder": en_question.get("placeholder"),
                "unknown_label": "Not sure yet",
            },
            "en": {
                "prompt": en_question.get("prompt"),
                "help": en_question.get("help"),
                "placeholder": en_question.get("placeholder"),
                "unknown_label": "Not sure yet",
            },
        }
        en_options = {
            str(item.get("value")): item.get("label")
            for item in en_question.get("options", [])
        }
        for option in question.get("options", []):
            value = str(option.get("value"))
            option["translations"] = {
                "fa": en_options.get(value, option.get("label")),
                "en": en_options.get(value, option.get("label")),
            }
    return selected, extracted


def validate_answers(questions: list[dict[str, Any]], answers: dict[str, Any]) -> dict[str, str]:
    """Accept only fields issued by this intake session and bound every value."""
    if not isinstance(answers, dict):
        raise ValueError("answers must be an object")
    cleaned: dict[str, str] = {}
    missing: list[str] = []
    for question in questions:
        key = question["id"]
        value = answers.get(key)
        text = "" if value is None else str(value).strip()
        if question.get("required", True) and not text:
            missing.append(key)
            continue
        if not text:
            continue
        # ``unknown`` is an explicit answer, not a missing field.  The analysis
        # can surface the data gap while the profile layer deliberately avoids
        # remembering it as a durable user fact.
        if text == "unknown" and question.get("allow_unknown", True):
            cleaned[key] = text
            continue
        if len(text) > int(question.get("max_length", 500)):
            raise ValueError(f"answer '{key}' is too long")
        if question.get("type") == "single":
            allowed = {str(option["value"]) for option in question.get("options", [])}
            if text not in allowed:
                raise ValueError(f"answer '{key}' is not one of the allowed options")
        cleaned[key] = text
    if missing:
        raise ValueError("missing required answers: " + ", ".join(missing))
    return cleaned


def readable_context(
    query: str,
    answers: dict[str, Any],
    extracted: dict[str, Any],
    memory: dict[str, Any] | None,
) -> str:
    remembered = ((memory or {}).get("facts") or {}) if isinstance(memory, dict) else {}
    combined = {**remembered, **extracted, **answers}
    lines = [f"ORIGINAL SITUATION: {query}", "VERIFIED DECISION CONTEXT:"]
    lines.extend(f"- {key}: {value}" for key, value in combined.items() if str(value).strip())
    return "\n".join(lines)
