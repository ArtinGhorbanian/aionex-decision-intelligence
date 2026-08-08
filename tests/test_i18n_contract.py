from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "static" / "script.js").read_text(encoding="utf-8")
I18N = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")
STYLE = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
PERSIAN = re.compile(r"[\u0600-\u06ff]")


class _VisibleCopyParser(HTMLParser):
    translatable_attributes = {
        "aria-label",
        "title",
        "placeholder",
        "data-query-preset",
        "data-follow-up-prompt",
        "content",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self._ignored_depth += 1
        if self._ignored_depth:
            return
        for name, value in attrs:
            if name in self.translatable_attributes and value:
                self.values.append(value.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.values.append(data.strip())


def test_server_and_dynamic_ui_are_english_only() -> None:
    assert '<html lang="en" dir="ltr">' in HTML
    assert "/static/i18n.js" not in HTML
    assert PERSIAN.search(HTML) is None
    assert PERSIAN.search(SCRIPT) is None
    assert PERSIAN.search(I18N) is None
    assert PERSIAN.search(STYLE) is None

    parser = _VisibleCopyParser()
    parser.feed(HTML)
    assert len(parser.values) >= 100
    assert all(PERSIAN.search(value) is None for value in parser.values)
    assert "AIONEX" in HTML
    assert "OMNI<span>" not in HTML
    assert "Omni AI" not in SCRIPT


def test_locale_switching_and_persistence_are_removed() -> None:
    forbidden = (
        "data-locale-option",
        "data-locale-cycle",
        "language-switch",
        "mobile-language-toggle",
        "omni-locale-v1",
        "setInterfaceLocale",
        "bindLanguageControls",
        "omni:localechange",
        "state.locale",
    )
    assert all(token not in HTML + SCRIPT + I18N for token in forbidden)
    assert "html[dir=" not in STYLE
    assert "html[lang=" not in STYLE


def test_api_requests_are_hard_locked_to_english() -> None:
    assert "const APP_LOCALE = 'en';" in SCRIPT
    assert "'Accept-Language': APP_LOCALE" in SCRIPT
    assert SCRIPT.count("locale: APP_LOCALE") >= 4
    assert "translations.en" in SCRIPT
    assert "i18n.en" in SCRIPT


def test_progressive_disclosure_result_tabs_and_execution_kit_are_wired() -> None:
    for element_id in (
        "hero-toggle-btn",
        "context-rail-toggle",
        "context-rail-content",
    ):
        assert f'id="{element_id}"' in HTML
    assert "role: 'tablist'" in SCRIPT
    assert "setAttribute('role', 'tabpanel')" in SCRIPT
    assert "function renderExecutionKit" in SCRIPT
    assert "safeExternalUrl" in SCRIPT
    assert "parsed.protocol !== 'https:'" in SCRIPT
    assert "safeExternalUrl(stream.source_url)" in SCRIPT
    assert "intel-source-link" in SCRIPT
    assert "sourceLink.rel = 'noopener noreferrer'" in SCRIPT
    assert "support_url" in SCRIPT
    assert "execution.support" in SCRIPT
    assert "'/api/analyses/' + encodeURIComponent(entry.id)" in SCRIPT
    assert "vault.hydrated" in SCRIPT
    assert "vault.unavailable" in SCRIPT
    assert "function hasCompleteStoredAnalysis" in SCRIPT
    assert "noopener noreferrer" in SCRIPT
    assert "data.execution_kit" in SCRIPT


def test_health_copy_reflects_the_real_health_endpoint() -> None:
    for element_id in ("system-state", "system-state-label", "system-state-detail"):
        assert f'id="{element_id}"' in HTML
    assert 'data-status="checking"' in HTML
    assert "function loadHealthStatus" in SCRIPT
    assert "apiRequest('/api/health'" in SCRIPT
    assert "health.ai_ready" in SCRIPT
    assert "health.storage_ready" in SCRIPT
    assert "health.demo_mode" in SCRIPT
    assert "Engine ready" not in HTML


def test_completed_analysis_status_and_coverage_copy_are_truthful() -> None:
    assert 'id="analysis-status-label"' in HTML
    assert "refs.analysisStatusLabel = byId('analysis-status-label')" in SCRIPT
    assert "busy ? 'Building your analysis' : 'Analysis ready'" in SCRIPT
    assert "<span>Estimated</span>" in HTML
    assert "<span>Preparing</span>" not in HTML


def test_mobile_drawer_is_inert_and_contains_focus() -> None:
    assert "refs.sidebar.inert = mobile && !expanded" in SCRIPT
    assert "refs.sidebar.setAttribute('aria-hidden'" in SCRIPT
    assert "sidebarFocusableElements" in SCRIPT
    assert "event.key === 'Tab'" in SCRIPT
    assert "event.key === 'Escape'" in SCRIPT
    assert "refs.mobileNavToggle.focus" in SCRIPT
    assert "visibility: hidden" in STYLE
    assert "pointer-events: none" in STYLE


def test_accessibility_and_ltr_layout_contracts() -> None:
    assert "translate(-50%, -160%)" in STYLE
    assert "translate(-50%, -50%)" in STYLE
    assert "translateX(-50%)" in STYLE
    assert "min-height: 2.75rem" in STYLE
    assert "safe-area-inset-top" in STYLE
    assert "safe-area-inset-right" in STYLE
    assert "safe-area-inset-bottom" in STYLE
    assert "safe-area-inset-left" in STYLE
    assert "prefers-reduced-motion: reduce" in STYLE
    assert 'dir="auto"' in HTML
    assert 'aria-live="off"' in HTML
    assert "border-inline-start: 3px solid" not in STYLE
    assert "background-clip: text" not in STYLE
    assert "transition: max-height" not in STYLE
    touch_target_block = STYLE[STYLE.index(".query-presets button,", STYLE.index("/* Accessibility baseline")) :]
    for selector in (
        ".query-presets button",
        ".follow-up-suggestions button",
        ".filter-chip",
        ".copy-btn",
        ".result-tab",
        ".secondary-button--compact",
        ".action-step-controls .deep-dive-trigger",
    ):
        assert selector in touch_target_block
    assert "min-height: 2.75rem" in touch_target_block
