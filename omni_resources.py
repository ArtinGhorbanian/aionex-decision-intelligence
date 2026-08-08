"""Trusted, bilingual execution resources and outreach templates.

This is a deterministic enrichment layer: it creates concrete next actions,
verified URLs and editable messages without another model request.  URLs never
come from model or user output, and no message is sent automatically.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any, Literal
from urllib.parse import urlsplit


Locale = Literal["fa", "en"]
Tier = Literal["B2C", "B2B"]
AccessType = Literal[
    "free_keyless",
    "free_account",
    "freemium",
    "transaction_fee",
    "unknown",
]
ContactChannel = Literal["help_center", "contact_form", "email", "phone"]
VERIFIED_AT = "2026-07-13"
DEFAULT_REVIEW_AFTER = "2026-10-13"

ACCESS_TYPES: frozenset[str] = frozenset(
    {"free_keyless", "free_account", "freemium", "transaction_fee", "unknown"}
)
CONTACT_CHANNELS: frozenset[str] = frozenset(
    {"help_center", "contact_form", "email", "phone"}
)

# Exact hosts only.  A subdomain is not trusted merely because its parent is.
ALLOWED_RESOURCE_HOSTS: frozenset[str] = frozenset(
    {
        "academy.hubspot.com",
        "data.worldbank.org",
        "github.com",
        "learn.microsoft.com",
        "open.fda.gov",
        "search.google.com",
        "stat.unido.org",
        "support.google.com",
        "support.upwork.com",
        "ted.europa.eu",
        "trade.ec.europa.eu",
        "trends.google.com",
        "www.canada.ca",
        "www.cisa.gov",
        "www.fairwork.gov.au",
        "www.federalregister.gov",
        "www.google.com",
        "www.sba.gov",
        "www.score.org",
        "www.sec.gov",
        "www.upwork.com",
    }
)


@dataclass(frozen=True)
class LocalizedText:
    fa: str
    en: str

    def get(self, locale: Locale) -> str:
        return self.en if locale == "en" else self.fa


@dataclass(frozen=True)
class Resource:
    resource_id: str
    name: LocalizedText
    url: str
    purpose: LocalizedText
    first_action: LocalizedText
    access_note: LocalizedText
    limitation: LocalizedText
    tags: frozenset[str]
    tiers: frozenset[Tier]
    jurisdiction: str = "GLOBAL"
    official: bool = True
    access_type: AccessType = "free_keyless"
    verified_at: str = VERIFIED_AT
    review_after: str = DEFAULT_REVIEW_AFTER
    support_url: str | None = None
    contact_channel: ContactChannel | None = None

    @property
    def free_access(self) -> bool:
        """Whether the complete recommended action has no platform fee."""

        return self.access_type in {"free_keyless", "free_account"}

    @property
    def requires_account(self) -> bool:
        return self.access_type in {
            "free_account",
            "freemium",
            "transaction_fee",
        }


def _resource(
    resource_id: str,
    name_fa: str,
    name_en: str,
    url: str,
    purpose_fa: str,
    purpose_en: str,
    action_fa: str,
    action_en: str,
    tags: tuple[str, ...],
    tiers: tuple[Tier, ...] = ("B2C", "B2B"),
    *,
    jurisdiction: str = "GLOBAL",
    requires_account: bool = False,
    access_type: AccessType | None = None,
    verified_at: str = VERIFIED_AT,
    review_after: str = DEFAULT_REVIEW_AFTER,
    support_url: str | None = None,
    contact_channel: ContactChannel | None = None,
    access_fa: str = "دسترسی اولیه رایگان است و API پولی استفاده نمی‌شود.",
    access_en: str = "Initial access is free and no paid API is used.",
    limitation_fa: str = "پیش از اقدام مالی یا حقوقی، شرایط و قوانین محل فعالیت خود را بررسی کنید.",
    limitation_en: str = "Check the terms and rules in your operating jurisdiction before financial or legal action.",
) -> Resource:
    return Resource(
        resource_id=resource_id,
        name=LocalizedText(name_fa, name_en),
        url=url,
        purpose=LocalizedText(purpose_fa, purpose_en),
        first_action=LocalizedText(action_fa, action_en),
        access_note=LocalizedText(access_fa, access_en),
        limitation=LocalizedText(limitation_fa, limitation_en),
        tags=frozenset(tags),
        tiers=frozenset(tiers),
        jurisdiction=jurisdiction,
        access_type=access_type
        or ("free_account" if requires_account else "free_keyless"),
        verified_at=verified_at,
        review_after=review_after,
        support_url=support_url,
        contact_channel=contact_channel,
    )


RESOURCE_CATALOG: tuple[Resource, ...] = (
    _resource(
        "google_trends",
        "گوگل ترندز",
        "Google Trends",
        "https://trends.google.com/trends/explore",
        "مقایسه جهت و کشش جست‌وجوی چند مسئله یا پیشنهاد ارزش، نه برآورد مستقیم اندازه بازار.",
        "Compare the direction and search interest of problems or value propositions; it is not a direct market-size estimate.",
        "دو تا پنج عبارت دقیق مشتری را در کشور هدف مقایسه و نمودار و Related queries را ثبت کنید.",
        "Compare two to five precise customer phrases in the target country and record the chart and related queries.",
        ("validation", "demand", "market_research", "marketing", "content"),
    ),
    _resource(
        "world_bank_data",
        "داده‌های بانک جهانی",
        "World Bank Data",
        "https://data.worldbank.org/indicator",
        "بررسی خط مبنای اقتصاد، جمعیت، تورم، اشتغال و دسترسی دیجیتال کشور هدف.",
        "Check economic, population, inflation, labor and digital-access baselines for the target country.",
        "کشور و یک شاخص مرتبط را انتخاب کنید و آخرین سال موجود و محدودیت زمانی داده را یادداشت کنید.",
        "Choose the country and one relevant indicator; record the latest available year and the data lag.",
        ("macro", "country", "strategic", "research", "employment", "industry"),
    ),
    _resource(
        "eu_access2markets",
        "درگاه Access2Markets اتحادیه اروپا",
        "EU Access2Markets",
        "https://trade.ec.europa.eu/access-to-markets/en/home",
        "بررسی تعرفه، مالیات، قواعد مبدأ، تشریفات و الزامات محصول برای تجارت با اتحادیه اروپا.",
        "Check tariffs, taxes, rules of origin, procedures and product requirements for EU trade.",
        "کد کالای تقریبی، کشور مبدأ و مقصد را وارد و نتیجه را در پرونده تصمیم ذخیره کنید.",
        "Enter the approximate product code, origin and destination, then save the result in the decision record.",
        ("trade", "supply", "compliance", "procurement"),
        ("B2B",),
        jurisdiction="EU",
        access_fa="رایگان و چندزبانه است؛ برای جست‌وجوی اولیه حساب پولی نمی‌خواهد.",
        access_en="Free and multilingual; initial lookup does not require a paid account.",
    ),
    _resource(
        "ted_tenders",
        "مناقصه‌های رسمی اتحادیه اروپا (TED)",
        "EU Tenders (TED)",
        "https://ted.europa.eu/en/search/result",
        "یافتن مناقصه‌های عمومی و مشاهده خریدار، مهلت و متن رسمی آگهی.",
        "Find public tenders and inspect the buyer, deadline and official notice.",
        "سه کلیدواژه صنعت و کشور هدف را جست‌وجو کنید؛ فقط فرصت‌های با مهلت و شرایط متناسب را نگه دارید.",
        "Search three industry keywords and the target country; keep only opportunities whose deadline and requirements fit.",
        ("procurement", "sales", "trade", "opportunity"),
        ("B2B",),
        jurisdiction="EU",
    ),
    _resource(
        "sba_business_guide",
        "راهنمای کسب‌وکار SBA",
        "SBA Business Guide",
        "https://www.sba.gov/business-guide",
        "چک‌لیست ساخت، راه‌اندازی، مدیریت و رشد کسب‌وکار کوچک در آمریکا.",
        "A structured checklist for planning, launching, managing and growing a US small business.",
        "فقط بخش مرتبط با مرحله فعلی را باز کنید و مجوز، ساختار و تعهدات لازم را به‌عنوان سؤال بررسی ثبت کنید.",
        "Open only the section matching the current stage and log licenses, structure and obligations as verification questions.",
        ("business", "startup", "compliance", "planning"),
        jurisdiction="US",
        limitation_fa="راهنمای آمریکا است و جایگزین قانون یا مشاور محل فعالیت شما نیست.",
        limitation_en="US guidance only; it does not replace the law or an adviser in your jurisdiction.",
    ),
    _resource(
        "score_mentor",
        "منتورینگ SCORE",
        "SCORE Mentoring",
        "https://www.score.org/find-mentor",
        "دریافت بازخورد کسب‌وکار از منتور داوطلب برای بازار آمریکا.",
        "Get business feedback from a volunteer mentor for the US market.",
        "یک سؤال تصمیمی مشخص، داده‌های فعلی و گزینه‌ها را آماده و درخواست منتور متناسب ثبت کنید.",
        "Prepare one specific decision question, current evidence and options, then request a relevant mentor.",
        ("business", "mentor", "validation", "planning", "startup"),
        jurisdiction="US",
        requires_account=True,
        access_fa="جلسه‌های منتورینگ اصلی رایگان‌اند؛ ثبت درخواست لازم است.",
        access_en="Core mentoring is free; a request must be submitted.",
    ),
    _resource(
        "github_new_repo",
        "ساخت مخزن در GitHub",
        "Create a GitHub Repository",
        "https://github.com/new",
        "ساخت نمونه قابل‌نمایش، ثبت تغییرات و جمع‌آوری issue برای مسیر نرم‌افزاری.",
        "Create a demonstrable prototype, track changes and collect issues for a software path.",
        "یک مخزن خصوصی یا عمومی با README شامل مسئله، مخاطب و معیار تست بسازید؛ هیچ کلید یا راز را commit نکنید.",
        "Create a private or public repository with a README containing the problem, audience and test metric; never commit secrets.",
        ("technology", "software", "portfolio", "validation", "skills"),
        requires_account=True,
    ),
    _resource(
        "microsoft_learn",
        "Microsoft Learn",
        "Microsoft Learn",
        "https://learn.microsoft.com/training/",
        "یادگیری رایگان و ساختاریافته برای مهارت‌های فنی و کسب‌وکار دیجیتال.",
        "Free structured learning for technical and digital-business skills.",
        "یک مسیر کوتاه مرتبط را انتخاب کنید و خروجی عملی هفته اول را قبل از شروع تعریف کنید.",
        "Choose one short relevant path and define the practical week-one deliverable before starting.",
        ("skills", "technology", "career", "learning"),
        ("B2C",),
    ),
    _resource(
        "hubspot_academy",
        "HubSpot Academy",
        "HubSpot Academy",
        "https://academy.hubspot.com/",
        "آموزش رایگان فروش، بازاریابی و مدیریت ارتباط با مشتری.",
        "Free training in sales, marketing and customer relationship management.",
        "فقط یک درس مرتبط با گلوگاه فعلی انتخاب و همان روز یک تمرین آن را روی پیشنهاد خود اجرا کنید.",
        "Choose one lesson tied to the current bottleneck and apply one exercise to the offer the same day.",
        ("skills", "sales", "marketing", "content", "learning"),
        requires_account=True,
    ),
    _resource(
        "google_business_profile",
        "Google Business Profile",
        "Google Business Profile",
        "https://www.google.com/business/",
        "ساخت حضور رایگان برای کسب‌وکار محلی در Google Search و Maps.",
        "Create a free local-business presence on Google Search and Maps.",
        "واجدشرایط‌بودن را بررسی و نام، دسته، محدوده خدمت، ساعات و راه تماس معتبر را آماده کنید.",
        "Check eligibility and prepare the verified name, category, service area, hours and contact route.",
        ("local", "sales", "marketing", "business"),
        requires_account=True,
        support_url="https://support.google.com/business/",
        contact_channel="help_center",
        limitation_fa="فقط برای کسب‌وکارهای واجد شرایط و مطابق دستورالعمل نمایش در Google است.",
        limitation_en="Only for eligible businesses that follow Google's representation guidelines.",
    ),
    _resource(
        "search_console",
        "Google Search Console",
        "Google Search Console",
        "https://search.google.com/search-console/about",
        "اندازه‌گیری فنی دیده‌شدن سایت و خطاهای ایندکس، بدون خرید تبلیغ.",
        "Measure technical search visibility and indexing errors without buying ads.",
        "مالکیت دامنه را تأیید کنید و قبل از هر بهینه‌سازی، baseline کلیک، نمایش و خطا را ثبت کنید.",
        "Verify the domain and record baseline clicks, impressions and errors before optimizing anything.",
        ("content", "marketing", "website", "sales"),
        requires_account=True,
        support_url="https://support.google.com/webmasters/",
        contact_channel="help_center",
    ),
    _resource(
        "federal_register",
        "Federal Register",
        "Federal Register",
        "https://www.federalregister.gov/documents/search",
        "جست‌وجوی قوانین، قواعد پیشنهادی و اطلاعیه‌های رسمی فدرال آمریکا.",
        "Search official US federal rules, proposed rules and notices.",
        "نام صنعت و موضوع را جست‌وجو کنید؛ تاریخ اجرا، نهاد صادرکننده و لینک متن رسمی را ثبت کنید.",
        "Search the industry and topic; record the effective date, issuing agency and official text link.",
        ("compliance", "regulation", "risk"),
        ("B2B",),
        jurisdiction="US",
        limitation_fa="فقط مقررات فدرال آمریکا را پوشش می‌دهد و تفسیر حقوقی ارائه نمی‌کند.",
        limitation_en="Covers US federal material only and does not provide legal interpretation.",
    ),
    _resource(
        "cisa_kev",
        "کاتالوگ آسیب‌پذیری‌های CISA",
        "CISA Known Exploited Vulnerabilities",
        "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "اولویت‌بندی آسیب‌پذیری‌هایی که بهره‌برداری واقعی از آن‌ها شناخته شده است.",
        "Prioritize vulnerabilities known to be exploited in the wild.",
        "فهرست نرم‌افزار و vendorهای درون محدوده را با کاتالوگ تطبیق و مالک اصلاح هر مورد را مشخص کنید.",
        "Match in-scope software and vendors to the catalog and assign a remediation owner for each match.",
        ("cyber", "risk", "vendor", "compliance"),
        ("B2B",),
        jurisdiction="GLOBAL",
    ),
    _resource(
        "sec_edgar",
        "SEC EDGAR",
        "SEC EDGAR",
        "https://www.sec.gov/edgar/search/",
        "بررسی filingهای رسمی شرکت‌های مشمول گزارش‌دهی SEC برای due diligence.",
        "Review official filings of SEC-reporting companies for due diligence.",
        "نام حقوقی شرکت را بیابید و آخرین 10-K/10-Q و بخش Risk Factors را با تاریخ ثبت یادداشت کنید.",
        "Find the legal company name, then record the latest 10-K/10-Q and its Risk Factors section with filing date.",
        ("company", "vendor", "finance", "research"),
        ("B2B",),
        jurisdiction="US",
        limitation_fa="فقط ناشران مشمول SEC را پوشش می‌دهد؛ نبود نتیجه به معنی نبود ریسک نیست.",
        limitation_en="Only covers SEC-reporting issuers; no result does not imply no risk.",
    ),
    _resource(
        "openfda",
        "openFDA",
        "openFDA",
        "https://open.fda.gov/data/",
        "بررسی داده‌های عمومی recall و enforcement برای غذا، دارو و تجهیزات در آمریکا.",
        "Review public recall and enforcement data for US food, drugs and devices.",
        "نام محصول، شرکت و دسته را جداگانه جست‌وجو و هر تطابق را با رکورد رسمی بازبینی کنید.",
        "Search the product, company and category separately, then inspect every match in the official record.",
        ("food", "health", "compliance", "vendor", "regulation"),
        ("B2B",),
        jurisdiction="US",
    ),
    _resource(
        "unido_statistics",
        "درگاه آمار صنعتی UNIDO",
        "UNIDO Statistics Portal",
        "https://stat.unido.org/data/table",
        "مقایسه داده‌های رسمی تولید، تجارت و ساختار صنعت در اقتصادهای مختلف.",
        "Compare official manufacturing, trade and industrial-structure data across economies.",
        "کشور، طبقه ISIC و شاخص دقیق را انتخاب کنید؛ سال پوشش و شکاف داده را کنار نتیجه ثبت کنید.",
        "Select the country, exact ISIC class and indicator; record the coverage year and data gaps with the result.",
        ("manufacturing", "industry", "supply", "trade", "research", "macro"),
        jurisdiction="GLOBAL",
        support_url="https://stat.unido.org/about",
        contact_channel="email",
        limitation_fa="این درگاه برای خط مبنای آماری است؛ مجوز محلی کارخانه یا قیمت روز تجهیزات را تأیید نمی‌کند.",
        limitation_en="This is a statistical baseline; it does not verify local factory permits or current equipment prices.",
    ),
    _resource(
        "australia_fair_work",
        "بازرس کار منصفانه استرالیا",
        "Australian Fair Work Ombudsman",
        "https://www.fairwork.gov.au/employment-conditions",
        "بررسی رسمی حداقل استانداردها، دستمزد، مرخصی و شرایط استخدام در استرالیا.",
        "Check official minimum standards, pay, leave and employment conditions in Australia.",
        "نوع رابطه کاری و award احتمالی را مشخص و سپس بخش مرتبط را با تاریخ بازبینی در پرونده منابع انسانی ثبت کنید.",
        "Identify the work relationship and likely award, then record the relevant guidance and review date in the HR file.",
        ("employment", "hr", "compliance", "regulation", "career"),
        jurisdiction="AU",
        support_url="https://www.fairwork.gov.au/about-us/contact-us",
        contact_channel="phone",
        limitation_fa="راهنمای عمومی استرالیا است؛ برای تفسیر پرونده خاص از متخصص روابط کار کمک بگیرید.",
        limitation_en="This is general Australian guidance; seek workplace-relations advice for case-specific interpretation.",
    ),
    _resource(
        "canada_foreign_credentials",
        "برنامه شناسایی مدارک خارجی کانادا",
        "Canada Foreign Credential Recognition",
        "https://www.canada.ca/en/employment-social-development/programs/foreign-credential-recognition-program.html",
        "نقشه رسمی کانادا برای شناسایی مدرک و ورود متخصصان آموزش‌دیده در خارج به مشاغل تنظیم‌شده.",
        "Canada's official overview of foreign-credential recognition for regulated occupations.",
        "استان مقصد و نهاد تنظیم‌گر حرفه را پیدا کنید؛ مراحل، مدارک، هزینه‌های احتمالی و زمان هر مرحله را از همان نهاد تأیید کنید.",
        "Identify the destination province and profession regulator; confirm steps, documents, possible fees and timing with that regulator.",
        ("credential", "nursing", "health", "career", "employment", "compliance"),
        jurisdiction="CA",
        limitation_fa="مجوز حرفه‌ای عمدتاً استانی/قلمرویی است و ممکن است ارزیابی یا آزمون شخص ثالث هزینه داشته باشد.",
        limitation_en="Professional licensing is mainly provincial/territorial and third-party assessments or exams may have fees.",
    ),
    _resource(
        "upwork_profile",
        "ساخت پروفایل Upwork",
        "Create an Upwork Profile",
        "https://www.upwork.com/nx/create-profile/",
        "آزمون عرضه یک خدمت مشخص در بازار فریلنس بین‌المللی.",
        "Test a clearly scoped service in an international freelance marketplace.",
        "پیش از ساخت پروفایل، یک خدمت، یک خروجی، زمان تحویل و سه نمونه مدرک توانایی را آماده کنید.",
        "Before creating the profile, prepare one service, one deliverable, delivery time and three pieces of proof.",
        ("freelance", "skills", "sales", "career", "employment"),
        ("B2C",),
        access_type="transaction_fee",
        review_after="2026-08-13",
        support_url="https://support.upwork.com/hc/en-us",
        contact_channel="help_center",
        access_fa="ساخت حساب هزینه اولیه ندارد؛ کارمزدها و محدودیت کشور را پیش از قبول کار بررسی کنید.",
        access_en="Account creation has no upfront fee; check service fees and country eligibility before accepting work.",
        limitation_fa="دسترسی و پرداخت در همه کشورها یکسان نیست و پلتفرم پس از درآمد کارمزد دارد.",
        limitation_en="Availability and payouts vary by country, and the platform charges fees after earnings.",
    ),
)
RESOURCE_BY_ID = {item.resource_id: item for item in RESOURCE_CATALOG}

# A user naming a catalog destination is stronger evidence than a broad intent
# tag. Keep these aliases phrase-specific so brand-like substrings (for example
# "GitHubber" or "Microsoft Learner") cannot activate a resource accidentally.
EXPLICIT_RESOURCE_PATTERNS: dict[str, tuple[str, ...]] = {
    "github_new_repo": (
        "github repository",
        "github repo",
        "repository on github",
        "repo on github",
        "مخزن گیت هاب",
        "مخزن در گیت هاب",
        "ریپازیتوری گیت هاب",
        "ریپو گیت هاب",
        "مخزن گیتهاب",
        "ریپازیتوری گیتهاب",
    ),
    "microsoft_learn": (
        "microsoft learn",
        "مایکروسافت لرن",
    ),
}


TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "technology": (
        "software",
        "saas",
        "developer",
        "coding",
        "artificial intelligence",
        "machine learning",
        "ai",
        "نرم افزار",
        "نرم‌افزار",
        "برنامه نویسی",
        "برنامه‌نویسی",
        "هوش مصنوعی",
    ),
    "freelance": (
        "freelance",
        "freelancer",
        "freelancing",
        "gig work",
        "side income",
        "فریلنس",
        "فریلنسر",
        "درآمد جانبی",
    ),
    "skills": (
        "skill",
        "skills",
        "learn",
        "learning",
        "training",
        "course",
        "مهارت",
        "یادگیری",
        "آموزش",
        "دوره",
    ),
    "trade": (
        "import",
        "export",
        "tariff",
        "trade",
        "customs",
        "واردات",
        "صادرات",
        "تعرفه",
        "تجارت",
        "گمرک",
    ),
    "supply": (
        "supplier",
        "suppliers",
        "supply chain",
        "vendor",
        "vendors",
        "تامین کننده",
        "تأمین کننده",
        "زنجیره تامین",
        "زنجیره تأمین",
        "فروشنده",
    ),
    "procurement": (
        "procurement",
        "request for quotation",
        "rfq",
        "purchase order",
        "تدارکات",
        "استعلام قیمت",
        "خرید سازمانی",
    ),
    "manufacturing": (
        "factory",
        "manufacturing",
        "production line",
        "industrial plant",
        "کارخانه",
        "تولید صنعتی",
        "خط تولید",
    ),
    "industry": ("industry", "industrial", "manufacturing sector", "صنعت", "صنعتی"),
    "compliance": (
        "law",
        "legal",
        "regulation",
        "regulations",
        "regulatory",
        "license",
        "licence",
        "compliance",
        "قانون",
        "حقوقی",
        "مقررات",
        "مجوز",
        "انطباق",
    ),
    "food": ("food", "drug", "pharmaceutical", "غذا", "دارو", "دارویی"),
    "health": (
        "health",
        "healthcare",
        "medical",
        "nurse",
        "nurses",
        "nursing",
        "سلامت",
        "درمان",
        "پزشکی",
        "پرستار",
        "پرستاری",
    ),
    "nursing": ("nurse", "nurses", "nursing", "registered nurse", "پرستار", "پرستاری"),
    "credential": (
        "credential",
        "credentials",
        "degree recognition",
        "professional recognition",
        "licensure",
        "مدرک",
        "اعتبارسنجی مدرک",
        "تطبیق مدرک",
        "پروانه حرفه ای",
        "پروانه حرفه‌ای",
    ),
    "employment": (
        "employment",
        "employee",
        "employees",
        "employer",
        "workplace",
        "job",
        "jobs",
        "استخدام",
        "کارمند",
        "کارفرما",
        "محل کار",
        "شغل",
    ),
    "hr": (
        "human resources",
        "hr",
        "people operations",
        "منابع انسانی",
        "امور کارکنان",
    ),
    "career": ("career", "occupation", "profession", "مسیر شغلی", "حرفه"),
    "sales": (
        "sales",
        "customer",
        "customers",
        "lead generation",
        "فروش",
        "مشتری",
        "جذب مشتری",
    ),
    "marketing": (
        "marketing",
        "advertising",
        "campaign",
        "بازاریابی",
        "تبلیغات",
        "کمپین",
    ),
    "content": ("content", "seo", "newsletter", "محتوا", "سئو", "خبرنامه"),
    "website": (
        "website",
        "web site",
        "domain",
        "indexing",
        "search console",
        "وب سایت",
        "وب‌سایت",
        "دامنه",
        "ایندکس",
    ),
    "local": (
        "local business",
        "local shop",
        "restaurant",
        "retail store",
        "کسب و کار محلی",
        "کسب‌وکار محلی",
        "فروشگاه",
        "رستوران",
    ),
    "company": (
        "company",
        "companies",
        "competitor",
        "competitors",
        "investor",
        "شرکت",
        "رقیب",
        "سرمایه گذار",
        "سرمایه‌گذار",
    ),
    "cyber": (
        "cyber",
        "cybersecurity",
        "cyber security",
        "information security",
        "vulnerability",
        "vulnerabilities",
        "امنیت سایبری",
        "آسیب پذیری",
        "آسیب‌پذیری",
    ),
    "validation": (
        "validate",
        "validation",
        "test my idea",
        "idea validation",
        "اعتبارسنجی",
        "سنجش ایده",
        "آزمون ایده",
    ),
    "demand": (
        "market demand",
        "search demand",
        "customer demand",
        "تقاضای بازار",
        "تقاضای مشتری",
    ),
    "market_research": (
        "market research",
        "customer research",
        "market size",
        "تحقیق بازار",
        "اندازه بازار",
        "مصاحبه مشتری",
    ),
    "business": (
        "business",
        "startup",
        "small business",
        "کسب و کار",
        "کسب‌وکار",
        "استارتاپ",
    ),
    "planning": (
        "business plan",
        "launch plan",
        "برنامه کسب و کار",
        "برنامه کسب‌وکار",
        "برنامه راه اندازی",
        "برنامه راه‌اندازی",
    ),
    "finance": (
        "finance",
        "financial",
        "investment",
        "سرمایه",
        "مالی",
        "سرمایه گذاری",
        "سرمایه‌گذاری",
    ),
    "support": (
        "support request",
        "customer support",
        "help center",
        "account error",
        "account issue",
        "پشتیبانی",
        "خطای حساب",
        "مشکل حساب",
    ),
}

JURISDICTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "AU": ("australia", "australian", "استرالیا"),
    "CA": ("canada", "canadian", "کانادا"),
    "IR": ("iran", "iranian", "ایران", "ایرانی"),
    "US": (
        "united states",
        "united states of america",
        "usa",
        "american",
        "آمریکا",
        "ایالات متحده",
    ),
    "EU": (
        "european union",
        "europe",
        "germany",
        "france",
        "italy",
        "spain",
        "netherlands",
        "اتحادیه اروپا",
        "اروپا",
        "آلمان",
        "فرانسه",
        "ایتالیا",
        "اسپانیا",
        "هلند",
    ),
}

STRUCTURED_JURISDICTION_CODES: dict[str, str] = {
    "au": "AU",
    "aus": "AU",
    "australia": "AU",
    "ca": "CA",
    "can": "CA",
    "canada": "CA",
    "ir": "IR",
    "irn": "IR",
    "iran": "IR",
    "us": "US",
    "usa": "US",
    "united states": "US",
    "eu": "EU",
    "european union": "EU",
}

GEO_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "country",
        "country code",
        "country_code",
        "geography",
        "jurisdiction",
        "location",
        "market",
        "market country",
        "market_country",
        "target country",
        "target_country",
    }
)

ACCESS_BADGES: dict[AccessType, LocalizedText] = {
    "free_keyless": LocalizedText("رایگان، بدون حساب", "Free — no account"),
    "free_account": LocalizedText("رایگان، نیازمند حساب", "Free — account required"),
    "freemium": LocalizedText(
        "فریمیوم؛ امکانات پولی اختیاری", "Freemium — optional paid features"
    ),
    "transaction_fee": LocalizedText(
        "ثبت‌نام رایگان؛ دارای کارمزد تراکنش", "Free signup — transaction fees apply"
    ),
    "unknown": LocalizedText("هزینه تأیید نشده", "Cost not verified"),
}

# Specialized resources need an anchor intent; a generic shared tag such as
# "marketing" must not surface an unrelated local-business or compliance tool.
RESOURCE_TRIGGER_TAGS: dict[str, frozenset[str]] = {
    "github_new_repo": frozenset({"technology", "software", "portfolio"}),
    "microsoft_learn": frozenset({"technology", "software"}),
    "google_business_profile": frozenset({"local"}),
    "search_console": frozenset({"website"}),
    "cisa_kev": frozenset({"cyber"}),
    "unido_statistics": frozenset({"manufacturing", "industry"}),
    "eu_access2markets": frozenset({"trade"}),
    "ted_tenders": frozenset({"procurement"}),
    "sec_edgar": frozenset({"company", "finance"}),
    "openfda": frozenset({"food", "health"}),
    "australia_fair_work": frozenset({"employment", "hr"}),
    "canada_foreign_credentials": frozenset({"credential", "nursing"}),
    "upwork_profile": frozenset({"freelance"}),
}


def normalize_locale(value: Any) -> Locale:
    """Normalize all presentation output to the English product locale."""
    return "en"


def _normalize_match_text(value: Any) -> str:
    text = (
        str(value or "")
        .casefold()
        .translate(
            str.maketrans({"\u200c": " ", "\u200d": " ", "ي": "ی", "ك": "ک", "ـ": " "})
        )
    )
    text = re.sub(r"[_/\-–—]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_term(normalized_text: str, term: str) -> bool:
    """Match complete tokens/phrases, never arbitrary substrings (e.g. ai/email)."""

    normalized_term = _normalize_match_text(term)
    if not normalized_term:
        return False
    expression = re.escape(normalized_term).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![\w]){expression}(?![\w])", normalized_text) is not None


def _flatten_text(value: Any, *, max_items: int = 80, max_chars: int = 12_000) -> str:
    pieces: list[str] = []
    seen: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > 4 or len(pieces) >= max_items or sum(map(len, pieces)) >= max_chars:
            return
        if item is None:
            return
        if isinstance(item, str):
            pieces.append(item[:2_000])
            return
        if isinstance(item, (int, float, bool)):
            pieces.append(str(item))
            return
        if isinstance(item, Mapping):
            marker = id(item)
            if marker in seen:
                return
            seen.add(marker)
            for nested in list(item.values())[:20]:
                visit(nested, depth + 1)
            return
        if isinstance(item, (list, tuple, set, frozenset)):
            marker = id(item)
            if marker in seen:
                return
            seen.add(marker)
            for nested in list(item)[:20]:
                visit(nested, depth + 1)

    visit(value, 0)
    return " ".join(pieces)[:max_chars]


def _combined_signal_text(
    query: str,
    steps: list[Any] | None,
    context: Any,
    facts: Any,
) -> str:
    return _normalize_match_text(
        " ".join(
            part
            for part in (
                str(query or "")[:4_000],
                _flatten_text(steps or []),
                _flatten_text(context),
                _flatten_text(facts),
            )
            if part
        )
    )


def infer_explicit_resource_ids(
    query: str,
    steps: list[Any] | None = None,
    *,
    context: Any = None,
    facts: Any = None,
) -> set[str]:
    """Return catalog resources explicitly named in the bounded user context."""

    text = _combined_signal_text(query, steps, context, facts)
    return {
        resource_id
        for resource_id, patterns in EXPLICIT_RESOURCE_PATTERNS.items()
        if any(_contains_term(text, pattern) for pattern in patterns)
    }


def _structured_jurisdictions(value: Any) -> set[str]:
    jurisdictions: set[str] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > 4:
            return
        if isinstance(item, Mapping):
            for raw_key, nested in list(item.items())[:30]:
                key = _normalize_match_text(raw_key)
                if key in GEO_CONTEXT_KEYS:
                    normalized_value = _normalize_match_text(nested)
                    code = STRUCTURED_JURISDICTION_CODES.get(normalized_value)
                    if code:
                        jurisdictions.add(code)
                    for candidate, patterns in JURISDICTION_PATTERNS.items():
                        if any(
                            _contains_term(normalized_value, term) for term in patterns
                        ):
                            jurisdictions.add(candidate)
                visit(nested, depth + 1)
        elif isinstance(item, (list, tuple, set, frozenset)):
            for nested in list(item)[:30]:
                visit(nested, depth + 1)

    visit(value, 0)
    return jurisdictions


def infer_jurisdictions(
    query: str,
    steps: list[Any] | None = None,
    *,
    context: Any = None,
    facts: Any = None,
) -> set[str]:
    text = _combined_signal_text(query, steps, context, facts)
    jurisdictions = _structured_jurisdictions(context) | _structured_jurisdictions(
        facts
    )
    for code, patterns in JURISDICTION_PATTERNS.items():
        if any(_contains_term(text, term) for term in patterns):
            jurisdictions.add(code)
    return jurisdictions


def infer_resource_tags(
    query: str,
    tier: Tier,
    steps: list[Any] | None = None,
    *,
    context: Any = None,
    facts: Any = None,
) -> set[str]:
    """Infer only explicit intents; audience tier never fabricates an intent."""

    if tier not in {"B2C", "B2B"}:
        raise ValueError("tier must be B2C or B2B")
    text = _combined_signal_text(query, steps, context, facts)
    tags = {
        tag
        for tag, patterns in TAG_PATTERNS.items()
        if any(_contains_term(text, pattern) for pattern in patterns)
    }
    if "technology" in tags and _contains_term(text, "security"):
        tags.add("cyber")
    return tags


def _localized_resource(
    item: Resource,
    locale: Locale,
    *,
    matched_tags: set[str],
    target_jurisdictions: set[str],
) -> dict[str, Any]:
    host = (urlsplit(item.url).hostname or "").casefold()
    data: dict[str, Any] = {
        "resource_id": item.resource_id,
        "name": item.name.get(locale),
        "url": item.url,
        "domain": host,
        "purpose": item.purpose.get(locale),
        "first_action": item.first_action.get(locale),
        "access_note": item.access_note.get(locale),
        "access_type": item.access_type,
        "access_badge": ACCESS_BADGES[item.access_type].get(locale),
        "free_access": item.free_access,
        "fee_disclosure_required": item.access_type in {"freemium", "transaction_fee"},
        "limitation": item.limitation.get(locale),
        "official": item.official,
        "requires_account": item.requires_account,
        "jurisdiction": item.jurisdiction,
        "jurisdiction_match": item.jurisdiction in target_jurisdictions,
        "matched_tags": sorted(item.tags & matched_tags),
        "tags": sorted(item.tags),
        "verified_at": item.verified_at,
        "review_after": item.review_after,
    }
    if item.support_url and item.contact_channel:
        data["support_url"] = item.support_url
        data["contact_channel"] = item.contact_channel
    return data


def select_resources(
    query: str,
    tier: Tier,
    locale: Locale,
    steps: list[Any] | None = None,
    limit: int = 6,
    *,
    context: Any = None,
    facts: Any = None,
) -> list[dict[str, Any]]:
    locale = "en"
    tags = infer_resource_tags(query, tier, steps, context=context, facts=facts)
    explicit_resource_ids = infer_explicit_resource_ids(
        query, steps, context=context, facts=facts
    )
    target_jurisdictions = infer_jurisdictions(
        query, steps, context=context, facts=facts
    )
    candidates: list[tuple[int, Resource]] = []
    for item in RESOURCE_CATALOG:
        if tier not in item.tiers:
            continue
        # Execution recommendations are strictly zero-fee. Fee-bearing entries
        # can remain in the catalog only so their status is never hidden.
        if item.access_type not in {"free_keyless", "free_account"}:
            continue
        if (
            item.jurisdiction != "GLOBAL"
            and item.jurisdiction not in target_jurisdictions
        ):
            continue
        explicit_match = item.resource_id in explicit_resource_ids
        overlap = item.tags & tags
        if not overlap and not explicit_match:
            continue
        trigger_tags = RESOURCE_TRIGGER_TAGS.get(item.resource_id)
        if trigger_tags and not explicit_match and not trigger_tags & tags:
            continue
        geography_score = 20 if item.jurisdiction in target_jurisdictions else 0
        official_score = 2 if item.official else 0
        explicit_score = 100 if explicit_match else 0
        candidates.append(
            (
                explicit_score
                + len(overlap) * 10
                + geography_score
                + official_score,
                item,
            )
        )

    ranked = sorted(candidates, key=lambda pair: (-pair[0], pair[1].resource_id))
    selected: list[Resource] = []
    used_domains: set[str] = set()
    cap = max(1, min(6, int(limit or 1)))
    for _, item in ranked:
        domain = (urlsplit(item.url).hostname or "").casefold()
        if domain in used_domains:
            continue
        selected.append(item)
        used_domains.add(domain)
        if len(selected) >= cap:
            break
    return [
        _localized_resource(
            item,
            locale,
            matched_tags=tags,
            target_jurisdictions=target_jurisdictions,
        )
        for item in selected
    ]


def _template(
    template_id: str,
    channel: str,
    recipient_role_fa: str,
    recipient_role_en: str,
    subject_fa: str,
    subject_en: str,
    body_fa: str,
    body_en: str,
    locale: Locale,
    send_when_fa: str,
    send_when_en: str,
    *,
    intent_tags: set[str],
    source_resource: dict[str, Any] | None = None,
    contact_url: str | None = None,
    contact_channel: str | None = None,
) -> dict[str, Any]:
    subject = subject_en if locale == "en" else subject_fa
    body = body_en if locale == "en" else body_fa
    customize_fields = list(
        dict.fromkeys(re.findall(r"\[[^\[\]\r\n]{1,80}\]", f"{subject}\n{body}"))
    )
    template: dict[str, Any] = {
        "template_id": template_id,
        "channel": channel,
        "recipient_role": recipient_role_en if locale == "en" else recipient_role_fa,
        "subject": subject,
        "body": body,
        "customize_fields": customize_fields,
        "send_when": send_when_en if locale == "en" else send_when_fa,
        "do_not_send_if": (
            "Do not send confidential, credential, payment-card or unnecessary personal data."
            if locale == "en"
            else "اطلاعات محرمانه، رمز، اطلاعات کارت یا داده شخصی غیرضروری را ارسال نکنید."
        ),
        "generated_locally": True,
        "auto_send": False,
        "intent_tags": sorted(intent_tags),
    }
    if source_resource:
        template["source_resource_id"] = source_resource.get("resource_id")
        template["source_url"] = source_resource.get("url")
    if contact_url and contact_channel and is_allowlisted_resource_url(contact_url):
        template["contact_url"] = contact_url
        template["contact_channel"] = contact_channel
    return template


def _first_resource_with_tags(
    resources: list[dict[str, Any]], wanted: set[str]
) -> dict[str, Any] | None:
    for resource in resources:
        if set(resource.get("tags") or []) & wanted:
            return resource
    return None


def build_outreach_templates(
    tier: Tier,
    locale: Locale,
    *,
    intent_tags: set[str] | None = None,
    resources: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Create only templates justified by an explicit intent and selected source."""

    locale = "en"
    if tier not in {"B2C", "B2B"}:
        raise ValueError("tier must be B2C or B2B")
    tags = set(intent_tags or set())
    selected_resources = list(resources or [])
    templates: list[dict[str, Any]] = []

    canada_resource = next(
        (
            item
            for item in selected_resources
            if item.get("resource_id") == "canada_foreign_credentials"
        ),
        None,
    )
    australia_resource = next(
        (
            item
            for item in selected_resources
            if item.get("resource_id") == "australia_fair_work"
        ),
        None,
    )
    supply_resource = _first_resource_with_tags(
        selected_resources, {"manufacturing", "procurement", "supply", "trade"}
    )
    validation_resource = _first_resource_with_tags(
        selected_resources, {"demand", "market_research", "validation"}
    )

    if canada_resource and tags & {"credential", "nursing"}:
        templates.append(
            _template(
                "credential_requirements_request",
                "email_or_contact_form",
                "نهاد تنظیم‌گر حرفه در استان/قلمرو مقصد",
                "Profession regulator in the destination province/territory",
                "درخواست تأیید مراحل مدرک [حرفه] در [استان/قلمرو]",
                "Please confirm [profession] credential steps in [province/territory]",
                "سلام،\n\nمن مدرک [حرفه] را در [کشور محل تحصیل] گرفته‌ام و قصد فعالیت در [استان/قلمرو] را دارم. لطفاً مسیر رسمی را تأیید کنید: نهاد ارزیاب، مدارک و ترجمه‌های لازم، الزامات زبان، آزمون/دوره تکمیلی، همه هزینه‌های اجباری و زمان تقریبی هر مرحله. وضعیت فعلی من: [وضعیت مهاجرت/اقامت]. لطفاً فقط به صفحه رسمی و فرم درست ارجاع دهید و مشخص کنید کدام اطلاعات ممکن است تغییر کند.\n\nسپاس",
                "Hello,\n\nI earned my [profession] credential in [country of education] and intend to practise in [province/territory]. Please confirm the official route: assessment body, required documents and translations, language requirements, exams or bridging, every mandatory fee, and typical timing for each stage. My current status is [immigration/residency status]. Please link only to the official page or form and identify which details may change.\n\nThank you,",
                locale,
                "پس از تعیین حرفه و استان/قلمرو مقصد؛ پیش از پرداخت به ارزیاب یا دوره آموزشی.",
                "After choosing the profession and destination province/territory, before paying an assessor or training provider.",
                intent_tags=tags & {"credential", "nursing", "health", "employment"},
                source_resource=canada_resource,
            )
        )
    elif australia_resource and tags & {"employment", "hr"}:
        templates.append(
            _template(
                "workplace_rule_clarification",
                "phone_or_contact_form",
                "راهنمای رسمی روابط کار",
                "Official workplace-relations guidance service",
                "تأیید قاعده [موضوع استخدام] برای [نوع رابطه کاری]",
                "Confirm [employment topic] for [work arrangement]",
                "سلام، برای ثبت دقیق سیاست منابع انسانی درباره [موضوع استخدام] تماس می‌گیرم. محل کار در [ایالت/قلمرو] است، نوع رابطه [تمام‌وقت/پاره‌وقت/موقت/پیمانکار] و award یا agreement احتمالی [عنوان] است. برداشت فعلی ما [برداشت] و تاریخ اجرای تصمیم [تاریخ] است. لطفاً منبع رسمی، نسخه/تاریخ قاعده و مرز اطلاعات عمومی با مشاوره تخصصی را مشخص کنید.",
                "Hello, I am checking an HR policy concerning [employment topic]. The workplace is in [state/territory], the arrangement is [full-time/part-time/casual/contractor], and the likely award or agreement is [title]. Our current interpretation is [interpretation], with a decision date of [date]. Please identify the official source, the rule version/date, and where general information ends and specialist advice is needed.",
                locale,
                "پس از مشخص‌کردن نوع رابطه کاری، محل و award/agreement احتمالی.",
                "After identifying the work arrangement, location and likely award/agreement.",
                intent_tags=tags & {"employment", "hr", "compliance", "regulation"},
                source_resource=australia_resource,
                contact_url=australia_resource.get("support_url"),
                contact_channel=australia_resource.get("contact_channel"),
            )
        )
    elif supply_resource and tags & {
        "manufacturing",
        "procurement",
        "supply",
        "trade",
    }:
        templates.append(
            _template(
                "supplier_rfq",
                "email",
                "مدیر فروش یا تأمین‌کننده",
                "Supplier sales manager",
                "درخواست قیمت و شرایط قابل‌مقایسه برای [کالا/خدمت]",
                "Comparable quotation request for [product/service]",
                "سلام [نام]،\n\nبرای ارزیابی [کالا/خدمت] لطفاً قیمت واحد، حداقل سفارش، زمان تحویل، اعتبار پیشنهاد، شرایط پرداخت، Incoterm، گواهی‌ها و سیاست نمونه/مرجوعی را جداگانه اعلام کنید. مقصد [مکان] و حجم آزمایشی [مقدار] است. لطفاً موارد خارج از قیمت و هر محدودیت ظرفیت را نیز شفاف کنید.\n\nبا احترام",
                "Hello [Name],\n\nTo evaluate [product/service], please itemize unit price, minimum order, lead time, quote validity, payment terms, Incoterm, certifications, and sample/return policy. Destination is [location] and pilot quantity is [quantity]. Please also disclose exclusions and capacity constraints.\n\nRegards,",
                locale,
                "بعد از تعریف مشخصات، حجم آزمایشی و معیار مقایسه؛ هم‌زمان برای حداقل سه تأمین‌کننده.",
                "After defining specifications, pilot quantity and comparison criteria; send consistently to at least three suppliers.",
                intent_tags=tags & {"manufacturing", "procurement", "supply", "trade"},
                source_resource=supply_resource,
            )
        )
    elif validation_resource and tags & {"validation", "demand", "market_research"}:
        templates.append(
            _template(
                "customer_discovery",
                "email_or_message",
                "مشتری بالقوه",
                "Potential customer",
                "یک گفت‌وگوی کوتاه درباره [مسئله] — بدون فروش",
                "Short research conversation about [problem] — no sales pitch",
                "سلام [نام]،\n\nدر حال بررسی این هستم که افراد چگونه با [مسئله] روبه‌رو می‌شوند. قصد فروش در این تماس ندارم. آیا این هفته ۱۵ دقیقه وقت دارید تا درباره آخرین باری که این مسئله رخ داد، راه‌حل فعلی و هزینه/زمان آن صحبت کنیم؟ پاسخ شما فقط برای سنجش مسئله استفاده می‌شود.\n\nسپاس",
                "Hello [Name],\n\nI am researching how people handle [problem]. This is not a sales call. Would you have 15 minutes this week to discuss the last time it happened, your current workaround, and its time or cost? Your response will only be used to validate the problem.\n\nThank you,",
                locale,
                "قبل از ساخت یا خرید ابزار؛ برای پنج نفر از جامعه هدف با یک متن یکسان.",
                "Before building or buying tools; send consistently to five people in the target segment.",
                intent_tags=tags & {"validation", "demand", "market_research"},
                source_resource=validation_resource,
            )
        )

    if "support" in tags:
        support_resource = next(
            (
                item
                for item in selected_resources
                if item.get("support_url") and item.get("contact_channel")
            ),
            None,
        )
        if support_resource:
            templates.append(
                _template(
                    "support_escalation",
                    str(support_resource.get("contact_channel") or "help_center"),
                    "پشتیبانی یا مدیر حساب",
                    "Support or account manager",
                    "درخواست بررسی مستند برای [مسئله]",
                    "Evidence-based review request: [problem]",
                    "سلام [نام]،\n\nبرای [مسئله] به بررسی شما نیاز دارم. اقدام‌های انجام‌شده: [اقدام‌ها]. نتیجه یا خطای دقیق: [مدرک]. درخواست مشخص من [درخواست دقیق] است. اگر این مسیر درست نیست، لطفاً بخش یا سند رسمی مناسب را معرفی کنید. مهلت تصمیم من [مهلت] است.\n\nسپاس",
                    "Hello [Name],\n\nI need your review of [problem]. Actions already taken: [actions]. Exact result or error: [evidence]. My specific request is [specific request]. If this is not the right route, please point me to the correct team or official documentation. My decision deadline is [deadline].\n\nThank you,",
                    locale,
                    "وقتی مدرک خطا، اقدام‌های قبلی و یک درخواست مشخص آماده است.",
                    "When the exact evidence, prior actions and one specific request are ready.",
                    intent_tags={"support"},
                    source_resource=support_resource,
                    contact_url=support_resource.get("support_url"),
                    contact_channel=support_resource.get("contact_channel"),
                )
            )
    return templates[:2]


def build_execution_kit(
    query: str,
    tier: Tier,
    lang_code: str = "en",
    action_steps: list[Any] | None = None,
    *,
    context: Any = None,
    facts: Any = None,
    locale: str | None = None,
) -> dict[str, Any]:
    resolved_locale = normalize_locale(locale or lang_code)
    intents = infer_resource_tags(
        query, tier, action_steps, context=context, facts=facts
    )
    jurisdictions = infer_jurisdictions(
        query, action_steps, context=context, facts=facts
    )
    resources = select_resources(
        query,
        tier,
        resolved_locale,
        action_steps,
        context=context,
        facts=facts,
    )
    templates = build_outreach_templates(
        tier,
        resolved_locale,
        intent_tags=intents,
        resources=resources,
    )
    if resolved_locale == "en":
        contact_action = (
            "Customize the relevant template and send it manually only to qualified recipients."
            if templates
            else "Complete one independent evidence check; no outreach is suggested without a relevant intent and route."
        )
        contact_evidence = (
            "Manually sent messages and a response log"
            if templates
            else "A second dated source note or observation"
        )
        checklist = [
            {
                "sequence": 1,
                "title": "Define the test",
                "action": "Write one decision, one measurable assumption and one stop condition.",
                "timebox": "20 minutes",
                "evidence": "A dated one-page test brief",
                "estimated_cost": "$0",
            },
            {
                "sequence": 2,
                "title": "Open the primary source",
                "action": resources[0]["first_action"]
                if resources
                else "Collect three independent observations from an official source.",
                "timebox": "30–45 minutes",
                "evidence": "Links, dates and three recorded observations",
                "estimated_cost": "$0",
            },
            {
                "sequence": 3,
                "title": "Run the next evidence action",
                "action": contact_action,
                "timebox": "45 minutes",
                "evidence": contact_evidence,
                "estimated_cost": "$0",
            },
            {
                "sequence": 4,
                "title": "Hold the decision gate",
                "action": "Compare evidence with the success and stop thresholds before spending capital.",
                "timebox": "15 minutes",
                "evidence": "Proceed, revise or stop decision with rationale",
                "estimated_cost": "$0",
            },
        ]
        guardrails = [
            "Every recommended resource is free/keyless or free-account; freemium, transaction-fee and unknown-cost catalog entries are excluded from recommendations.",
            "This enrichment performs no model call, external API call or automatic message send.",
            "Links are selected from a local allowlisted catalog, never invented by the model.",
            "Do not send secrets or personal data; messages are templates and are never sent automatically.",
            "Verify jurisdiction, eligibility and current terms before committing money.",
        ]
    else:
        contact_action = (
            "الگوی مرتبط را شخصی‌سازی کنید و فقط به‌صورت دستی برای مخاطب واجد شرایط بفرستید."
            if templates
            else "یک بررسی مستقل دیگر ثبت کنید؛ بدون intent و مسیر تماس مرتبط، هیچ نامه‌ای پیشنهاد نمی‌شود."
        )
        contact_evidence = (
            "پیام‌های دستی ارسال‌شده و دفتر ثبت پاسخ"
            if templates
            else "یادداشت تاریخ‌دار از منبع یا مشاهده مستقل دوم"
        )
        checklist = [
            {
                "sequence": 1,
                "title": "تعریف آزمون",
                "action": "یک تصمیم، یک فرض قابل‌اندازه‌گیری و یک شرط توقف را بنویسید.",
                "timebox": "۲۰ دقیقه",
                "evidence": "برگه یک‌صفحه‌ای تاریخ‌دار",
                "estimated_cost": "۰ دلار",
            },
            {
                "sequence": 2,
                "title": "بازکردن منبع اصلی",
                "action": resources[0]["first_action"]
                if resources
                else "سه مشاهده مستقل را از یک منبع رسمی ثبت کنید.",
                "timebox": "۳۰ تا ۴۵ دقیقه",
                "evidence": "لینک، تاریخ و سه مشاهده ثبت‌شده",
                "estimated_cost": "۰ دلار",
            },
            {
                "sequence": 3,
                "title": "اجرای اقدام شواهد بعدی",
                "action": contact_action,
                "timebox": "۴۵ دقیقه",
                "evidence": contact_evidence,
                "estimated_cost": "۰ دلار",
            },
            {
                "sequence": 4,
                "title": "دروازه تصمیم",
                "action": "پیش از خرج سرمایه، شواهد را با معیار موفقیت و توقف مقایسه کنید.",
                "timebox": "۱۵ دقیقه",
                "evidence": "تصمیم ادامه، اصلاح یا توقف همراه دلیل",
                "estimated_cost": "۰ دلار",
            },
        ]
        guardrails = [
            "فقط منابع رایگانِ بدون حساب یا رایگانِ نیازمند حساب پیشنهاد می‌شوند؛ منابع فریمیوم، کارمزدی و با هزینه نامشخص از پیشنهاد حذف‌اند.",
            "این غنی‌سازی هیچ فراخوانی مدل، API بیرونی یا ارسال خودکار پیام انجام نمی‌دهد.",
            "لینک‌ها فقط از کاتالوگ محلی مجاز انتخاب می‌شوند و مدل آن‌ها را اختراع نمی‌کند.",
            "رمز یا داده شخصی نفرستید؛ نامه‌ها فقط الگو هستند و خودکار ارسال نمی‌شوند.",
            "پیش از تعهد مالی، حوزه قضایی، واجدشرایط‌بودن و شرایط جاری را بررسی کنید.",
        ]
    return {
        "locale": resolved_locale,
        "generated_without_ai_call": True,
        "additional_model_calls": 0,
        "external_api_cost_usd": 0,
        "external_api_calls": 0,
        "query_shared_with_resources": False,
        "detected_intents": sorted(intents),
        "target_jurisdictions": sorted(jurisdictions),
        "selection_policy": {
            "recommended_access_types": ["free_keyless", "free_account"],
            "excluded_access_types": ["freemium", "transaction_fee", "unknown"],
            "exact_host_allowlist": True,
            "jurisdiction_aware": True,
        },
        "resources": resources,
        "first_24_hours": checklist,
        "outreach_templates": templates,
        "guardrails": guardrails,
        "verified_at": VERIFIED_AT,
        "review_after": min(
            (str(item.get("review_after")) for item in resources),
            default=DEFAULT_REVIEW_AFTER,
        ),
    }


def _validate_allowlisted_url(url: str, resource_id: str) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    try:
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError(f"Unsafe resource URL port: {resource_id}") from exc
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or port is not None
    ):
        raise RuntimeError(f"Unsafe resource URL: {resource_id}")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise RuntimeError(f"IP resource URL is forbidden: {resource_id}")
    if (
        host not in ALLOWED_RESOURCE_HOSTS
        or host == "localhost"
        or host.endswith((".local", ".internal", ".localhost"))
    ):
        raise RuntimeError(f"Unallowlisted resource host: {resource_id}")


def is_allowlisted_resource_url(url: str) -> bool:
    try:
        _validate_allowlisted_url(url, "candidate")
    except (RuntimeError, ValueError):
        return False
    return True


def validate_resource_catalog(catalog: Iterable[Resource] | None = None) -> None:
    identifiers: set[str] = set()
    for item in RESOURCE_CATALOG if catalog is None else catalog:
        if item.resource_id in identifiers:
            raise RuntimeError(f"Duplicate resource id: {item.resource_id}")
        identifiers.add(item.resource_id)
        _validate_allowlisted_url(item.url, item.resource_id)
        if item.access_type not in ACCESS_TYPES or item.access_type == "unknown":
            raise RuntimeError(f"Unverified access type: {item.resource_id}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item.verified_at):
            raise RuntimeError(f"Invalid verified_at: {item.resource_id}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item.review_after):
            raise RuntimeError(f"Invalid review_after: {item.resource_id}")
        if item.review_after < item.verified_at:
            raise RuntimeError(
                f"review_after predates verification: {item.resource_id}"
            )
        if bool(item.support_url) != bool(item.contact_channel):
            raise RuntimeError(f"Incomplete support metadata: {item.resource_id}")
        if item.support_url:
            _validate_allowlisted_url(item.support_url, f"{item.resource_id}:support")
        if item.contact_channel and item.contact_channel not in CONTACT_CHANNELS:
            raise RuntimeError(f"Invalid contact channel: {item.resource_id}")


validate_resource_catalog()


__all__ = [
    "ALLOWED_RESOURCE_HOSTS",
    "ACCESS_TYPES",
    "EXPLICIT_RESOURCE_PATTERNS",
    "RESOURCE_BY_ID",
    "RESOURCE_CATALOG",
    "VERIFIED_AT",
    "build_execution_kit",
    "build_outreach_templates",
    "infer_explicit_resource_ids",
    "infer_jurisdictions",
    "infer_resource_tags",
    "is_allowlisted_resource_url",
    "normalize_locale",
    "select_resources",
    "validate_resource_catalog",
]
