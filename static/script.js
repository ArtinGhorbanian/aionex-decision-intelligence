(() => {
    'use strict';

    const INPUT_LIMIT = 3000;
    const FOLLOW_UP_LIMIT = 2000;
    const APP_LOCALE = 'en';
    const EN_MESSAGES = Object.freeze({
        'hero.expand': 'Show full introduction',
        'hero.collapse': 'Collapse introduction',
        'context.title': 'Decision context center',
        'context.subtitle': 'Context, saved information, goals, and usage in one organized view',
        'context.expand': 'Open the decision context center',
        'context.collapse': 'Close the decision context center',
        'vault.hydrating': 'Loading the latest stored analysis details…',
        'vault.hydrated': 'The full stored analysis was restored without an additional model call.',
        'vault.fallback': 'The detailed record was unavailable; the stored summary is shown.',
        'vault.unavailable': 'The full stored analysis is temporarily unavailable. Please try again shortly.',
        'result.tabs.label': 'Analysis sections',
        'result.tab.overview': 'Overview',
        'result.tab.action': 'Action plan',
        'result.tab.evidence': 'Evidence & data',
        'result.tab.risks': 'Risks & scenarios',
        'execution.title': 'Practical execution kit',
        'execution.resources': 'Recommended websites and resources',
        'execution.outreach': 'Outreach and support templates',
        'execution.free': 'Free',
        'execution.freeAccount': 'Free account',
        'execution.freemium': 'Limited free tier',
        'execution.transactionFee': 'Transaction fees apply',
        'execution.official': 'Official source',
        'execution.open': 'Open resource',
        'execution.support': 'Open official support',
        'execution.contact': 'Contact method',
        'execution.copy': 'Copy text',
        'execution.copied': 'The ready-to-use text was copied to your clipboard.',
        'execution.copyFailed': 'Your browser did not allow this text to be copied.',
        'execution.instructions': 'What to do',
        'execution.why': 'Why it is recommended',
        'execution.when': 'When to use it',
        'execution.recipient': 'Recipient',
        'execution.subject': 'Subject',
        'execution.message': 'Suggested message',
        'execution.channel': 'Channel',
        'execution.invalidUrl': 'This resource address is not valid.',
        'execution.zeroCost': 'Execution-kit external API cost: $0',
        'execution.noModelCall': 'Execution kit adds no model call',
        'execution.first24': 'Your first 24 hours',
        'execution.guardrails': 'Execution safeguards',
        'execution.purpose': 'What this resource is for',
        'execution.access': 'Access notes',
        'execution.limitation': 'Important limitation',
        'execution.accountRequired': 'Account required',
        'execution.noAccount': 'No account required',
        'execution.jurisdiction': 'Jurisdiction',
        'execution.verified': 'Last reviewed',
        'execution.reviewAfter': 'Next source review',
        'execution.timebox': 'Suggested timebox',
        'execution.evidence': 'Completion evidence',
        'execution.cost': 'Estimated external cost',
        'execution.customize': 'Fields to customize',
        'execution.doNotSend': 'Information not to send',
    });
    const translateEnglish = (value, params = {}) => {
        const key = String(value ?? '');
        const message = EN_MESSAGES[key] || key;
        return Object.entries(params).reduce(
            (result, [name, replacement]) => result.replaceAll('{' + name + '}', String(replacement)),
            message
        );
    };
    const i18n = Object.freeze({
        apply: (root = document) => {
            const html = root.documentElement || document.documentElement;
            html.lang = APP_LOCALE;
            html.dir = 'ltr';
        },
        bindAttribute: (element, attribute, value) => {
            element.setAttribute(attribute, translateEnglish(value));
            return element;
        },
        bindText: (element, value) => {
            element.textContent = translateEnglish(value);
            return element;
        },
        date: (value, options = {}) => {
            const parsed = value instanceof Date ? value : new Date(value);
            if (Number.isNaN(parsed.getTime())) return value ? String(value) : '—';
            return new Intl.DateTimeFormat('en-US', options).format(parsed);
        },
        direction: () => 'ltr',
        getLocale: () => APP_LOCALE,
        list: (values) => new Intl.ListFormat('en-US', { style: 'long', type: 'conjunction' }).format(values),
        number: (value, options = {}) => {
            const numeric = Number(value);
            return Number.isFinite(numeric) ? new Intl.NumberFormat('en-US', options).format(numeric) : String(value);
        },
        percent: (value, options = {}) => {
            const numeric = Number(value);
            if (!Number.isFinite(numeric)) return '—';
            return new Intl.NumberFormat('en-US', {
                style: 'percent',
                maximumFractionDigits: 1,
                ...options,
            }).format(numeric / 100);
        },
        t: translateEnglish,
    });
    const t = (value, params = {}) => i18n.t(value, params);
    const formatNumber = (value, options = {}) => i18n.number(value, options);
    const formatPercent = (value, options = {}) => i18n.percent(value, options);
    const formatDays = (value) => formatNumber(value) + ' days';
    const formatOutcomes = (value) => formatNumber(value) + ' outcomes';
    const API_TIMEOUT = Object.freeze({
        read: 20000,
        intake: 25000,
        analyze: 95000,
        chat: 75000,
        write: 30000,
    });

    const state = {
        tier: 'B2C',
        horizon: 'instant',
        intake: null,
        questions: [],
        questionIndex: 0,
        answers: Object.create(null),
        knownFacts: Object.create(null),
        currentAnalysis: null,
        currentIntelligence: null,
        currentAnalysisId: null,
        currentGoal: null,
        currentProfile: null,
        currentUsage: null,
        messages: [],
        chatExecutionKits: [],
        goals: [],
        calibration: null,
        calibrationPredictions: [],
        selectedResultTab: 'overview',
        memoryFilter: 'all',
        vaultEntries: [],
        defaultFollowUps: [],
        intakeBusy: false,
        analysisBusy: false,
        chatBusy: false,
        goalBusy: false,
        activeRequests: 0,
        pendingRequests: new Map(),
        draftTimer: null,
        statusTimer: null,
        lastDialogTrigger: new WeakMap(),
        chatList: null,
    };

    const refs = {};

    class ApiError extends Error {
        constructor(message, status = 0, code = 'api_error') {
            super(message);
            this.name = 'ApiError';
            this.status = status;
            this.code = code;
        }
    }

    function byId(id) {
        return document.getElementById(id);
    }

    function asText(value, fallback = '') {
        if (value === null || value === undefined) return fallback;
        if (typeof value === 'string') return value;
        if (typeof value === 'number' || typeof value === 'boolean') return String(value);
        return fallback;
    }

    function asArray(value) {
        return Array.isArray(value) ? value : [];
    }

    function isRecord(value) {
        return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
    }

    function clampNumber(value, minimum, maximum, fallback = minimum) {
        const number = Number(value);
        if (!Number.isFinite(number)) return fallback;
        return Math.min(maximum, Math.max(minimum, number));
    }

    function hasValue(value) {
        if (value === null || value === undefined) return false;
        if (typeof value === 'string') return value.trim().length > 0;
        if (Array.isArray(value)) return value.length > 0;
        if (typeof value === 'object') return Object.keys(value).length > 0;
        return true;
    }

    function safeDirection(value) {
        const direction = asText(value).toLowerCase();
        return direction === 'rtl' || direction === 'ltr' ? direction : 'auto';
    }

    function safeStatusClass(value) {
        const token = asText(value).toLowerCase();
        if (token === 'live') return 'live';
        if (token === 'correct') return 'correct';
        if (token === 'incorrect') return 'incorrect';
        if (token === 'flat') return 'flat';
        if (token === 'pending') return 'pending';
        if (token === 'active') return 'active';
        if (token === 'completed') return 'completed';
        if (token === 'paused') return 'paused';
        if (token === 'archived') return 'archived';
        return 'degraded';
    }

    const SEMANTIC_LABELS = Object.freeze({
        high: 'High',
        moderate: 'Moderate',
        medium: 'Medium',
        low: 'Low',
        live: 'Live',
        fresh: 'Fresh',
        stale: 'Stale',
        partial: 'Partial',
        degraded: 'Limited',
        unavailable: 'Unavailable',
        up: 'Up',
        down: 'Down',
        flat: 'Flat',
        correct: 'Correct',
        incorrect: 'Incorrect',
        pending: 'Pending',
        active: 'Active',
        paused: 'Paused',
        completed: 'Completed',
        archived: 'Archived',
    });

    function semanticLabel(value) {
        const raw = asText(value);
        const localized = SEMANTIC_LABELS[raw.toLowerCase()];
        return localized || raw;
    }

    function safeScrollIntoView(target, options = {}) {
        if (!target || typeof target.scrollIntoView !== 'function') return;
        const reduceMotion = typeof window.matchMedia === 'function'
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        target.scrollIntoView({
            ...options,
            behavior: reduceMotion ? 'auto' : 'smooth',
        });
    }

    function node(tag, options = {}) {
        const element = document.createElement(tag);
        if (options.className) {
            asText(options.className)
                .split(/\s+/)
                .filter(Boolean)
                .forEach((className) => element.classList.add(className));
        }
        if (options.text !== undefined) {
            if (options.translate === false) {
                element.textContent = asText(options.text);
                element.dataset.i18nSkip = 'true';
            } else {
                i18n.bindText(element, asText(options.text));
            }
        }
        if (options.type && 'type' in element) element.type = options.type;
        if (options.id) element.id = options.id;
        if (options.role) element.setAttribute('role', options.role);
        if (options.title) i18n.bindAttribute(element, 'title', asText(options.title));
        return element;
    }

    function setUiText(element, value) {
        if (element) i18n.bindText(element, asText(value));
        return element;
    }

    function setUiAttribute(element, attribute, value) {
        if (element) i18n.bindAttribute(element, attribute, asText(value));
        return element;
    }

    function append(parent, ...children) {
        children.flat().forEach((child) => {
            if (child instanceof Node) parent.appendChild(child);
        });
        return parent;
    }

    function clear(element) {
        if (element) element.replaceChildren();
    }

    function textLine(text, className, translate = true) {
        return node('p', { className, text, translate });
    }

    function heading(level, text, className) {
        const safeLevel = [2, 3, 4, 5, 6].includes(level) ? level : 3;
        return node('h' + safeLevel, { className, text });
    }

    function sectionBlock(title, className = '') {
        const section = node('section', { className });
        if (title) section.appendChild(heading(3, title, 'section-title'));
        return section;
    }

    function listBlock(items, className = 'detail-list') {
        const list = node('ul', { className });
        asArray(items).forEach((item) => {
            const value = typeof item === 'string' ? item : describeObject(item);
            if (value) list.appendChild(node('li', { text: value, translate: false }));
        });
        return list;
    }

    const FIELD_LABELS = Object.freeze({
        amount: 'Amount',
        budget: 'Budget',
        capital: 'Capital',
        channel: 'Channel',
        cost: 'Cost',
        deadline: 'Deadline',
        description: 'Description',
        duration: 'Duration',
        frequency: 'Frequency',
        metric: 'Metric',
        objective: 'Goal',
        owner: 'Owner',
        phase: 'Phase',
        priority: 'Priority',
        target: 'Goal',
        time: 'Time',
        title: 'Title',
        weekly_hours: 'Weekly hours',
    });

    function describeObject(value) {
        if (!isRecord(value)) return asText(value);
        return Object.entries(value)
            .filter((entry) => hasValue(entry[1]))
            .slice(0, 12)
            .map(([key, item]) => {
                const label = FIELD_LABELS[key] || key.replaceAll('_', ' ');
                const rendered = Array.isArray(item)
                    ? i18n.list(item.map((part) => asText(part)).filter(Boolean))
                    : asText(item);
                return rendered ? t(label) + ': ' + rendered : '';
            })
            .filter(Boolean)
            .join(' · ');
    }

    function detailGrid(fields, className = 'detail-grid') {
        const grid = node('dl', { className });
        fields.forEach(([label, value]) => {
            if (!hasValue(value)) return;
            const row = node('div', { className: 'detail-row' });
            append(
                row,
                node('dt', { text: label }),
                node('dd', { text: describeObject(value) || asText(value), translate: false })
            );
            grid.appendChild(row);
        });
        return grid;
    }

    function formatDate(value) {
        if (!value) return '—';
        return i18n.date(value);
    }

    function extractMessage(payload, fallback) {
        if (!isRecord(payload)) return fallback;
        if (typeof payload.message === 'string' && payload.message.trim()) return payload.message;
        if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail;
        if (isRecord(payload.detail)) {
            if (typeof payload.detail.message === 'string' && payload.detail.message.trim()) {
                return payload.detail.message;
            }
            if (typeof payload.detail.error === 'string' && payload.detail.error.trim()) {
                return payload.detail.error;
            }
        }
        if (Array.isArray(payload.detail)) {
            const validationMessages = payload.detail
                .filter(isRecord)
                .map((item) => asText(item.msg))
                .filter(Boolean)
                .slice(0, 3);
            if (validationMessages.length) {
                return validationMessages.join('; ');
            }
        }
        if (typeof payload.error === 'string' && payload.error.trim()) return payload.error;
        return fallback;
    }

    function unwrapData(payload) {
        return isRecord(payload) && Object.prototype.hasOwnProperty.call(payload, 'data')
            ? payload.data
            : payload;
    }

    function listFrom(payload, fallbackKeys = []) {
        const data = unwrapData(payload);
        if (Array.isArray(data)) return data;
        if (isRecord(data)) {
            for (const key of fallbackKeys) {
                if (Array.isArray(data[key])) return data[key];
            }
        }
        return [];
    }

    function localizedHttpError(status) {
        if (status === 400) return 'The request cannot be processed. Check the information you entered.';
        if (status === 401 || status === 403) return 'Your session is invalid or you do not have access to this section.';
        if (status === 404) return 'The requested information was not found.';
        if (status === 409) return 'This action is not compatible with the current state.';
        if (status === 413) return 'The request is larger than the allowed limit.';
        if (status === 422) return 'Some answers are invalid or incomplete.';
        if (status === 429) return 'The temporary request limit has been reached. Try again shortly.';
        if (status === 502) return 'The AI engine returned an invalid response. Try again.';
        if (status === 503) return 'The AI service is temporarily unavailable.';
        if (status === 504) return 'The service timed out.';
        return 'An unexpected error occurred. Try again.';
    }

    function updateGlobalProgress() {
        if (!refs.globalProgress) return;
        const busy = state.activeRequests > 0;
        refs.globalProgress.hidden = !busy;
        refs.globalProgress.setAttribute('aria-busy', busy ? 'true' : 'false');
        if (refs.globalProgressText) {
            setUiText(refs.globalProgressText, busy ? 'Syncing information…' : '');
        }
    }

    async function apiRequest(path, options = {}) {
        const method = asText(options.method, 'GET').toUpperCase();
        const requestKey = asText(options.key, method + ':' + path);
        if (state.pendingRequests.has(requestKey)) {
            throw new ApiError('This request is already in progress.', 0, 'duplicate');
        }

        const controller = new AbortController();
        const timeout = clampNumber(options.timeout, 1000, 120000, API_TIMEOUT.read);
        const timer = window.setTimeout(() => controller.abort(), timeout);
        const headers = {
            Accept: 'application/json',
            'Accept-Language': APP_LOCALE,
        };
        const fetchOptions = {
            method,
            headers,
            credentials: 'same-origin',
            cache: 'no-store',
            signal: controller.signal,
        };
        if (options.body !== undefined) {
            headers['Content-Type'] = 'application/json';
            fetchOptions.body = JSON.stringify(options.body);
        }

        state.pendingRequests.set(requestKey, controller);
        state.activeRequests += 1;
        if (!options.silent) updateGlobalProgress();

        try {
            const response = await fetch(path, fetchOptions);
            let payload = null;
            const contentType = asText(response.headers.get('content-type')).toLowerCase();
            if (contentType.includes('application/json')) {
                try {
                    payload = await response.json();
                } catch {
                    throw new ApiError('The server response could not be read.', response.status, 'invalid_json');
                }
            }

            if (!response.ok) {
                throw new ApiError(
                    extractMessage(payload, localizedHttpError(response.status)),
                    response.status,
                    'http_error'
                );
            }
            if (payload === null) {
                throw new ApiError('The server did not return a valid response.', response.status, 'empty_response');
            }
            if (isRecord(payload) && payload.status && payload.status !== 'success') {
                throw new ApiError(extractMessage(payload, 'The operation did not complete.'), response.status, 'api_status');
            }
            return payload;
        } catch (error) {
            if (error && error.name === 'AbortError') {
                throw new ApiError('The request timed out. Check your connection and try again.', 0, 'timeout');
            }
            if (error instanceof ApiError) throw error;
            throw new ApiError('Could not connect to the server.', 0, 'network');
        } finally {
            window.clearTimeout(timer);
            state.pendingRequests.delete(requestKey);
            state.activeRequests = Math.max(0, state.activeRequests - 1);
            if (!options.silent) updateGlobalProgress();
        }
    }

    function announce(message, assertive = false) {
        const target = assertive ? refs.assertiveLiveRegion : refs.toastRegion;
        if (!target) return;
        if (assertive) {
            target.textContent = t(message);
            window.setTimeout(() => {
                if (target.textContent === t(message)) target.textContent = '';
            }, 5000);
            return;
        }
        const toast = node('div', { className: 'toast-message', text: message, role: 'status' });
        target.appendChild(toast);
        window.setTimeout(() => toast.remove(), 4500);
    }

    function showError(target, message) {
        if (target) {
            setUiText(target, message);
            target.hidden = false;
        }
        announce(message, true);
    }

    function clearError(target) {
        if (!target) return;
        target.textContent = '';
        target.hidden = true;
    }

    function setStatus(message, busy = false) {
        if (refs.analysisStatusLabel) {
            setUiText(refs.analysisStatusLabel, busy ? 'Building your analysis' : 'Analysis ready');
        }
        if (refs.systemLogs) setUiText(refs.systemLogs, message);
        if (refs.analysisStatus) {
            refs.analysisStatus.hidden = !busy && !hasValue(message);
            refs.analysisStatus.dataset.state = busy ? 'busy' : 'idle';
            refs.analysisStatus.setAttribute('aria-busy', busy ? 'true' : 'false');
        }
        if (refs.resultsContainer) refs.resultsContainer.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    function startStatusSequence(messages) {
        stopStatusSequence();
        setStatus(messages[0] || 'Working…', true);
    }

    function stopStatusSequence(finalMessage = '') {
        if (state.statusTimer) {
            window.clearInterval(state.statusTimer);
            state.statusTimer = null;
        }
        setStatus(finalMessage, false);
    }

    function readStorage(key) {
        try {
            return localStorage.getItem(key);
        } catch {
            return null;
        }
    }

    function writeStorage(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch {
            // Storage is optional; the application must remain usable without it.
        }
    }

    function removeStorage(key) {
        try {
            localStorage.removeItem(key);
        } catch {
            // Storage is optional.
        }
    }

    function setHeroCompact(compact, persist = false) {
        const collapsed = Boolean(compact);
        document.body.classList.toggle('hero-compact', collapsed);
        if (refs.heroToggle) {
            refs.heroToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            setUiText(refs.heroToggle, collapsed ? 'hero.expand' : 'hero.collapse');
        }
        if (persist) writeStorage('omni-hero-compact-v1', collapsed ? '1' : '0');
    }

    function bindProgressiveDisclosure() {
        if (refs.heroToggle) {
            refs.heroToggle.addEventListener('click', () => {
                setHeroCompact(!document.body.classList.contains('hero-compact'), true);
            });
        }
        setHeroCompact(readStorage('omni-hero-compact-v1') === '1');

        if (refs.contextRailToggle && refs.contextRailContent) {
            refs.contextRailToggle.addEventListener('click', () => {
                const expanded = refs.contextRailToggle.getAttribute('aria-expanded') === 'true';
                refs.contextRailToggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
                refs.contextRailContent.hidden = expanded;
                setUiAttribute(
                    refs.contextRailToggle,
                    'aria-label',
                    expanded ? 'context.expand' : 'context.collapse'
                );
                writeStorage('omni-context-expanded-v1', expanded ? '0' : '1');
            });
            const expanded = readStorage('omni-context-expanded-v1') !== '0';
            refs.contextRailToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            refs.contextRailContent.hidden = !expanded;
            setUiAttribute(
                refs.contextRailToggle,
                'aria-label',
                expanded ? 'context.collapse' : 'context.expand'
            );
        }
    }

    function applyTheme(theme) {
        const light = theme === 'light';
        document.body.classList.toggle('light-mode', light);
        document.documentElement.dataset.theme = light ? 'light' : 'dark';
        if (refs.themeColorMeta) refs.themeColorMeta.content = light ? '#f4f7fb' : '#070a12';
        if (refs.themeToggle) {
            refs.themeToggle.removeAttribute('aria-pressed');
            setUiAttribute(refs.themeToggle, 'aria-label', light ? 'Enable dark mode' : 'Enable light mode');
            setUiAttribute(refs.themeToggle, 'title', light ? 'Dark mode' : 'Light mode');
            const label = refs.themeToggleLabel || refs.themeToggle.querySelector('[data-theme-label]');
            if (label) {
                setUiText(label, light ? 'Dark theme' : 'Light theme');
            } else if (!refs.themeToggle.children.length) {
                refs.themeToggle.textContent = light ? '☾' : '☀';
            }
        }
    }

    function initializeTheme() {
        let theme = readStorage('omni-theme');
        if (theme !== 'light' && theme !== 'dark') {
            theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
                ? 'light'
                : 'dark';
        }
        applyTheme(theme);
        if (refs.themeToggle) {
            refs.themeToggle.addEventListener('click', () => {
                const next = document.body.classList.contains('light-mode') ? 'dark' : 'light';
                applyTheme(next);
                writeStorage('omni-theme', next);
            });
        }
    }

    const TIER_COPY = Object.freeze({
        B2C: {
            placeholder: 'For example: I have $5,000 and two hours a day. What is the best lower-risk path for my current skills?',
            description: 'Individual path: evaluates your skills, time, capital, local market, and maximum tolerable loss.',
        },
        B2B: {
            placeholder: 'For example: we source components from East Asia. What are the supply-chain risks and the right 90-day decision?',
            description: 'Business path: evaluates KPIs, stakeholders, suppliers, jurisdictions, compliance, and financial impact.',
        },
    });

    function setTier(tier, persist = true) {
        state.tier = tier === 'B2B' ? 'B2B' : 'B2C';
        const isB2C = state.tier === 'B2C';
        if (refs.tierB2C) {
            if (refs.tierB2C.matches('input[type="radio"]')) {
                refs.tierB2C.checked = isB2C;
                refs.tierB2C.removeAttribute('aria-pressed');
            } else {
                refs.tierB2C.setAttribute('aria-pressed', isB2C ? 'true' : 'false');
            }
            refs.tierB2C.classList.toggle('active', isB2C);
        }
        if (refs.tierB2B) {
            if (refs.tierB2B.matches('input[type="radio"]')) {
                refs.tierB2B.checked = !isB2C;
                refs.tierB2B.removeAttribute('aria-pressed');
            } else {
                refs.tierB2B.setAttribute('aria-pressed', !isB2C ? 'true' : 'false');
            }
            refs.tierB2B.classList.toggle('active', !isB2C);
        }
        if (refs.queryInput) setUiAttribute(refs.queryInput, 'placeholder', TIER_COPY[state.tier].placeholder);
        renderContextSummary();
        updatePrecision();
        if (persist) scheduleDraftSave();
    }

    function setHorizon(horizon, persist = true) {
        state.horizon = horizon === 'strategic' ? 'strategic' : 'instant';
        const strategic = state.horizon === 'strategic';
        if (refs.strategicToggle) {
            if (refs.strategicToggle.matches('input[type="checkbox"]')) {
                refs.strategicToggle.checked = strategic;
            } else {
                refs.strategicToggle.classList.toggle('is-on', strategic);
            }
            refs.strategicToggle.setAttribute('aria-checked', strategic ? 'true' : 'false');
        }
        renderContextSummary();
        updatePrecision();
        if (persist) scheduleDraftSave();
    }

    function scheduleDraftSave() {
        if (state.draftTimer) window.clearTimeout(state.draftTimer);
        state.draftTimer = window.setTimeout(() => {
            const draft = {
                query: refs.queryInput ? refs.queryInput.value.slice(0, INPUT_LIMIT) : '',
                tier: state.tier,
                horizon: state.horizon,
            };
            writeStorage('omni-draft-v2', JSON.stringify(draft));
        }, 250);
    }

    function restoreDraft() {
        const raw = readStorage('omni-draft-v2');
        if (!raw) return;
        try {
            const draft = JSON.parse(raw);
            if (!isRecord(draft)) return;
            setTier(draft.tier, false);
            setHorizon(draft.horizon, false);
            if (refs.queryInput && typeof draft.query === 'string') {
                refs.queryInput.value = draft.query.slice(0, INPUT_LIMIT);
            }
        } catch {
            removeStorage('omni-draft-v2');
        }
    }

    function updateCharacterCount() {
        if (!refs.queryInput) return;
        if (refs.queryInput.value.length > INPUT_LIMIT) {
            refs.queryInput.value = refs.queryInput.value.slice(0, INPUT_LIMIT);
        }
        if (refs.queryCharCount) {
            const current = formatNumber(refs.queryInput.value.length);
            const maximum = formatNumber(INPUT_LIMIT);
            setUiText(refs.queryCharCount, current + ' of ' + maximum);
        }
        scheduleDraftSave();
        updatePrecision();
    }

    function factEntries() {
        return Object.entries(isRecord(state.knownFacts) ? state.knownFacts : {})
            .filter((entry) => hasValue(entry[1]))
            .slice(0, 8);
    }

    function renderContextSummary() {
        if (!refs.contextSummaryList) return;
        clear(refs.contextSummaryList);
        refs.contextSummaryList.appendChild(node('li', {
            text: state.tier === 'B2C' ? 'Individual decision (B2C)' : 'Business decision (B2B)',
        }));
        refs.contextSummaryList.appendChild(node('li', {
            text: state.horizon === 'strategic' ? 'Strategic, long-term horizon' : 'Near-term execution horizon',
        }));
        refs.contextSummaryList.appendChild(node('li', { text: TIER_COPY[state.tier].description }));
        factEntries().forEach(([key, value]) => {
            refs.contextSummaryList.appendChild(node('li', {
                text: (FIELD_LABELS[key] || key.replaceAll('_', ' ')) + ': ' + describeObject(value),
            }));
        });
    }

    function updatePrecision() {
        const queryLength = refs.queryInput ? refs.queryInput.value.trim().length : 0;
        const answered = Object.values(state.answers)
            .filter((value) => hasValue(value) && asText(value).toLowerCase() !== 'unknown')
            .length;
        const total = state.questions.length;
        let score = queryLength >= 20 ? 24 : Math.round((queryLength / 20) * 24);
        score += state.tier ? 12 : 0;
        score += state.horizon ? 10 : 0;
        score += Math.min(14, factEntries().length * 3);
        if (total) score += Math.round((answered / total) * 40);
        score = clampNumber(score, 0, 100, 0);
        if (refs.precisionMeter) {
            if ('value' in refs.precisionMeter) refs.precisionMeter.value = score;
            else refs.precisionMeter.textContent = formatPercent(score);
        }
        if (refs.precisionMeterFill) {
            refs.precisionMeterFill.max = 100;
            refs.precisionMeterFill.value = score;
            refs.precisionMeterFill.textContent = formatPercent(score);
        }
        if (refs.precisionLabel) {
            setUiText(refs.precisionLabel, score < 45
                ? 'Starting coverage'
                : score < 80
                    ? 'Useful coverage'
                    : 'Strong coverage');
        }
        if (refs.wizardPrecisionValue) {
            refs.wizardPrecisionValue.textContent = formatPercent(score);
        }
        if (refs.wizardPrecisionLabel) {
            setUiText(refs.wizardPrecisionLabel, score < 45
                ? 'Starting coverage'
                : score < 80
                    ? 'Useful coverage'
                    : 'Strong coverage');
        }
    }

    function normalizeOption(option, index) {
        if (isRecord(option)) {
            const value = asText(option.value || option.id || option.label, String(index + 1));
            const localized = isRecord(option.translations) && hasValue(option.translations.en)
                ? option.translations.en
                : isRecord(option.i18n) && hasValue(option.i18n.en)
                    ? option.i18n.en
                    : null;
            const localizedLabel = isRecord(localized)
                ? localized.label || localized.text
                : localized;
            return { value, label: asText(localizedLabel || option.label || option.text || option.value, value) };
        }
        const value = asText(option, String(index + 1));
        return { value, label: value };
    }

    function normalizeQuestion(question, index) {
        const raw = isRecord(question) ? question : {};
        const localized = isRecord(raw.translations) && isRecord(raw.translations.en)
            ? raw.translations.en
            : isRecord(raw.i18n) && isRecord(raw.i18n.en)
                ? raw.i18n.en
                : {};
        const source = { ...raw, ...localized };
        const rawType = asText(source.type).toLowerCase();
        const mappedType = rawType === 'single' ? 'choice' : rawType;
        const allowedTypes = new Set(['text', 'textarea', 'number', 'select', 'choice', 'radio', 'multiselect', 'boolean']);
        const type = allowedTypes.has(mappedType)
            ? mappedType
            : 'text';
        return {
            id: asText(raw.id, 'question_' + (index + 1)),
            type,
            prompt: asText(source.prompt || source.question || source.label, 'Clarifying answer'),
            help: asText(source.help || source.help_text),
            required: raw.required !== false,
            allowUnknown: raw.allow_unknown !== false,
            unknownLabel: asText(source.unknown_label, 'I do not know / not decided yet'),
            options: asArray(source.options || raw.options).slice(0, 30).map(normalizeOption),
            placeholder: asText(source.placeholder),
            maxLength: clampNumber(raw.max_length, 1, 2000, 800),
        };
    }

    function currentQuestion() {
        return state.questions[state.questionIndex] || null;
    }

    function buildQuestionControl(question) {
        const wrapper = node('div', { className: 'wizard-question-card' });
        const controlId = 'clarification-answer-' + state.questionIndex;
        const options = question.type === 'boolean'
            ? [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }]
            : question.options;
        const usesFieldset = options.length > 0 && (
            question.type === 'multiselect'
            || question.type === 'choice'
            || question.type === 'radio'
            || question.type === 'boolean'
        );
        const prompt = node(usesFieldset ? 'p' : 'label', {
            className: 'wizard-question-prompt',
            text: question.prompt,
        });
        prompt.id = controlId + '-prompt';
        if (!usesFieldset) prompt.htmlFor = controlId;
        wrapper.appendChild(prompt);
        if (question.help) wrapper.appendChild(textLine(question.help, 'wizard-question-help'));

        const previous = state.answers[question.id];
        let control;

        if (question.type === 'multiselect' && options.length) {
            control = node('fieldset', { className: 'wizard-options' });
            control.id = controlId;
            const selected = new Set(Array.isArray(previous) ? previous.map(asText) : []);
            options.forEach((option, optionIndex) => {
                const label = node('label', { className: 'wizard-option' });
                const input = node('input', { type: 'checkbox' });
                input.name = 'clarification-multi';
                input.value = option.value;
                input.checked = selected.has(option.value);
                input.dataset.optionIndex = String(optionIndex);
                append(label, input, node('span', { text: option.label }));
                control.appendChild(label);
            });
        } else if ((question.type === 'choice' || question.type === 'radio' || question.type === 'boolean') && options.length) {
            control = node('fieldset', { className: 'wizard-options' });
            control.id = controlId;
            options.forEach((option, optionIndex) => {
                const label = node('label', { className: 'wizard-option' });
                const input = node('input', { type: 'radio' });
                input.name = 'clarification-choice';
                input.value = option.value;
                input.checked = asText(previous) === option.value;
                input.dataset.optionIndex = String(optionIndex);
                append(label, input, node('span', { text: option.label }));
                control.appendChild(label);
            });
        } else if (question.type === 'select' && options.length) {
            control = node('select');
            control.id = controlId;
            control.name = 'clarification-answer';
            const emptyOption = node('option', { text: 'Select an option' });
            emptyOption.value = '';
            control.appendChild(emptyOption);
            options.forEach((option) => {
                const optionNode = node('option', { text: option.label });
                optionNode.value = option.value;
                optionNode.selected = asText(previous) === option.value;
                control.appendChild(optionNode);
            });
        } else if (question.type === 'textarea') {
            control = node('textarea');
            control.id = controlId;
            control.name = 'clarification-answer';
            control.rows = 4;
            control.maxLength = question.maxLength;
            control.value = asText(previous);
        } else {
            control = node('input', { type: question.type === 'number' ? 'number' : 'text' });
            control.id = controlId;
            control.name = 'clarification-answer';
            if (question.type !== 'number') control.maxLength = question.maxLength;
            control.value = asText(previous);
        }

        if ('placeholder' in control && question.placeholder) control.placeholder = question.placeholder;
        if ('required' in control) control.required = question.required;
        if (usesFieldset) control.setAttribute('aria-labelledby', prompt.id);
        control.setAttribute('aria-required', question.required ? 'true' : 'false');
        wrapper.appendChild(control);
        const fieldError = textLine('', 'field-error');
        fieldError.dataset.wizardError = 'true';
        fieldError.hidden = true;
        wrapper.appendChild(fieldError);
        return wrapper;
    }

    function renderWizardSummary() {
        if (!refs.clarificationSummary || !refs.clarificationSummaryContent) return;
        clear(refs.clarificationSummaryContent);
        const answered = state.questions
            .filter((question) => hasValue(state.answers[question.id]))
            .map((question) => {
                const answer = state.answers[question.id];
                const displayAnswer = asText(answer).toLowerCase() === 'unknown'
                    ? question.unknownLabel
                    : Array.isArray(answer)
                        ? i18n.list(answer)
                        : asText(answer);
                return question.prompt + ': ' + displayAnswer;
            });
        if (!answered.length) {
            refs.clarificationSummary.hidden = true;
            return;
        }
        refs.clarificationSummary.hidden = false;
        refs.clarificationSummaryContent.appendChild(listBlock(answered, 'wizard-summary-list'));
    }

    function renderWizardStep() {
        const question = currentQuestion();
        if (!question || !refs.clarificationQuestions) return;
        clear(refs.clarificationQuestions);
        refs.clarificationQuestions.appendChild(buildQuestionControl(question));

        const total = state.questions.length;
        const position = state.questionIndex + 1;
        if (refs.wizardStepLabel) {
            const positionText = formatNumber(position);
            const totalText = formatNumber(total);
            setUiText(refs.wizardStepLabel, 'Question ' + positionText + ' of ' + totalText);
        }
        if (refs.wizardProgressBar) {
            refs.wizardProgressBar.max = total;
            refs.wizardProgressBar.value = position;
            refs.wizardProgressBar.textContent = formatNumber(position) + ' of ' + formatNumber(total);
        }
        if (refs.wizardBack) refs.wizardBack.hidden = state.questionIndex === 0;
        if (refs.wizardSkip) refs.wizardSkip.hidden = !question.allowUnknown;
        if (refs.wizardNext) refs.wizardNext.hidden = state.questionIndex >= total - 1;
        if (refs.wizardSubmit) refs.wizardSubmit.hidden = state.questionIndex < total - 1;
        renderWizardSummary();
        updatePrecision();
        window.requestAnimationFrame(() => {
            const focusTarget = refs.clarificationQuestions.querySelector('input, textarea, select, button');
            if (focusTarget) focusTarget.focus({ preventScroll: true });
        });
    }

    function readCurrentAnswer(validateRequired = true) {
        const question = currentQuestion();
        if (!question || !refs.clarificationQuestions) return true;
        let value;
        if (question.type === 'multiselect') {
            value = Array.from(refs.clarificationQuestions.querySelectorAll('input[type="checkbox"]:checked'))
                .map((input) => input.value);
        } else if (question.type === 'choice' || question.type === 'radio' || question.type === 'boolean') {
            const checked = refs.clarificationQuestions.querySelector('input[type="radio"]:checked');
            value = checked ? checked.value : '';
        } else {
            const control = refs.clarificationQuestions.querySelector('input, textarea, select');
            value = control ? control.value.trim() : '';
        }

        const valid = hasValue(value) || !question.required || !validateRequired;
        const error = refs.clarificationQuestions.querySelector('[data-wizard-error]');
        if (!valid) {
            if (error) {
                setUiText(error, 'Answer this question to continue.');
                error.hidden = false;
            }
            return false;
        }
        if (error) {
            error.textContent = '';
            error.hidden = true;
        }
        if (hasValue(value)) state.answers[question.id] = value;
        else delete state.answers[question.id];
        renderWizardSummary();
        updatePrecision();
        return true;
    }

    function skipCurrentQuestion() {
        const question = currentQuestion();
        if (!question || !question.allowUnknown || state.analysisBusy) return;
        state.answers[question.id] = 'unknown';
        renderWizardSummary();
        updatePrecision();
        if (state.questionIndex < state.questions.length - 1) {
            state.questionIndex += 1;
            renderWizardStep();
            return;
        }
        void submitAnalysis(true);
    }

    function showWizard(intakeData) {
        const data = isRecord(intakeData) ? intakeData : {};
        state.intake = data;
        state.questions = asArray(data.questions).slice(0, 5).map(normalizeQuestion);
        state.questionIndex = 0;
        state.answers = Object.create(null);
        state.knownFacts = isRecord(data.known_facts) ? data.known_facts : Object.create(null);
        renderContextSummary();
        if (!refs.clarificationWizard || !state.questions.length) return false;
        refs.clarificationWizard.hidden = false;
        refs.clarificationWizard.dataset.state = 'active';
        if (refs.wizardTitle) {
            setUiText(refs.wizardTitle, state.tier === 'B2C'
                ? 'A few questions for a genuinely personalized recommendation'
                : 'A few questions for a defensible business decision');
        }
        renderWizardStep();
        safeScrollIntoView(refs.clarificationWizard, { block: 'start' });
        return true;
    }

    function hideWizard() {
        if (!refs.clarificationWizard) return;
        refs.clarificationWizard.hidden = true;
        refs.clarificationWizard.dataset.state = 'idle';
    }

    function setAnalysisControlsDisabled(disabled) {
        state.intakeBusy = disabled;
        if (refs.analyzeButton) refs.analyzeButton.disabled = disabled;
        if (refs.queryInput) refs.queryInput.disabled = disabled;
        if (refs.tierB2C) refs.tierB2C.disabled = disabled;
        if (refs.tierB2B) refs.tierB2B.disabled = disabled;
        if (refs.strategicToggle && 'disabled' in refs.strategicToggle) refs.strategicToggle.disabled = disabled;
    }

    async function beginIntake() {
        if (state.intakeBusy || state.analysisBusy || !refs.queryInput) return;
        clearError(refs.analysisFormError);
        const query = refs.queryInput.value.trim();
        if (query.length < 10) {
            showError(refs.analysisFormError, 'Describe the problem using at least 10 characters.');
            refs.queryInput.focus();
            return;
        }
        if (query.length > INPUT_LIMIT) {
            showError(refs.analysisFormError, 'The request is longer than the allowed limit.');
            return;
        }

        setHeroCompact(true, true);
        setAnalysisControlsDisabled(true);
        startStatusSequence([
            'Extracting facts already present in your request…',
            state.tier === 'B2C'
                ? 'Checking gaps in skills, time, capital, and risk…'
                : 'Checking gaps in operations, KPIs, compliance, and supply chain…',
            'Preparing the shortest path to a more precise answer…',
        ]);
        try {
            const payload = await apiRequest('/api/intake', {
                method: 'POST',
                body: { query, tier: state.tier, horizon: state.horizon, locale: APP_LOCALE },
                timeout: API_TIMEOUT.intake,
                key: 'intake',
            });
            const intakeData = unwrapData(payload);
            if (!isRecord(intakeData) || !asText(intakeData.session_id)) {
                throw new ApiError('The server did not return a clarification-session ID.', 502, 'missing_session');
            }
            state.intake = intakeData;
            const shown = showWizard(intakeData);
            stopStatusSequence(shown ? 'Clarifying questions are ready.' : 'Context is complete; analysis is starting.');
            if (!shown) await submitAnalysis(false);
        } catch (error) {
            stopStatusSequence('');
            showError(refs.analysisFormError, error.message);
        } finally {
            setAnalysisControlsDisabled(false);
        }
    }

    function setWizardControlsDisabled(disabled) {
        [refs.wizardBack, refs.wizardSkip, refs.wizardNext, refs.wizardSubmit]
            .filter(Boolean)
            .forEach((button) => {
                button.disabled = disabled;
            });
    }

    async function submitAnalysis(preserveCurrentAnswer = false) {
        if (state.analysisBusy) return;
        if (!state.intake || !asText(state.intake.session_id)) {
            showError(refs.analysisFormError, 'The analysis session was not found; submit the request again.');
            return;
        }
        if (!preserveCurrentAnswer && state.questions.length && !readCurrentAnswer(true)) return;

        state.analysisBusy = true;
        setWizardControlsDisabled(true);
        clearError(refs.analysisFormError);
        startStatusSequence([
            'Checking available sources and assembling your analysis…',
            state.horizon === 'strategic'
                ? 'Building scenarios, stop conditions, and a long-term roadmap…'
                : 'Building short, measurable, lower-risk actions…',
            'Validating risk, cost, and success criteria for each step…',
            'Finalizing the structured response…',
        ]);

        try {
            const payload = await apiRequest('/api/analyze', {
                method: 'POST',
                body: {
                    session_id: state.intake.session_id,
                    answers: { ...state.answers },
                    force_refresh: false,
                    locale: APP_LOCALE,
                },
                timeout: API_TIMEOUT.analyze,
                key: 'analysis',
            });
            const analysis = unwrapData(payload);
            if (!isRecord(analysis)) {
                throw new ApiError('The analysis response has an invalid structure.', 502, 'invalid_analysis');
            }
            const intelligence = isRecord(payload.intelligence)
                ? payload.intelligence
                : isRecord(analysis.intelligence_snapshot)
                    ? analysis.intelligence_snapshot
                    : {};
            analysis.cached = Boolean(payload.cached || analysis.cached);
            state.currentAnalysis = analysis;
            state.currentIntelligence = intelligence;
            state.currentAnalysisId = asText(analysis.analysis_id || analysis.id);
            hideWizard();
            renderAnalysis(analysis, intelligence);
            await loadMessages(state.currentAnalysisId, true);
            removeStorage('omni-draft-v2');
            stopStatusSequence(analysis.cached ? 'The result was restored from the local cache.' : 'Analysis complete.');
            announce(analysis.cached ? 'This result came from the local cache without additional model usage.' : 'Your new analysis is ready.');
            void refreshContextPreviews();
        } catch (error) {
            stopStatusSequence('');
            showError(refs.analysisFormError, error.message);
        } finally {
            state.analysisBusy = false;
            setWizardControlsDisabled(false);
        }
    }

    function appendTextSection(parent, title, value, className = '') {
        if (!hasValue(value)) return;
        const section = sectionBlock(title, className);
        section.appendChild(textLine(asText(value), 'detail-copy', false));
        parent.appendChild(section);
    }

    function appendListSection(parent, title, items, className = '') {
        if (!asArray(items).length) return;
        const section = sectionBlock(title, className);
        section.appendChild(listBlock(items));
        parent.appendChild(section);
    }

    function appendFlexibleCards(parent, title, items, className = '') {
        if (!asArray(items).length) return;
        const section = sectionBlock(title, className);
        const grid = node('div', { className: 'detail-card-grid' });
        asArray(items).forEach((item) => {
            const card = node('article', { className: 'detail-card' });
            if (typeof item === 'string') {
                card.appendChild(textLine(item, 'detail-copy', false));
            } else if (isRecord(item)) {
                const itemTitle = asText(item.title || item.name || item.phase || item.channel);
                if (itemTitle) card.appendChild(node('h4', {
                    className: 'detail-card-title',
                    text: itemTitle,
                    translate: false,
                }));
                const rows = Object.entries(item)
                    .filter(([key, value]) => !['title', 'name', 'phase', 'channel'].includes(key) && hasValue(value))
                    .slice(0, 12)
                    .map(([key, value]) => [FIELD_LABELS[key] || key.replaceAll('_', ' '), value]);
                card.appendChild(detailGrid(rows, 'detail-grid compact'));
            }
            grid.appendChild(card);
        });
        section.appendChild(grid);
        parent.appendChild(section);
    }

    function renderEvidencePanel(intelligence, evidence) {
        const hasStreams = isRecord(intelligence) && asArray(intelligence.streams).length > 0;
        const evidenceList = asArray(evidence);
        if (!hasStreams && !evidenceList.length) return null;

        const section = sectionBlock('Evidence and sources used', 'intel-section evidence-section');
        if (hasStreams) {
            const coverage = asText(intelligence.coverage_label);
            if (coverage) {
                section.appendChild(textLine('Source coverage estimate: ' + coverage, 'intel-coverage'));
            }
            const streamGrid = node('div', { className: 'intel-grid' });
            asArray(intelligence.streams).forEach((stream) => {
                if (!isRecord(stream)) return;
                const rawStatus = asText(stream.status || stream.freshness || stream.cache_status).toLowerCase();
                const status = ['live', 'fresh', 'current', 'ok'].includes(rawStatus)
                    ? 'fresh'
                    : ['stale', 'cached', 'expired'].includes(rawStatus)
                        ? 'stale'
                        : ['partial', 'degraded', 'limited'].includes(rawStatus)
                            ? 'partial'
                            : 'unavailable';
                const card = node('article', { className: 'intel-card ' + status });
                const head = node('div', { className: 'intel-card-head' });
                append(
                    head,
                    node('span', { className: 'intel-dot ' + status }),
                    node('span', { className: 'intel-label', text: stream.label || stream.key || 'Source' }),
                    node('span', { className: 'intel-status', text: semanticLabel(status) })
                );
                card.appendChild(head);
                if (hasValue(stream.summary)) card.appendChild(textLine(stream.summary, 'intel-summary'));
                const provider = asText(stream.provider || stream.source, 'Source');
                const sourceDetails = [
                    stream.as_of ? 'As of ' + asText(stream.as_of) : '',
                    stream.cache_status ? 'Cache: ' + asText(stream.cache_status) : '',
                ].filter(Boolean);
                const sourceUrl = safeExternalUrl(stream.source_url);
                const sourceLine = node('p', { className: 'intel-source' });
                if (sourceUrl) {
                    const sourceLink = node('a', {
                        className: 'intel-source-link',
                        text: provider,
                        translate: false,
                    });
                    sourceLink.href = sourceUrl.href;
                    sourceLink.target = '_blank';
                    sourceLink.rel = 'noopener noreferrer';
                    sourceLine.appendChild(sourceLink);
                } else {
                    sourceLine.appendChild(document.createTextNode(provider));
                }
                if (sourceDetails.length) {
                    sourceLine.appendChild(document.createTextNode(' · ' + sourceDetails.join(' · ')));
                }
                card.appendChild(sourceLine);
                streamGrid.appendChild(card);
            });
            section.appendChild(streamGrid);
        }

        if (evidenceList.length) {
            const evidenceGrid = node('div', { className: 'evidence-grid' });
            evidenceList.forEach((item) => {
                if (!isRecord(item)) return;
                const card = node('article', { className: 'evidence-card' });
                const head = node('div', { className: 'evidence-card-head' });
                append(
                    head,
                    heading(4, item.source_key || 'Source', 'evidence-source'),
                    item.as_of ? node('time', { className: 'evidence-time', text: formatDate(item.as_of) }) : null
                );
                card.appendChild(head);
                if (item.observation) card.appendChild(textLine(item.observation, 'evidence-observation'));
                if (item.relevance) {
                    card.appendChild(textLine('Decision relevance: ' + asText(item.relevance), 'evidence-relevance'));
                }
                if (item.limitation) {
                    card.appendChild(textLine('Limitation: ' + asText(item.limitation), 'evidence-limitation'));
                }
                evidenceGrid.appendChild(card);
            });
            section.appendChild(evidenceGrid);
        }
        return section;
    }

    function normalizeActionStep(step, index) {
        if (typeof step === 'string') {
            return {
                step_id: String(index),
                sequence: index + 1,
                title: step,
                objective: '',
                why_it_matters: '',
                actions: [],
                dependencies: [],
                risk_controls: [],
            };
        }
        if (!isRecord(step)) return null;
        return {
            step_id: asText(step.step_id, 'step_' + (index + 1)),
            sequence: clampNumber(step.sequence, 1, 999, index + 1),
            title: asText(step.title || step.objective, 'Step ' + (index + 1)),
            objective: asText(step.objective),
            why_it_matters: asText(step.why_it_matters),
            actions: asArray(step.actions),
            owner: asText(step.owner),
            timebox: asText(step.timebox),
            estimated_cost: asText(step.estimated_cost),
            success_metric: asText(step.success_metric),
            dependencies: asArray(step.dependencies),
            risk_controls: asArray(step.risk_controls),
        };
    }

    function renderDeepDive(panel, data, cached) {
        clear(panel);
        panel.dir = safeDirection(data.lang_dir);
        const content = node('article', { className: 'deep-dive-content' });
        if (data.step_focus) content.appendChild(node('h4', {
            className: 'dd-focus',
            text: data.step_focus,
            translate: false,
        }));
        if (data.detailed_breakdown) {
            const breakdown = textLine(data.detailed_breakdown, 'dd-breakdown', false);
            breakdown.dir = 'auto';
            content.appendChild(breakdown);
        }
        if (data.live_context) appendTextSection(content, 'Available source context', data.live_context, 'dd-block');
        appendListSection(content, 'Assumptions for this step', data.assumptions, 'dd-block');

        const subSteps = asArray(data.sub_steps);
        if (subSteps.length) {
            const block = sectionBlock('Execution sub-steps', 'dd-block');
            const list = node('ol', { className: 'dd-sub-steps' });
            subSteps.forEach((subStep, index) => {
                if (!isRecord(subStep)) return;
                const item = node('li', { className: 'dd-sub-step' });
                item.appendChild(node('h5', {
                    className: 'dd-sub-step-title',
                    text: asText(subStep.sequence, String(index + 1)) + '. ' + asText(subStep.action, 'Action'),
                    translate: false,
                }));
                if (subStep.rationale) {
                    const rationale = textLine(subStep.rationale, 'dd-sub-step-rationale', false);
                    rationale.dir = 'auto';
                    item.appendChild(rationale);
                }
                item.appendChild(detailGrid([
                    ['Duration', subStep.duration],
                    ['Completion evidence', subStep.completion_evidence],
                ], 'detail-grid compact'));
                list.appendChild(item);
            });
            block.appendChild(list);
            content.appendChild(block);
        }

        appendFlexibleCards(content, 'Tools and resources', data.tools_resources, 'dd-block');
        appendFlexibleCards(content, 'Decision checkpoints', data.decision_checkpoints, 'dd-block');
        appendListSection(content, 'Success evidence', data.success_evidence, 'dd-block');
        if (data.pro_tip) {
            const tip = node('aside', { className: 'dd-protip' });
            append(tip, node('strong', { className: 'dd-protip-label', text: 'Practical tip' }), textLine(data.pro_tip, 'dd-protip-text', false));
            content.appendChild(tip);
        }
        if (data.risk_note) {
            const risk = node('aside', { className: 'dd-risk' });
            append(risk, node('strong', { className: 'dd-risk-label', text: 'Risk warning' }), textLine(data.risk_note, 'dd-risk-text', false));
            content.appendChild(risk);
        }
        if (data.next_best_question && refs.followUpInput) {
            const next = node('button', {
                type: 'button',
                className: 'copy-btn',
                text: 'Continue the conversation: ' + asText(data.next_best_question),
            });
            next.addEventListener('click', () => {
                refs.followUpInput.value = asText(data.next_best_question).slice(0, FOLLOW_UP_LIMIT);
                refs.followUpInput.focus();
            });
            content.appendChild(next);
        }
        const executionKit = renderExecutionKit(data.execution_kit);
        if (executionKit) content.appendChild(executionKit);
        content.appendChild(textLine(
            cached ? 'Details were restored from the local cache.' : 'New details were generated for this step.',
            'dd-meta'
        ));
        panel.appendChild(content);
        panel.dataset.loaded = 'true';
        panel.classList.add('is-open');
        panel.hidden = false;
    }

    async function loadDeepDive(step, panel, button) {
        if (!state.currentAnalysisId) {
            announce('Open a valid analysis before requesting details.', true);
            return;
        }
        if (panel.dataset.loaded === 'true') {
            const open = panel.classList.toggle('is-open');
            panel.hidden = !open;
            setUiText(button, open ? 'Close execution details' : 'Step execution details');
            return;
        }
        if (panel.dataset.loading === 'true') return;
        panel.dataset.loading = 'true';
        panel.hidden = false;
        panel.classList.add('is-open');
        clear(panel);
        const loading = node('div', { className: 'deep-dive-loading', role: 'status' });
        append(
            loading,
            node('span', { className: 'loader-sm' }),
            node('span', { className: 'deep-dive-loading-text', text: 'Building practical details for this step…' })
        );
        panel.appendChild(loading);
        button.disabled = true;
        try {
            const payload = await apiRequest('/api/deep-dive', {
                method: 'POST',
                body: {
                    analysis_id: state.currentAnalysisId,
                    step_id: step.step_id,
                    locale: APP_LOCALE,
                },
                timeout: API_TIMEOUT.chat,
                key: 'deep-dive:' + state.currentAnalysisId + ':' + step.step_id,
            });
            const data = unwrapData(payload);
            if (!isRecord(data)) throw new ApiError('The step details have an invalid structure.', 502, 'invalid_deep_dive');
            renderDeepDive(panel, data, Boolean(payload.cached));
            setUiText(button, 'Close execution details');
            if (payload.cached) announce('This step was restored from the local cache without additional model usage.');
            void loadUsage(true);
        } catch (error) {
            clear(panel);
            panel.appendChild(textLine(error.message, 'dd-error'));
            panel.classList.add('is-open');
            setUiText(button, 'Retry step details');
        } finally {
            panel.dataset.loading = 'false';
            button.disabled = false;
        }
    }

    function focusFollowUpForStep(step) {
        if (!refs.followUpInput || !state.currentAnalysisId) return;
        refs.followUpInput.value = t(
            'Discuss this step in more detail: “' + asText(step.title) + '”'
        );
        updateFollowUpCount();
        refs.followUpInput.focus();
        safeScrollIntoView(refs.followUpForm, { block: 'center' });
    }

    function renderActionSteps(steps) {
        const normalized = asArray(steps).map(normalizeActionStep).filter(Boolean);
        if (!normalized.length) return null;
        const section = sectionBlock('Action plan', 'action-section');
        const list = node('ol', { className: 'action-steps' });
        normalized.forEach((step) => {
            const item = node('li', { className: 'action-step-item' });
            const card = node('article', { className: 'action-step-row' });
            const header = node('header', { className: 'action-step-header' });
            append(
                header,
                node('span', { className: 'action-sequence', text: formatNumber(step.sequence) }),
                heading(4, step.title, 'action-step-text')
            );
            card.appendChild(header);
            if (step.objective && step.objective !== step.title) {
                card.appendChild(textLine(step.objective, 'action-objective'));
            }
            if (step.why_it_matters) {
                card.appendChild(textLine('Why it matters: ' + step.why_it_matters, 'action-why'));
            }
            card.appendChild(detailGrid([
                ['Owner', step.owner],
                ['Timebox', step.timebox],
                ['Estimated cost', step.estimated_cost],
                ['Success criterion', step.success_metric],
            ], 'detail-grid action-meta'));

            if (step.actions.length) {
                const actions = node('div', { className: 'action-detail-group' });
                append(actions, heading(5, 'Specific actions', 'dd-block-title'), listBlock(step.actions, 'dd-sub-steps'));
                card.appendChild(actions);
            }
            if (step.dependencies.length) {
                const dependencies = node('div', { className: 'action-detail-group' });
                append(dependencies, heading(5, 'Dependencies', 'dd-block-title'), listBlock(step.dependencies));
                card.appendChild(dependencies);
            }
            if (step.risk_controls.length) {
                const controls = node('div', { className: 'action-detail-group risk-controls' });
                append(controls, heading(5, 'Risk controls', 'dd-block-title'), listBlock(step.risk_controls));
                card.appendChild(controls);
            }

            const controls = node('div', { className: 'action-step-controls' });
            const discuss = node('button', {
                type: 'button',
                className: 'deep-dive-trigger',
                text: 'Discuss this step',
            });
            discuss.addEventListener('click', () => focusFollowUpForStep(step));
            controls.appendChild(discuss);
            const deepDive = node('button', {
                type: 'button',
                className: 'deep-dive-trigger',
                text: 'Step execution details',
            });
            const panel = node('div', { className: 'deep-dive-panel' });
            panel.hidden = true;
            deepDive.disabled = !state.currentAnalysisId;
            deepDive.addEventListener('click', () => void loadDeepDive(step, panel, deepDive));
            controls.appendChild(deepDive);
            card.appendChild(controls);
            item.appendChild(card);
            item.appendChild(panel);
            list.appendChild(item);
        });
        section.appendChild(list);
        return section;
    }

    function renderGoalBlueprint(blueprint) {
        if (!isRecord(blueprint) || !Object.keys(blueprint).length) return null;
        const section = sectionBlock('Trackable goal blueprint', 'goal-blueprint-section');
        if (blueprint.goal_title) section.appendChild(heading(4, blueprint.goal_title, 'goal-blueprint-title'));
        if (blueprint.desired_outcome) section.appendChild(textLine(blueprint.desired_outcome, 'detail-copy'));
        section.appendChild(detailGrid([
            ['Target metric', blueprint.target_metric],
            ['Target value', blueprint.target_value],
            ['Deadline', blueprint.deadline],
            ['Capital ceiling', blueprint.capital_ceiling],
            ['Maximum loss', blueprint.loss_ceiling],
            ['Weekly time commitment', blueprint.weekly_time_commitment],
            ['Review cadence', blueprint.review_cadence],
        ]));

        const milestones = asArray(blueprint.milestones);
        if (milestones.length) {
            const milestoneBlock = node('div', { className: 'milestone-block' });
            milestoneBlock.appendChild(heading(4, 'Milestones', 'dd-block-title'));
            const list = node('ol', { className: 'milestone-list' });
            milestones.forEach((milestone, index) => {
                if (!isRecord(milestone)) return;
                const item = node('li', { className: 'milestone-item' });
                item.appendChild(node('h5', {
                    className: 'milestone-title',
                    text: milestone.title || t('Milestone') + ' ' + formatNumber(index + 1),
                    translate: false,
                }));
                item.appendChild(detailGrid([
                    ['Due window', milestone.due_window],
                    ['Metric', milestone.target_metric],
                    ['Completion evidence', milestone.completion_evidence],
                ], 'detail-grid compact'));
                list.appendChild(item);
            });
            milestoneBlock.appendChild(list);
            section.appendChild(milestoneBlock);
        }
        if (asArray(blueprint.leading_indicators).length) {
            append(section, heading(4, 'Leading indicators', 'dd-block-title'), listBlock(blueprint.leading_indicators));
        }
        if (asArray(blueprint.stop_conditions).length) {
            const stopBlock = node('div', { className: 'stop-conditions' });
            append(stopBlock, heading(4, 'Stop conditions', 'dd-block-title'), listBlock(blueprint.stop_conditions));
            section.appendChild(stopBlock);
        }
        return section;
    }

    function renderRiskAssessment(risk, legacyLevel) {
        if (!isRecord(risk) && !legacyLevel) return null;
        const data = isRecord(risk) ? risk : {};
        const section = sectionBlock('Risk assessment and capital protection', 'risk-assessment-section');
        section.appendChild(detailGrid([
            ['Overall level', semanticLabel(data.overall_level || legacyLevel)],
            ['Capital at risk', data.capital_at_risk],
            ['Worst case', data.worst_case],
            ['Legal and compliance note', data.legal_compliance_note],
        ]));
        if (asArray(data.key_risks).length) {
            append(section, heading(4, 'Key risks', 'dd-block-title'), listBlock(data.key_risks));
        }
        if (asArray(data.stop_conditions).length) {
            append(section, heading(4, 'Emergency brakes', 'dd-block-title'), listBlock(data.stop_conditions));
        }
        return section;
    }

    function renderScenarios(scenarios) {
        if (!isRecord(scenarios)) return null;
        const keys = [
            ['base', 'Base case'],
            ['bull', 'Upside case'],
            ['bear', 'Defensive case'],
        ];
        const available = keys.filter(([key]) => hasValue(scenarios[key]));
        if (!available.length) return null;
        const section = sectionBlock('Scenario test', 'strategic-section');
        const grid = node('div', { className: 'strat-scenarios' });
        available.forEach(([key, label]) => {
            const value = scenarios[key];
            const scenario = isRecord(value) ? value : { description: value };
            const card = node('article', { className: 'strat-scenario ' + key });
            card.appendChild(heading(4, label, 'strat-scn-tag'));
            if (scenario.description) card.appendChild(textLine(scenario.description, 'strat-scn-text'));
            if (asArray(scenario.early_signals).length) {
                append(card, heading(5, 'Early signals', 'dd-block-title'), listBlock(scenario.early_signals));
            }
            if (scenario.response) card.appendChild(textLine('Recommended response: ' + asText(scenario.response), 'scenario-response'));
            grid.appendChild(card);
        });
        section.appendChild(grid);
        return section;
    }

    function renderPredictions(predictions) {
        const items = asArray(predictions);
        if (!items.length) return null;
        const section = sectionBlock('Measurable predictions', 'prediction-section');
        const list = node('div', { className: 'calib-pred-list' });
        items.forEach((prediction) => {
            if (!isRecord(prediction)) return;
            const status = safeStatusClass(prediction.status || 'pending');
            const item = node('article', { className: 'calib-pred-item' });
            const top = node('div', { className: 'calib-pred-top' });
            const direction = asText(prediction.direction).toLowerCase();
            append(
                top,
                node('span', {
                    className: 'calib-pred-metric',
                    text: (direction === 'up' ? '▲ ' : direction === 'down' ? '▼ ' : '') + asText(prediction.metric_label || prediction.metric, 'Metric'),
                }),
                node('span', { className: 'pred-chip pred-' + status, text: predictionStatusLabel(status) })
            );
            item.appendChild(top);
            item.appendChild(detailGrid([
                ['Horizon', prediction.horizon_days ? formatDays(prediction.horizon_days) : ''],
                ['Baseline value', prediction.baseline_value],
                ['Rationale', prediction.rationale],
                ['Evaluation time', prediction.resolve_at ? formatDate(prediction.resolve_at) : ''],
            ], 'detail-grid compact'));
            list.appendChild(item);
        });
        section.appendChild(list);
        return section;
    }

    function renderB2CDetails(data) {
        const hasDetails = hasValue(data.personalized_fit)
            || asArray(data.skill_leverage).length
            || hasValue(data.first_revenue_path)
            || asArray(data.budget_plan).length
            || asArray(data.weekly_schedule).length;
        if (!hasDetails) return null;
        const section = sectionBlock('Personal fit and income path', 'audience-detail-section b2c-detail');
        appendTextSection(section, 'Why does this fit you?', data.personalized_fit);
        appendListSection(section, 'Existing-skill leverage', data.skill_leverage);
        appendTextSection(section, 'Shortest path to first revenue', data.first_revenue_path);
        appendFlexibleCards(section, 'Budget plan', data.budget_plan);
        appendFlexibleCards(section, 'Weekly schedule', data.weekly_schedule);
        return section;
    }

    function renderB2BDetails(data) {
        const hasDetails = hasValue(data.decision_statement)
            || hasValue(data.organization_fit)
            || hasValue(data.financial_case)
            || asArray(data.supply_chain_exposures).length
            || asArray(data.stakeholder_plan).length
            || asArray(data.compliance_checklist).length;
        if (!hasDetails) return null;
        const section = sectionBlock('Business decision case', 'audience-detail-section b2b-detail');
        appendTextSection(section, 'Decision required', data.decision_statement);
        appendTextSection(section, 'Organization fit', data.organization_fit);
        appendTextSection(section, 'Financial case', data.financial_case);
        appendFlexibleCards(section, 'Supply-chain exposures', data.supply_chain_exposures);
        appendFlexibleCards(section, 'Stakeholder plan', data.stakeholder_plan);
        appendFlexibleCards(section, 'Compliance checklist', data.compliance_checklist);
        return section;
    }

    function buildCopyText(data) {
        const lines = [];
        lines.push(asText(data.signal_name, 'AIONEX analysis'));
        if (data.executive_summary) lines.push('', asText(data.executive_summary));
        if (data.root_cause) lines.push('', t('Root-cause logic:'), asText(data.root_cause));
        const steps = asArray(data.action_steps).map(normalizeActionStep).filter(Boolean);
        if (steps.length) {
            lines.push('', t('Action plan') + ':');
            steps.forEach((step) => lines.push(step.sequence + '. ' + step.title));
        }
        if (data.disclaimer) lines.push('', asText(data.disclaimer));
        return lines.join('\n');
    }

    async function copyAnalysis(data, button) {
        try {
            await navigator.clipboard.writeText(buildCopyText(data));
            setUiText(button, 'Copied');
            announce('The analysis summary was copied to your clipboard.');
            window.setTimeout(() => {
                setUiText(button, 'Copy summary');
            }, 1800);
        } catch {
            announce('Your browser did not allow clipboard access.', true);
        }
    }

    function renderLegacyStrategicFields(card, data) {
        if (data.strategic_thesis && !data.executive_summary) {
            appendTextSection(card, 'Strategic thesis', data.strategic_thesis, 'strategic-section');
        }
        appendListSection(card, 'Structural drivers', data.structural_drivers, 'strategic-section');
        appendListSection(card, 'Review triggers', data.review_triggers, 'strategic-section');
        appendTextSection(card, 'Signal reading', data.signals_read);
        appendTextSection(card, 'Historical pattern', data.chronos_basis);
    }

    const RESULT_TABS = Object.freeze([
        ['overview', 'result.tab.overview'],
        ['action', 'result.tab.action'],
        ['evidence', 'result.tab.evidence'],
        ['risks', 'result.tab.risks'],
    ]);

    function activateResultTab(tabShell, tabId, focus = false) {
        if (!tabShell) return;
        const allowed = new Set(RESULT_TABS.map(([id]) => id));
        const selected = allowed.has(tabId) ? tabId : 'overview';
        state.selectedResultTab = selected;
        tabShell.querySelectorAll('[role="tab"]').forEach((button) => {
            const active = button.dataset.resultTab === selected;
            button.setAttribute('aria-selected', active ? 'true' : 'false');
            button.tabIndex = active ? 0 : -1;
            button.classList.toggle('is-active', active);
            if (active && focus) button.focus();
        });
        tabShell.querySelectorAll('[role="tabpanel"]').forEach((panel) => {
            panel.hidden = panel.dataset.resultPanel !== selected;
        });
    }

    function createResultTabs() {
        const shell = node('div', { className: 'result-tabs-shell' });
        const tabList = node('div', { className: 'result-tab-list', role: 'tablist' });
        setUiAttribute(tabList, 'aria-label', 'result.tabs.label');
        const panels = Object.create(null);

        RESULT_TABS.forEach(([id, key]) => {
            const tab = node('button', {
                type: 'button',
                className: 'result-tab',
                text: key,
            });
            tab.id = 'result-tab-' + id;
            tab.dataset.resultTab = id;
            tab.setAttribute('role', 'tab');
            tab.setAttribute('aria-controls', 'result-panel-' + id);
            tab.addEventListener('click', () => activateResultTab(shell, id));
            tab.addEventListener('keydown', (event) => {
                const current = RESULT_TABS.findIndex(([candidate]) => candidate === id);
                let next = current;
                if (event.key === 'Home') next = 0;
                else if (event.key === 'End') next = RESULT_TABS.length - 1;
                else if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                    const direction = event.key === 'ArrowRight' ? 1 : -1;
                    next = (current + direction + RESULT_TABS.length) % RESULT_TABS.length;
                } else {
                    return;
                }
                event.preventDefault();
                activateResultTab(shell, RESULT_TABS[next][0], true);
            });
            tabList.appendChild(tab);

            const panel = node('section', { className: 'result-tab-panel' });
            panel.id = 'result-panel-' + id;
            panel.dataset.resultPanel = id;
            panel.setAttribute('role', 'tabpanel');
            panel.setAttribute('aria-labelledby', tab.id);
            panel.tabIndex = 0;
            panels[id] = panel;
        });

        shell.appendChild(tabList);
        RESULT_TABS.forEach(([id]) => shell.appendChild(panels[id]));
        activateResultTab(shell, state.selectedResultTab);
        return { shell, panels };
    }

    function safeExternalUrl(value) {
        const raw = asText(value).trim();
        if (!raw) return null;
        try {
            const parsed = new URL(raw, window.location.origin);
            if (parsed.protocol !== 'https:') return null;
            if (parsed.username || parsed.password) return null;
            return parsed;
        } catch {
            return null;
        }
    }

    function resourceValue(resource, ...keys) {
        for (const key of keys) {
            if (hasValue(resource[key])) return resource[key];
        }
        return '';
    }

    const EXECUTION_CHANNEL_LABELS = Object.freeze({
        email: 'Email',
        email_or_message: 'Email or message',
        email_or_support_form: 'Email or support form',
        message: 'Message',
        support_form: 'Support form',
    });

    function executionChannelLabel(value) {
        const raw = asText(value);
        const localized = EXECUTION_CHANNEL_LABELS[raw.toLowerCase()];
        return localized || raw.replaceAll('_', ' ');
    }

    function renderExecutionKit(executionKit) {
        if (!isRecord(executionKit)) return null;
        const resources = asArray(executionKit.resources).filter(isRecord);
        const templates = asArray(executionKit.outreach_templates).filter(isRecord);
        const firstDay = asArray(executionKit.first_24_hours).filter(isRecord);
        const guardrails = asArray(executionKit.guardrails).filter(hasValue);
        if (!resources.length && !templates.length && !firstDay.length && !guardrails.length) return null;

        const section = sectionBlock('execution.title', 'execution-kit-section');
        const meta = node('div', { className: 'execution-kit-meta badge-container' });
        if (executionKit.generated_without_ai_call === true || Number(executionKit.additional_model_calls) === 0) {
            meta.appendChild(node('span', { className: 'badge', text: 'execution.noModelCall' }));
        }
        if (Number(executionKit.external_api_cost_usd) === 0) {
            meta.appendChild(node('span', { className: 'badge execution-free-badge', text: 'execution.zeroCost' }));
        }
        if (meta.childElementCount) section.appendChild(meta);

        if (firstDay.length) {
            const firstDayBlock = sectionBlock('execution.first24', 'execution-kit-block execution-first-day');
            const list = node('ol', { className: 'execution-checklist' });
            firstDay.forEach((item, index) => {
                const entry = node('li', { className: 'execution-checklist-item' });
                entry.appendChild(node('h4', {
                    className: 'execution-checklist-title',
                    text: asText(item.title, t('Step') + ' ' + formatNumber(index + 1)),
                    translate: false,
                }));
                const action = resourceValue(item, 'action', 'instruction', 'next_step');
                if (action) {
                    const copy = textLine(action, 'execution-checklist-action', false);
                    copy.dir = 'auto';
                    entry.appendChild(copy);
                }
                entry.appendChild(detailGrid([
                    ['execution.timebox', resourceValue(item, 'timebox', 'duration')],
                    ['execution.evidence', resourceValue(item, 'evidence', 'completion_evidence')],
                    ['execution.cost', resourceValue(item, 'estimated_cost', 'cost')],
                ], 'detail-grid compact'));
                list.appendChild(entry);
            });
            firstDayBlock.appendChild(list);
            section.appendChild(firstDayBlock);
        }

        if (resources.length) {
            const resourcesBlock = sectionBlock('execution.resources', 'execution-kit-block');
            const grid = node('div', { className: 'execution-resource-grid' });
            resources.forEach((resource) => {
                const card = node('article', { className: 'execution-resource-card' });
                const name = asText(resourceValue(resource, 'name', 'title', 'resource_name'), 'Source');
                const accessType = asText(resource.access_type).toLowerCase();
                const header = node('header', { className: 'execution-resource-head' });
                header.appendChild(node('h4', {
                    className: 'execution-resource-title',
                    text: name,
                    translate: false,
                }));
                const badges = node('div', { className: 'badge-container' });
                if (accessType === 'free_account') {
                    badges.appendChild(node('span', { className: 'badge execution-free-badge', text: 'execution.freeAccount' }));
                } else if (accessType === 'freemium') {
                    badges.appendChild(node('span', { className: 'badge', text: 'execution.freemium' }));
                } else if (accessType === 'transaction_fee') {
                    badges.appendChild(node('span', { className: 'badge', text: 'execution.transactionFee' }));
                } else if (accessType === 'free_keyless' || resource.free === true || resource.free_access === true || asText(resource.cost).toLowerCase() === 'free') {
                    badges.appendChild(node('span', { className: 'badge execution-free-badge', text: 'execution.free' }));
                }
                if (resource.official === true || resource.verified === true) {
                    badges.appendChild(node('span', { className: 'badge', text: 'execution.official' }));
                }
                if (resource.requires_account === true) {
                    badges.appendChild(node('span', { className: 'badge', text: 'execution.accountRequired' }));
                } else if (resource.requires_account === false) {
                    badges.appendChild(node('span', { className: 'badge', text: 'execution.noAccount' }));
                }
                if (badges.childElementCount) header.appendChild(badges);
                card.appendChild(header);

                const instruction = resourceValue(resource, 'first_action', 'instruction', 'action', 'how_to_use', 'next_step');
                const reason = resourceValue(resource, 'purpose', 'why', 'reason', 'why_recommended', 'description');
                if (instruction) appendTextSection(card, 'execution.instructions', instruction, 'execution-resource-copy');
                if (reason) appendTextSection(card, 'execution.purpose', reason, 'execution-resource-copy');
                const access = resourceValue(resource, 'access_note', 'access', 'availability');
                const limitation = resourceValue(resource, 'limitation', 'limitations', 'caveat');
                if (access) appendTextSection(card, 'execution.access', access, 'execution-resource-copy');
                if (limitation) appendTextSection(card, 'execution.limitation', limitation, 'execution-resource-copy');
                card.appendChild(detailGrid([
                    ['execution.jurisdiction', resourceValue(resource, 'jurisdiction', 'region')],
                    ['execution.contact', executionChannelLabel(resourceValue(resource, 'contact_channel', 'support_channel'))],
                    ['execution.verified', resourceValue(resource, 'verified_at', 'last_verified')],
                    ['execution.reviewAfter', resourceValue(resource, 'review_after')],
                ], 'detail-grid compact execution-resource-details'));

                const parsedUrl = safeExternalUrl(resourceValue(resource, 'url', 'website', 'source_url'));
                if (parsedUrl) {
                    const link = node('a', { className: 'execution-resource-link' });
                    link.href = parsedUrl.href;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    append(
                        link,
                        node('span', { text: 'execution.open' }),
                        node('span', { className: 'execution-resource-domain', text: parsedUrl.hostname, translate: false })
                    );
                    card.appendChild(link);
                } else if (resourceValue(resource, 'url', 'website', 'source_url')) {
                    card.appendChild(textLine('execution.invalidUrl', 'field-error'));
                }
                const supportUrl = safeExternalUrl(resourceValue(resource, 'support_url', 'contact_url'));
                if (supportUrl) {
                    const supportLink = node('a', { className: 'execution-resource-link execution-support-link' });
                    supportLink.href = supportUrl.href;
                    supportLink.target = '_blank';
                    supportLink.rel = 'noopener noreferrer';
                    append(
                        supportLink,
                        node('span', { text: 'execution.support' }),
                        node('span', { className: 'execution-resource-domain', text: supportUrl.hostname, translate: false })
                    );
                    card.appendChild(supportLink);
                }
                grid.appendChild(card);
            });
            resourcesBlock.appendChild(grid);
            section.appendChild(resourcesBlock);
        }

        if (templates.length) {
            const outreachBlock = sectionBlock('execution.outreach', 'execution-kit-block');
            const list = node('div', { className: 'execution-outreach-list' });
            templates.forEach((template, index) => {
                const card = node('article', { className: 'execution-outreach-card' });
                const title = asText(resourceValue(template, 'title', 'name'), t('execution.outreach') + ' ' + formatNumber(index + 1));
                card.appendChild(node('h4', {
                    className: 'execution-outreach-title',
                    text: title,
                    translate: false,
                }));
                const details = [
                    ['execution.channel', executionChannelLabel(resourceValue(template, 'channel', 'method'))],
                    ['execution.recipient', resourceValue(template, 'recipient', 'recipient_role', 'to')],
                    ['execution.when', resourceValue(template, 'send_when', 'when_to_use', 'timing', 'use_case')],
                    ['execution.subject', resourceValue(template, 'subject')],
                ];
                card.appendChild(detailGrid(details, 'detail-grid compact'));
                const destinationUrl = safeExternalUrl(resourceValue(template, 'destination_url', 'support_url', 'contact_url'));
                if (destinationUrl) {
                    const destinationLink = node('a', { className: 'execution-resource-link execution-support-link' });
                    destinationLink.href = destinationUrl.href;
                    destinationLink.target = '_blank';
                    destinationLink.rel = 'noopener noreferrer';
                    append(
                        destinationLink,
                        node('span', { text: 'execution.support' }),
                        node('span', { className: 'execution-resource-domain', text: destinationUrl.hostname, translate: false })
                    );
                    card.appendChild(destinationLink);
                }
                const customizeFields = asArray(template.customize_fields)
                    .map((field) => asText(field))
                    .filter(Boolean);
                if (customizeFields.length) {
                    appendTextSection(
                        card,
                        'execution.customize',
                        i18n.list(customizeFields),
                        'execution-resource-copy'
                    );
                }
                const doNotSend = resourceValue(template, 'do_not_send_if', 'privacy_note', 'warning');
                if (doNotSend) {
                    appendTextSection(card, 'execution.doNotSend', doNotSend, 'execution-resource-copy');
                }
                const body = asText(resourceValue(template, 'body', 'message', 'template', 'text'));
                if (body) {
                    const messageBlock = sectionBlock('execution.message', 'execution-message-block');
                    const messageCopy = textLine(body, 'execution-message-copy', false);
                    messageCopy.dir = 'auto';
                    messageBlock.appendChild(messageCopy);
                    card.appendChild(messageBlock);
                    const copy = node('button', {
                        type: 'button',
                        className: 'copy-btn',
                        text: 'execution.copy',
                    });
                    copy.addEventListener('click', async () => {
                        try {
                            await navigator.clipboard.writeText(body);
                            announce('execution.copied');
                        } catch {
                            announce('execution.copyFailed', true);
                        }
                    });
                    card.appendChild(copy);
                }
                list.appendChild(card);
            });
            outreachBlock.appendChild(list);
            section.appendChild(outreachBlock);
        }
        if (guardrails.length) {
            const guardrailBlock = sectionBlock('execution.guardrails', 'execution-kit-block execution-guardrails');
            guardrailBlock.appendChild(listBlock(guardrails, 'execution-guardrail-list'));
            section.appendChild(guardrailBlock);
        }
        return section;
    }

    function renderAnalysis(data, intelligence = {}, options = {}) {
        if (!refs.resultsContainer) return;
        renderFollowUpSuggestions([]);
        clear(refs.resultsContainer);
        refs.resultsContainer.hidden = false;
        refs.resultsContainer.classList.remove('hidden');
        refs.resultsContainer.setAttribute('aria-busy', 'false');
        if (refs.conversationEmptyState) refs.conversationEmptyState.hidden = true;

        const card = node('article', { className: 'result-card' });
        card.lang = APP_LOCALE;
        card.tabIndex = -1;

        const header = node('header', { className: 'result-header' });
        const titleWrap = node('div', { className: 'result-heading' });
        titleWrap.appendChild(heading(2, data.signal_name || 'Decision analysis', 'result-title'));
        const badges = node('div', { className: 'badge-container' });
        const audience = asText(data.audience || data.tier, state.tier);
        const horizon = asText(data.horizon_mode, state.horizon);
        const risk = isRecord(data.risk_assessment)
            ? data.risk_assessment.overall_level
            : data.risk_level;
        [
            audience === 'B2B' ? 'Business · B2B' : 'Individual · B2C',
            horizon === 'strategic' ? 'Strategic' : 'Execution-focused',
            risk ? t('Risk:') + ' ' + semanticLabel(risk) : '',
            data.confidence ? t('Confidence:') + ' ' + semanticLabel(data.confidence) : '',
        ].filter(Boolean).forEach((label) => badges.appendChild(node('span', { className: 'badge', text: label })));
        append(titleWrap, badges);
        header.appendChild(titleWrap);
        card.appendChild(header);

        if (data.executive_summary) {
            const summary = sectionBlock('Executive summary', 'executive-summary-section');
            const summaryCopy = textLine(data.executive_summary, 'executive-summary', false);
            summaryCopy.dir = 'auto';
            summary.appendChild(summaryCopy);
            card.appendChild(summary);
        }
        if (data.confidence_reason) {
            card.appendChild(textLine('Confidence rationale: ' + asText(data.confidence_reason), 'confidence-reason'));
        }

        const tabView = createResultTabs();
        card.appendChild(tabView.shell);

        const evidencePanel = renderEvidencePanel(intelligence, data.evidence);
        if (evidencePanel) tabView.panels.evidence.appendChild(evidencePanel);

        appendTextSection(tabView.panels.overview, 'Root-cause logic', data.root_cause, 'root-cause-section');
        renderLegacyStrategicFields(tabView.panels.overview, data);
        appendListSection(tabView.panels.evidence, 'Key assumptions', data.assumptions);
        appendListSection(tabView.panels.evidence, 'Data gaps', data.data_gaps);

        const audiencePanel = audience === 'B2B' ? renderB2BDetails(data) : renderB2CDetails(data);
        if (audiencePanel) tabView.panels.overview.appendChild(audiencePanel);

        const steps = renderActionSteps(data.action_steps);
        if (steps) tabView.panels.action.appendChild(steps);
        const blueprint = renderGoalBlueprint(data.goal_blueprint);
        if (blueprint) tabView.panels.action.appendChild(blueprint);
        const executionKit = renderExecutionKit(data.execution_kit);
        if (executionKit) tabView.panels.action.appendChild(executionKit);
        const riskPanel = renderRiskAssessment(data.risk_assessment, data.risk_level);
        if (riskPanel) tabView.panels.risks.appendChild(riskPanel);
        const scenarios = renderScenarios(data.scenarios);
        if (scenarios) tabView.panels.risks.appendChild(scenarios);
        const predictions = renderPredictions(data.predictions);
        if (predictions) tabView.panels.evidence.appendChild(predictions);

        const actions = node('div', { className: 'result-actions' });
        const copyButton = node('button', {
            id: 'copy-btn',
            type: 'button',
            className: 'copy-btn',
            text: 'Copy summary',
        });
        copyButton.dataset.resultAction = 'copy';
        copyButton.addEventListener('click', () => void copyAnalysis(data, copyButton));
        actions.appendChild(copyButton);

        const memoryButton = node('button', {
            id: 'save-memory-btn',
            type: 'button',
            className: 'copy-btn',
            text: 'Review saved context',
        });
        memoryButton.dataset.resultAction = 'memory';
        memoryButton.addEventListener('click', () => void openMemoryDialog(memoryButton));
        actions.appendChild(memoryButton);

        const goalButton = node('button', {
            id: 'create-goal-btn',
            type: 'button',
            className: 'glow-btn',
            text: 'Turn into goal',
        });
        goalButton.dataset.resultAction = 'goal';
        goalButton.disabled = !state.currentAnalysisId || !isRecord(data.goal_blueprint);
        goalButton.addEventListener('click', () => void createGoalFromCurrent(goalButton));
        actions.appendChild(goalButton);
        card.appendChild(actions);

        const meta = node('footer', { className: 'meta-info' });
        const metaParts = [
            data.cached ? 'Restored from local cache' : '',
            data.execution_time ? 'Processing time: ' + asText(data.execution_time) : '',
            data.data_coverage ? 'Context/data coverage estimate: ' + asText(data.data_coverage) : '',
            data.created_at ? formatDate(data.created_at) : '',
        ].filter(Boolean);
        meta.appendChild(node('span', { text: metaParts.join(' · ') }));
        card.appendChild(meta);

        if (data.disclaimer) {
            card.appendChild(textLine(data.disclaimer, 'intel-disclaimer'));
        } else {
            card.appendChild(textLine(
                'This output is a decision-support tool, not a return guarantee or a substitute for legal or financial advice.',
                'intel-disclaimer'
            ));
        }

        refs.resultsContainer.appendChild(card);
        if (refs.followUpForm) refs.followUpForm.hidden = !state.currentAnalysisId;
        if (refs.newAnalysisButton) refs.newAnalysisButton.hidden = false;
        if (options.focus !== false) {
            window.requestAnimationFrame(() => {
                card.focus({ preventScroll: true });
                safeScrollIntoView(refs.resultsContainer, { block: 'start' });
            });
        }
    }

    function ensureChatList() {
        if (!refs.conversationThread) return null;
        if (state.chatList && state.chatList.isConnected) return state.chatList;
        let list = refs.conversationThread.querySelector('[data-message-list]');
        if (!list) {
            list = node('div', { className: 'conversation-message-list' });
            list.dataset.messageList = 'true';
            refs.conversationThread.appendChild(list);
        }
        state.chatList = list;
        return list;
    }

    function messageRole(role) {
        return asText(role).toLowerCase() === 'user' ? 'user' : 'assistant';
    }

    function createMessageNode(message) {
        const role = messageRole(message && message.role);
        const article = node('article', { className: 'chat-message chat-message-' + role });
        article.dataset.role = role;
        const header = node('header', { className: 'chat-message-head' });
        append(
            header,
            node('span', { className: 'chat-message-author', text: role === 'user' ? 'You' : 'AIONEX' }),
            message && message.created_at
                ? node('time', { className: 'chat-message-time', text: formatDate(message.created_at) })
                : null
        );
        article.appendChild(header);
        const content = textLine(message && message.content, 'chat-message-content', false);
        content.dir = 'auto';
        article.appendChild(content);
        return article;
    }

    function renderMessages(messages) {
        const list = ensureChatList();
        if (!list) return;
        state.messages = asArray(messages).filter(isRecord);
        clear(list);
        state.messages.forEach((message) => {
            if (isRecord(message) && hasValue(message.content)) list.appendChild(createMessageNode(message));
        });
        state.chatExecutionKits.forEach((executionKit) => {
            const section = renderExecutionKit(executionKit);
            if (!section) return;
            section.classList.add('chat-execution-kit');
            list.appendChild(section);
        });
        refs.conversationThread.hidden = false;
    }

    function appendMessage(message) {
        const list = ensureChatList();
        if (!list || !isRecord(message) || !hasValue(message.content)) return;
        const messageNode = createMessageNode(message);
        list.appendChild(messageNode);
        state.messages.push(message);
        window.requestAnimationFrame(() => {
            safeScrollIntoView(list.lastElementChild, { block: 'nearest' });
        });
        return messageNode;
    }

    async function loadMessages(analysisId, silent = false) {
        if (!analysisId || !refs.conversationThread) {
            renderMessages([]);
            return;
        }
        try {
            const payload = await apiRequest(
                '/api/analyses/' + encodeURIComponent(analysisId) + '/messages',
                {
                    timeout: API_TIMEOUT.read,
                    key: 'messages:' + analysisId,
                    silent,
                }
            );
            renderMessages(listFrom(payload, ['messages']));
        } catch (error) {
            if (!silent) showError(refs.followUpError, error.message);
        }
    }

    function updateFollowUpCount() {
        if (!refs.followUpInput) return;
        if (refs.followUpInput.value.length > FOLLOW_UP_LIMIT) {
            refs.followUpInput.value = refs.followUpInput.value.slice(0, FOLLOW_UP_LIMIT);
        }
    }

    function followUpPrompt(value) {
        if (isRecord(value)) return asText(value.prompt || value.text || value.label).trim();
        return asText(value).trim();
    }

    function renderFollowUpSuggestions(suggestions) {
        if (!refs.followUpSuggestions) return;
        const dynamic = asArray(suggestions).map(followUpPrompt).filter(Boolean).slice(0, 4);
        const prompts = dynamic.length ? dynamic : state.defaultFollowUps;
        clear(refs.followUpSuggestions);
        prompts.forEach((prompt) => {
            const button = node('button', { type: 'button', text: prompt });
            button.dataset.followUpPrompt = prompt.slice(0, FOLLOW_UP_LIMIT);
            refs.followUpSuggestions.appendChild(button);
        });
        refs.followUpSuggestions.hidden = prompts.length === 0;
    }

    const MEMORY_CATEGORY_LABELS = Object.freeze({
        preference: 'Preference',
        constraint: 'Constraint',
        resource: 'Source',
        skill: 'Skill',
        goal: 'Goal',
    });

    function normalizeMemoryCandidate(candidate) {
        if (!isRecord(candidate)) return null;
        const category = asText(candidate.category).toLowerCase();
        const content = asText(candidate.content).trim().slice(0, 800);
        if (!Object.prototype.hasOwnProperty.call(MEMORY_CATEGORY_LABELS, category) || content.length < 2) {
            return null;
        }
        return {
            category,
            content,
            whyUseful: asText(candidate.why_useful_later).trim(),
            sensitive: asText(candidate.sensitivity).toLowerCase() === 'sensitive',
        };
    }

    async function saveMemoryCandidate(candidate, button, card) {
        if (!candidate || !button || button.disabled) return;
        button.disabled = true;
        setUiText(button, 'Saving…');
        try {
            await apiRequest('/api/profile/memory', {
                method: 'POST',
                body: {
                    tier: state.tier,
                    category: candidate.category,
                    content: candidate.content,
                },
                timeout: API_TIMEOUT.write,
                key: 'memory-save:' + state.tier + ':' + candidate.category + ':' + candidate.content,
            });
            setUiText(button, 'Saved to memory');
            button.setAttribute('aria-pressed', 'true');
            if (card) card.dataset.saved = 'true';
            announce('This item was saved to long-term memory with your confirmation.');
            await loadProfile(true);
        } catch (error) {
            button.disabled = false;
            setUiText(button, 'Confirm and save to memory');
            announce(error.message, true);
        }
    }

    function renderMemoryCandidates(candidates) {
        const normalized = asArray(candidates).map(normalizeMemoryCandidate).filter(Boolean).slice(0, 4);
        const list = ensureChatList();
        if (!list || !normalized.length) return;
        const section = node('section', { className: 'chat-memory-candidates' });
        setUiAttribute(section, 'aria-label', 'Optional long-term memory suggestions');
        section.appendChild(heading(4, 'What should I remember for next time?', 'memory-candidates-title'));
        section.appendChild(textLine(
            'Only these suggested long-term memory items require confirmation. Analysis context may already be saved for this browser.',
            'memory-candidates-intro'
        ));
        normalized.forEach((candidate) => {
            const card = node('article', { className: 'memory-candidate-card' });
            const meta = node('div', { className: 'memory-candidate-meta' });
            meta.appendChild(node('span', {
                className: 'badge',
                text: MEMORY_CATEGORY_LABELS[candidate.category],
            }));
            if (candidate.sensitive) {
                meta.appendChild(node('span', { className: 'badge badge-warning', text: 'Sensitive' }));
            }
            append(card, meta, textLine(candidate.content, 'memory-candidate-content'));
            if (candidate.whyUseful) {
                card.appendChild(textLine('Future use: ' + candidate.whyUseful, 'memory-candidate-reason'));
            }
            const saveButton = node('button', {
                type: 'button',
                className: 'copy-btn memory-candidate-save',
                text: 'Confirm and save to memory',
            });
            saveButton.addEventListener('click', () => void saveMemoryCandidate(candidate, saveButton, card));
            card.appendChild(saveButton);
            section.appendChild(card);
        });
        list.appendChild(section);
        window.requestAnimationFrame(() => safeScrollIntoView(section, { block: 'nearest' }));
    }

    async function sendFollowUp() {
        if (state.chatBusy || !refs.followUpInput || !state.currentAnalysisId) return;
        clearError(refs.followUpError);
        const message = refs.followUpInput.value.trim();
        if (!message) {
            showError(refs.followUpError, 'Write your message.');
            refs.followUpInput.focus();
            return;
        }
        if (message.length > FOLLOW_UP_LIMIT) {
            showError(refs.followUpError, 'The message is longer than the allowed limit.');
            return;
        }

        state.chatBusy = true;
        if (refs.followUpButton) refs.followUpButton.disabled = true;
        const optimisticData = {
            role: 'user',
            content: message,
            created_at: new Date().toISOString(),
        };
        const optimisticMessage = appendMessage(optimisticData);
        refs.followUpInput.value = '';
        setStatus('Answering within the context of this analysis…', true);
        try {
            const payload = await apiRequest('/api/chat', {
                method: 'POST',
                body: { analysis_id: state.currentAnalysisId, message, locale: APP_LOCALE },
                timeout: API_TIMEOUT.chat,
                key: 'chat:' + state.currentAnalysisId,
            });
            const data = unwrapData(payload);
            const assistantMessage = isRecord(data) && isRecord(data.message) ? data.message : null;
            if (assistantMessage) appendMessage(assistantMessage);
            else throw new ApiError('The conversation response has an invalid structure.', 502, 'invalid_chat');
            renderFollowUpSuggestions(isRecord(data) ? data.suggestions : []);
            renderMemoryCandidates(isRecord(data) ? data.memory_candidates : []);
            const rawExecutionKit = (isRecord(data) && data.execution_kit)
                || (assistantMessage && assistantMessage.execution_kit)
                || (isRecord(payload) && payload.execution_kit);
            const executionKit = renderExecutionKit(rawExecutionKit);
            const chatList = ensureChatList();
            if (executionKit && chatList) {
                state.chatExecutionKits.push(rawExecutionKit);
                executionKit.classList.add('chat-execution-kit');
                chatList.appendChild(executionKit);
                window.requestAnimationFrame(() => safeScrollIntoView(executionKit, { block: 'nearest' }));
            }
            if (Boolean(payload.cached)) {
                announce('A similar answer was restored from the local cache without an additional model call.');
            }
            stopStatusSequence('Your follow-up answer is ready.');
            void loadUsage(true);
        } catch (error) {
            stopStatusSequence('');
            showError(refs.followUpError, error.message);
            refs.followUpInput.value = message;
            if (optimisticMessage?.isConnected) optimisticMessage.remove();
            state.messages = state.messages.filter((item) => item !== optimisticData);
        } finally {
            state.chatBusy = false;
            if (refs.followUpButton) refs.followUpButton.disabled = false;
        }
    }

    function openDialog(dialog, trigger = null) {
        if (!dialog) return;
        if (trigger) state.lastDialogTrigger.set(dialog, trigger);
        if (typeof dialog.showModal === 'function') {
            if (!dialog.open) dialog.showModal();
        } else {
            dialog.hidden = false;
            dialog.classList.remove('hidden');
            dialog.setAttribute('open', '');
            dialog.setAttribute('role', 'dialog');
            dialog.setAttribute('aria-modal', 'true');
        }
        window.requestAnimationFrame(() => {
            const first = dialog.querySelector(
                'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex="0"]'
            );
            if (first) first.focus({ preventScroll: true });
        });
    }

    function closeDialog(dialog) {
        if (!dialog) return;
        if (typeof dialog.close === 'function' && dialog.open) {
            dialog.close();
        } else {
            dialog.removeAttribute('open');
            dialog.hidden = true;
            dialog.classList.add('hidden');
        }
        const trigger = state.lastDialogTrigger.get(dialog);
        if (trigger && trigger.isConnected) trigger.focus({ preventScroll: true });
    }

    function setPanelLoading(container, message = 'Loading information…') {
        if (!container) return;
        clear(container);
        const wrap = node('div', { className: 'panel-loading', role: 'status' });
        append(wrap, node('span', { className: 'loader-sm' }), node('span', { text: message }));
        container.appendChild(wrap);
    }

    function setPanelEmpty(container, message) {
        if (!container) return;
        clear(container);
        container.appendChild(textLine(message, 'panel-empty calib-empty'));
    }

    function normalizeVaultEntry(item) {
        if (!isRecord(item)) return null;
        const data = isRecord(item.data) ? item.data : item;
        const intelligence = isRecord(item.intelligence)
            ? item.intelligence
            : isRecord(data.intelligence_snapshot)
                ? data.intelligence_snapshot
                : {};
        return {
            data,
            intelligence,
            id: asText(data.analysis_id || item.id || data.id),
            title: asText(data.signal_name || data.title, 'Saved analysis'),
            query: asText(data.original_query || item.query),
            createdAt: data.created_at || item.created_at || data.timestamp,
            tier: asText(data.audience || data.tier || item.tier, 'B2C'),
            confidence: asText(data.confidence),
        };
    }

    function hasCompleteStoredAnalysis(data) {
        return isRecord(data)
            && asText(data.analysis_id).length >= 8
            && asText(data.executive_summary).length > 0
            && asArray(data.action_steps).length > 0;
    }

    async function restoreVaultEntry(entry) {
        let resolved = entry;
        let hydrated = false;
        announce('vault.hydrating');
        try {
            const payload = await apiRequest('/api/analyses/' + encodeURIComponent(entry.id), {
                timeout: API_TIMEOUT.read,
                key: 'vault-detail:' + entry.id,
                silent: true,
            });
            const fresh = normalizeVaultEntry(payload);
            if (fresh) {
                resolved = fresh;
                hydrated = true;
            }
        } catch {
            // Older servers may still return a complete analysis in each Vault
            // row. Keep that compatibility, but never try to render a modern
            // lightweight summary as if it were the complete analysis.
            if (!hasCompleteStoredAnalysis(entry.data)) {
                announce('vault.unavailable', true);
                return;
            }
        }
        state.currentAnalysis = resolved.data;
        state.currentIntelligence = resolved.intelligence;
        state.currentAnalysisId = resolved.id;
        if (resolved.tier === 'B2B' || resolved.tier === 'B2C') setTier(resolved.tier);
        setHorizon(asText(resolved.data.horizon_mode) === 'strategic' ? 'strategic' : 'instant');
        renderAnalysis(resolved.data, resolved.intelligence);
        closeDialog(refs.vaultDialog);
        await loadMessages(resolved.id, true);
        announce(hydrated ? 'vault.hydrated' : 'vault.fallback');
    }

    function renderVaultEntries(entries) {
        if (!refs.vaultList) return;
        clear(refs.vaultList);
        if (!entries.length) {
            setPanelEmpty(
                refs.vaultList,
                state.vaultEntries.length
                    ? 'No analysis matches the current search and filter.'
                    : 'No analysis has been saved to history yet.'
            );
            return;
        }
        entries.forEach((entry) => {
            const button = node('button', { type: 'button', className: 'vault-item' });
            button.dir = safeDirection(entry.data.lang_dir);
            const head = node('span', { className: 'vault-item-title' });
            append(
                head,
                node('span', { text: entry.title }),
                node('span', {
                    className: 'badge',
                    text: (entry.tier === 'B2B' ? 'B2B' : 'B2C') + (entry.confidence ? ' · ' + entry.confidence : ''),
                })
            );
            button.appendChild(head);
            if (entry.query) button.appendChild(node('span', { className: 'vault-item-query', text: entry.query }));
            if (entry.createdAt) {
                button.appendChild(node('time', { className: 'meta-info', text: formatDate(entry.createdAt) }));
            }
            button.addEventListener('click', () => void restoreVaultEntry(entry));
            refs.vaultList.appendChild(button);
        });
    }

    function applyVaultFilters() {
        const localeTag = APP_LOCALE;
        const search = refs.vaultSearchInput ? refs.vaultSearchInput.value.trim().toLocaleLowerCase(localeTag) : '';
        const filter = refs.vaultFilter ? refs.vaultFilter.value : 'all';
        const filtered = state.vaultEntries.filter((entry) => {
            const tierMatches = filter === 'all' || entry.tier === filter;
            const haystack = (entry.title + ' ' + entry.query).toLocaleLowerCase(localeTag);
            return tierMatches && (!search || haystack.includes(search));
        });
        renderVaultEntries(filtered);
    }

    function renderVault(items) {
        state.vaultEntries = asArray(items).map(normalizeVaultEntry).filter(Boolean);
        if (refs.vaultCountBadge) {
            refs.vaultCountBadge.textContent = formatNumber(state.vaultEntries.length);
            refs.vaultCountBadge.hidden = state.vaultEntries.length === 0;
        }
        applyVaultFilters();
    }

    async function openVaultDialog(trigger) {
        openDialog(refs.vaultDialog, trigger);
        if (refs.vaultSearchInput) refs.vaultSearchInput.value = '';
        if (refs.vaultFilter) refs.vaultFilter.value = 'all';
        setPanelLoading(refs.vaultList, 'Loading browser-scoped history…');
        try {
            const payload = await apiRequest('/api/vault', {
                timeout: API_TIMEOUT.read,
                key: 'vault',
            });
            renderVault(listFrom(payload, ['analyses', 'items']));
        } catch (error) {
            setPanelEmpty(refs.vaultList, error.message);
        }
    }

    function goalStatusLabel(status) {
        return t({
            active: 'Active',
            paused: 'Paused',
            completed: 'Completed',
            archived: 'Archived',
        }[asText(status).toLowerCase()] || 'Active');
    }

    function renderGoalPreview(goal) {
        if (!refs.activeGoalPreview) return;
        let dynamic = refs.activeGoalPreview.querySelector('[data-goal-preview-data]');
        if (!dynamic) {
            dynamic = node('div', { className: 'context-preview-data' });
            dynamic.dataset.goalPreviewData = 'true';
            refs.activeGoalPreview.insertBefore(dynamic, refs.activeGoalPreview.querySelector('.context-link'));
        }
        clear(dynamic);
        const summaryText = refs.activeGoalPreview.querySelector('[data-goal-preview-text]');
        if (!isRecord(goal)) {
            if (summaryText) setUiText(summaryText, 'You do not have an active goal yet.');
            dynamic.hidden = true;
            return;
        }
        dynamic.hidden = false;
        if (summaryText) summaryText.textContent = asText(goal.title, t('Active goal'));
        const progress = clampNumber(goal.progress, 0, 100, 0);
        const progressNode = node('progress');
        progressNode.max = 100;
        progressNode.value = progress;
        setUiAttribute(progressNode, 'aria-label', 'Goal progress');
        dynamic.appendChild(progressNode);
        dynamic.appendChild(textLine(
            formatPercent(progress) + ' · ' + goalStatusLabel(goal.status),
            'context-preview-meta'
        ));
    }

    async function patchGoal(goalId, patch, button = null) {
        if (state.goalBusy || !goalId) return;
        state.goalBusy = true;
        if (button) button.disabled = true;
        try {
            const payload = await apiRequest('/api/goals/' + encodeURIComponent(goalId), {
                method: 'PATCH',
                body: patch,
                timeout: API_TIMEOUT.write,
                key: 'goal-patch:' + goalId,
            });
            const goal = unwrapData(payload);
            if (!isRecord(goal)) throw new ApiError('The goal was not updated.', 502, 'invalid_goal');
            state.currentGoal = goal;
            announce('Goal updated.');
            await loadGoals(false, true);
        } catch (error) {
            announce(error.message, true);
        } finally {
            state.goalBusy = false;
            if (button) button.disabled = false;
        }
    }

    function createGoalCard(goal) {
        const card = node('article', { className: 'goal-card vault-item' });
        const head = node('header', { className: 'vault-item-title' });
        append(
            head,
            heading(3, goal.title || 'Goal', 'goal-card-title'),
            node('span', {
                className: 'badge goal-status-' + safeStatusClass(goal.status),
                text: goalStatusLabel(goal.status),
            })
        );
        card.appendChild(head);
        const blueprint = isRecord(goal.blueprint) ? goal.blueprint : {};
        if (blueprint.desired_outcome) card.appendChild(textLine(blueprint.desired_outcome, 'goal-outcome'));

        const progressValue = clampNumber(goal.progress, 0, 100, 0);
        const progressLabel = node('label', { className: 'goal-progress-label' });
        progressLabel.appendChild(node('span', {
            text: t('Progress:') + ' ' + formatPercent(progressValue) + ' · manual',
        }));
        const progress = node('input', { type: 'range' });
        progress.min = '0';
        progress.max = '100';
        progress.step = '5';
        progress.value = String(progressValue);
        setUiAttribute(progress, 'aria-label', 'Goal progress percentage');
        progress.addEventListener('input', () => {
            setUiText(progressLabel.firstElementChild, 'Progress: ' + formatPercent(Number(progress.value)) + ' · manual');
        });
        progressLabel.appendChild(progress);
        card.appendChild(progressLabel);

        const checkInLabel = node('label', { className: 'goal-checkin-label' });
        checkInLabel.appendChild(node('span', { text: 'Next check-in' }));
        const checkIn = node('input', { type: 'date' });
        if (/^\d{4}-\d{2}-\d{2}$/.test(asText(goal.next_check_in))) checkIn.value = goal.next_check_in;
        checkInLabel.appendChild(checkIn);
        card.appendChild(checkInLabel);

        card.appendChild(detailGrid([
            ['Deadline', goal.target_date || blueprint.deadline],
            ['Last updated', goal.updated_at ? formatDate(goal.updated_at) : ''],
        ], 'detail-grid compact'));

        const controls = node('div', { className: 'goal-card-actions' });
        const save = node('button', { type: 'button', className: 'glow-btn', text: 'Save progress' });
        save.addEventListener('click', () => void patchGoal(goal.id, {
            progress: Number(progress.value),
            next_check_in: checkIn.value || null,
        }, save));
        controls.appendChild(save);

        const pause = node('button', {
            type: 'button',
            className: 'copy-btn',
            text: goal.status === 'paused' ? 'Activate' : 'Pause',
        });
        pause.addEventListener('click', () => void patchGoal(
            goal.id,
            { status: goal.status === 'paused' ? 'active' : 'paused' },
            pause
        ));
        controls.appendChild(pause);

        const complete = node('button', { type: 'button', className: 'copy-btn', text: 'Complete goal' });
        complete.disabled = goal.status === 'completed';
        complete.addEventListener('click', () => void patchGoal(goal.id, {
            progress: 100,
            status: 'completed',
        }, complete));
        controls.appendChild(complete);

        const archive = node('button', { type: 'button', className: 'copy-btn', text: 'Archive' });
        archive.addEventListener('click', () => void patchGoal(goal.id, { status: 'archived' }, archive));
        controls.appendChild(archive);
        card.appendChild(controls);
        return card;
    }

    function renderGoals(goals) {
        if (!refs.goalsList) return;
        clear(refs.goalsList);
        const items = asArray(goals).filter(isRecord);
        state.goals = items;
        const activeCount = items.filter((goal) => goal.status === 'active' || goal.status === 'paused').length;
        const completedCount = items.filter((goal) => goal.status === 'completed').length;
        if (refs.activeGoalsCount) refs.activeGoalsCount.textContent = formatNumber(activeCount);
        if (refs.completedGoalsCount) refs.completedGoalsCount.textContent = formatNumber(completedCount);
        const active = items.find((goal) => goal.status === 'active') || items[0] || null;
        state.currentGoal = active;
        renderGoalPreview(active);
        if (!items.length) {
            setPanelEmpty(refs.goalsList, 'You do not have a goal yet. Convert an analysis or create one manually.');
            return;
        }
        items.forEach((goal) => refs.goalsList.appendChild(createGoalCard(goal)));
    }

    async function loadGoals(open = false, silent = false, trigger = null) {
        if (open) {
            openDialog(refs.goalsDialog, trigger);
            setPanelLoading(refs.goalsList, 'Loading goals…');
        }
        try {
            const payload = await apiRequest('/api/goals', {
                timeout: API_TIMEOUT.read,
                key: 'goals',
                silent,
            });
            renderGoals(listFrom(payload, ['goals']));
        } catch (error) {
            if (open) setPanelEmpty(refs.goalsList, error.message);
            else renderGoalPreview(null);
        }
    }

    async function createGoalFromCurrent(button = null) {
        if (!state.currentAnalysisId || state.goalBusy) {
            announce('Create or open a valid analysis first.', true);
            return;
        }
        state.goalBusy = true;
        if (button) button.disabled = true;
        try {
            const payload = await apiRequest('/api/goals/from-analysis', {
                method: 'POST',
                body: { analysis_id: state.currentAnalysisId, locale: APP_LOCALE },
                timeout: API_TIMEOUT.write,
                key: 'goal-from-analysis:' + state.currentAnalysisId,
            });
            const goal = unwrapData(payload);
            if (!isRecord(goal)) throw new ApiError('The goal was not created.', 502, 'invalid_goal');
            state.currentGoal = goal;
            renderGoalPreview(goal);
            announce('The analysis blueprint became a trackable goal.');
            if (button) setUiText(button, 'Goal created');
            void loadGoals(false, true);
        } catch (error) {
            announce(error.message, true);
            if (button) button.disabled = false;
        } finally {
            state.goalBusy = false;
        }
    }

    function validDateInput(value) {
        return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : undefined;
    }

    async function createManualGoal() {
        if (state.goalBusy) return;
        const title = refs.goalTitleInput ? refs.goalTitleInput.value.trim() : '';
        const target = refs.goalTargetInput ? refs.goalTargetInput.value.trim() : '';
        if (title.length < 3 || target.length < 3) {
            announce('Complete the goal title and measurable outcome.', true);
            return;
        }
        state.goalBusy = true;
        if (refs.goalSaveButton) refs.goalSaveButton.disabled = true;
        const body = {
            tier: state.tier,
            locale: APP_LOCALE,
            title,
            target,
        };
        const deadline = refs.goalDeadlineInput ? validDateInput(refs.goalDeadlineInput.value) : undefined;
        const weeklyTime = refs.goalTimeInput ? refs.goalTimeInput.value.trim() : '';
        const budget = refs.goalBudgetInput ? refs.goalBudgetInput.value.trim() : '';
        if (deadline) body.deadline = deadline;
        if (weeklyTime) body.weekly_time = weeklyTime;
        if (budget) body.budget = budget;
        try {
            const payload = await apiRequest('/api/goals', {
                method: 'POST',
                body,
                timeout: API_TIMEOUT.write,
                key: 'goal-create',
            });
            const goal = unwrapData(payload);
            if (!isRecord(goal)) throw new ApiError('The goal was not created.', 502, 'invalid_goal');
            refs.goalForm?.reset();
            if (refs.goalEditor) refs.goalEditor.hidden = true;
            state.currentGoal = goal;
            announce('The manual goal was created without an AI call.');
            await loadGoals(false, true);
        } catch (error) {
            announce(error.message, true);
        } finally {
            state.goalBusy = false;
            if (refs.goalSaveButton) refs.goalSaveButton.disabled = false;
        }
    }

    function memoryFacts(profile) {
        const memory = isRecord(profile) && isRecord(profile.memory) ? profile.memory : {};
        return isRecord(memory.facts) ? memory.facts : {};
    }

    function memoryCategory(key) {
        const token = asText(key).toLowerCase();
        if (/(budget|capital|loss|time|hour|deadline|constraint|jurisdiction|country|excluded|compliance)/.test(token)) {
            return 'constraint';
        }
        if (/(preference|risk|online|offline|sector|channel|style|horizon|target)/.test(token)) {
            return 'preference';
        }
        return 'profile';
    }

    function memoryKeyLabel(key) {
        const raw = asText(key);
        const prefix = raw.split(':', 1)[0].toLowerCase();
        return MEMORY_CATEGORY_LABELS[prefix] || FIELD_LABELS[raw] || raw.replaceAll('_', ' ');
    }

    function renderMemoryPreview(profile) {
        if (!refs.memoryPreview) return;
        let dynamic = refs.memoryPreview.querySelector('[data-memory-preview-data]');
        if (!dynamic) {
            dynamic = node('div', { className: 'context-preview-data' });
            dynamic.dataset.memoryPreviewData = 'true';
            refs.memoryPreview.insertBefore(dynamic, refs.memoryPreview.querySelector('.context-link'));
        }
        clear(dynamic);
        const facts = Object.entries(memoryFacts(profile)).filter((entry) => hasValue(entry[1]));
        if (!facts.length) {
            dynamic.appendChild(textLine('No facts are saved yet.', 'context-empty'));
            return;
        }
        facts.slice(0, 3).forEach(([key, value]) => {
            const row = node('div', { className: 'memory-preview-row' });
            append(
                row,
                node('span', { className: 'memory-preview-key', text: memoryKeyLabel(key) }),
                node('span', { className: 'memory-preview-value', text: describeObject(value) })
            );
            dynamic.appendChild(row);
        });
    }

    function renderMemory(profile) {
        state.currentProfile = isRecord(profile) ? profile : null;
        if (!refs.memoryList) {
            renderMemoryPreview(profile);
            return;
        }
        clear(refs.memoryList);
        const allFacts = Object.entries(memoryFacts(profile)).filter((entry) => hasValue(entry[1]));
        const facts = state.memoryFilter === 'all'
            ? allFacts
            : allFacts.filter(([key]) => memoryCategory(key) === state.memoryFilter);
        const memory = isRecord(profile) && isRecord(profile.memory) ? profile.memory : {};
        const allRecent = asArray(memory.recent_contexts);
        const recent = state.memoryFilter === 'all' ? allRecent : [];
        const overallEmpty = !allFacts.length && !allRecent.length;
        if (refs.memoryEmpty) refs.memoryEmpty.hidden = !overallEmpty;
        refs.memoryList.hidden = overallEmpty;
        if (!overallEmpty && !facts.length && !recent.length) {
            refs.memoryList.appendChild(textLine('There are no items in this category.', 'panel-empty'));
        }

        if (facts.length) {
            const factSection = sectionBlock('Saved long-term facts', 'memory-section');
            const list = node('dl', { className: 'memory-fact-list' });
            facts.forEach(([key, value]) => {
                const row = node('div', { className: 'memory-fact-row' });
                append(
                    row,
                    node('dt', { text: memoryKeyLabel(key) }),
                    node('dd', { text: describeObject(value) })
                );
                list.appendChild(row);
            });
            factSection.appendChild(list);
            refs.memoryList.appendChild(factSection);
        }
        if (recent.length) {
            const recentSection = sectionBlock('Automatically saved analysis context', 'memory-section');
            recentSection.appendChild(listBlock(recent));
            refs.memoryList.appendChild(recentSection);
        }
        if (isRecord(profile) && profile.updated_at) {
            refs.memoryList.appendChild(textLine('Last updated: ' + formatDate(profile.updated_at), 'meta-info'));
        }
        renderMemoryPreview(profile);
    }

    async function loadProfile(silent = false) {
        try {
            const payload = await apiRequest('/api/profile?tier=' + encodeURIComponent(state.tier), {
                timeout: API_TIMEOUT.read,
                key: 'profile:' + state.tier,
                silent,
            });
            const profile = unwrapData(payload);
            renderMemory(isRecord(profile) ? profile : {});
            return profile;
        } catch (error) {
            if (!silent) setPanelEmpty(refs.memoryList, error.message);
            else renderMemoryPreview(null);
            return null;
        }
    }

    async function openMemoryDialog(trigger) {
        openDialog(refs.memoryDialog, trigger);
        if (refs.memoryEmpty) refs.memoryEmpty.hidden = true;
        if (refs.memoryList) {
            refs.memoryList.hidden = false;
            setPanelLoading(refs.memoryList, 'Loading saved context…');
        }
        await loadProfile(false);
    }

    async function clearMemory() {
        if (!window.confirm(t(
            'Delete all saved context for the ' + state.tier + ' path? This cannot be undone.'
        ))) {
            return;
        }
        if (refs.memoryClearButton) refs.memoryClearButton.disabled = true;
        try {
            await apiRequest('/api/profile?tier=' + encodeURIComponent(state.tier), {
                method: 'DELETE',
                timeout: API_TIMEOUT.write,
                key: 'profile-delete:' + state.tier,
            });
            renderMemory({ tier: state.tier, memory: {}, updated_at: null });
            announce('Saved context for this path was deleted.');
        } catch (error) {
            announce(error.message, true);
        } finally {
            if (refs.memoryClearButton) refs.memoryClearButton.disabled = false;
        }
    }

    function exportMemory() {
        const profile = state.currentProfile;
        if (!isRecord(profile)) {
            announce('There is no saved context to export.', true);
            return;
        }
        const blob = new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = node('a');
        link.href = url;
        link.download = 'aionex-saved-context-' + state.tier.toLowerCase() + '.json';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
        announce('A portable saved-context export is ready.');
    }

    function renderUsagePreview(summary) {
        if (!refs.usagePreview) return;
        let dynamic = refs.usagePreview.querySelector('[data-usage-preview-data]');
        if (!dynamic) {
            dynamic = node('div', { className: 'context-preview-data' });
            dynamic.dataset.usagePreviewData = 'true';
            refs.usagePreview.appendChild(dynamic);
        }
        clear(dynamic);
        if (!isRecord(summary)) {
            dynamic.appendChild(textLine('Usage statistics are unavailable.', 'context-empty'));
            return;
        }
        const requests = clampNumber(summary.requests, 0, Number.MAX_SAFE_INTEGER, 0);
        const inputTokens = clampNumber(summary.input_tokens, 0, Number.MAX_SAFE_INTEGER, 0);
        const outputTokens = clampNumber(summary.output_tokens, 0, Number.MAX_SAFE_INTEGER, 0);
        const cached = clampNumber(summary.cached_requests, 0, Number.MAX_SAFE_INTEGER, 0);
        dynamic.appendChild(detailGrid([
            ['Requests', formatNumber(requests)],
            ['Input tokens', formatNumber(inputTokens)],
            ['Output tokens', formatNumber(outputTokens)],
            ['Cache hits', formatNumber(cached)],
        ], 'detail-grid compact'));
    }

    async function loadUsage(silent = false) {
        try {
            const payload = await apiRequest('/api/usage', {
                timeout: API_TIMEOUT.read,
                key: 'usage',
                silent,
            });
            const summary = unwrapData(payload);
            state.currentUsage = isRecord(summary) ? summary : null;
            renderUsagePreview(state.currentUsage);
            return state.currentUsage;
        } catch {
            renderUsagePreview(null);
            return null;
        }
    }

    function percentageText(value) {
        if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
        return formatPercent(clampNumber(value, 0, 100, 0));
    }

    function calibrationBar(label, band) {
        const data = isRecord(band) ? band : {};
        const row = node('div', { className: 'calib-band-row' });
        const head = node('div', { className: 'calib-band-head' });
        const decided = clampNumber(data.correct, 0, 1000000, 0)
            + clampNumber(data.incorrect, 0, 1000000, 0);
        append(
            head,
            node('span', { className: 'calib-band-name', text: label }),
            node('span', {
                className: 'calib-band-val',
                text: percentageText(data.win_rate) + ' · ' + formatOutcomes(decided),
            })
        );
        const bar = node('progress', { className: 'calib-bar calib-bar-fill' });
        bar.max = 100;
        bar.value = clampNumber(data.win_rate, 0, 100, 0);
        bar.textContent = percentageText(data.win_rate);
        bar.setAttribute('aria-label', label + ': ' + percentageText(data.win_rate));
        append(row, head, bar);
        return row;
    }

    function predictionStatusLabel(status) {
        return t({
            correct: 'Correct',
            incorrect: 'Incorrect',
            flat: 'Flat',
            pending: 'Pending',
        }[asText(status).toLowerCase()] || 'Pending');
    }

    function calibrationPrediction(prediction) {
        const status = ['correct', 'incorrect', 'flat', 'pending'].includes(asText(prediction.status).toLowerCase())
            ? asText(prediction.status).toLowerCase()
            : 'pending';
        const card = node('article', { className: 'calib-pred-item' });
        card.dir = safeDirection(prediction.lang_dir);
        const top = node('div', { className: 'calib-pred-top' });
        append(
            top,
            node('span', {
                className: 'calib-pred-metric',
                text: asText(prediction.metric_label || prediction.metric, t('Metric'))
                    + ' · ' + semanticLabel(prediction.direction),
            }),
            node('span', { className: 'pred-chip pred-' + status, text: predictionStatusLabel(status) })
        );
        card.appendChild(top);
        card.appendChild(textLine(
            [
                prediction.baseline_value !== undefined ? t('Baseline') + ' ' + asText(prediction.baseline_value) : '',
                prediction.horizon_days ? formatDays(prediction.horizon_days) : '',
                prediction.move_pct !== undefined
                    ? t('Move') + ' ' + formatPercent(prediction.move_pct)
                    : '',
            ].filter(Boolean).join(' · '),
            'calib-pred-mid',
            false
        ));
        if (prediction.signal_name) card.appendChild(textLine(prediction.signal_name, 'calib-pred-sig'));
        return card;
    }

    function renderTrackRecord(stats, predictions, usage) {
        if (!refs.calibrationBody) return;
        clear(refs.calibrationBody);
        const summary = isRecord(stats) ? stats : {};
        const top = node('section', { className: 'calib-summary' });
        top.appendChild(node('div', {
            className: 'calib-winrate',
            text: summary.win_rate === null || summary.win_rate === undefined
                ? 'Not enough observations'
                : percentageText(summary.win_rate),
        }));
        top.appendChild(textLine(
            [
                summary.correct !== undefined ? asText(summary.correct) + ' ' + t('Correct') : '',
                summary.incorrect !== undefined ? asText(summary.incorrect) + ' ' + t('Incorrect') : '',
                summary.flat !== undefined ? asText(summary.flat) + ' ' + t('Flat') : '',
                summary.pending !== undefined ? asText(summary.pending) + ' ' + t('Pending') : '',
            ].filter(Boolean).join(' · '),
            'calib-sub',
            false
        ));
        refs.calibrationBody.appendChild(top);

        if (isRecord(summary.by_band)) {
            const bandSection = sectionBlock('Directional accuracy by confidence band');
            const bands = node('div', { className: 'calib-bands' });
            ['High', 'Moderate', 'Low'].forEach((band) => {
                if (isRecord(summary.by_band[band])) {
                    bands.appendChild(calibrationBar(semanticLabel(band), summary.by_band[band]));
                }
            });
            bandSection.appendChild(bands);
            refs.calibrationBody.appendChild(bandSection);
        }

        if (isRecord(summary.by_metric) && Object.keys(summary.by_metric).length) {
            const metricSection = sectionBlock('Performance by metric');
            const grid = node('div', { className: 'calib-metric-grid' });
            Object.entries(summary.by_metric).forEach(([key, metric]) => {
                if (!isRecord(metric)) return;
                const card = node('article', { className: 'calib-metric-card' });
                append(
                    card,
                    node('div', { className: 'calib-metric-name', text: metric.label || key }),
                    node('div', { className: 'calib-metric-val', text: percentageText(metric.win_rate) }),
                    node('div', {
                        className: 'calib-metric-sub',
                        text: asText(metric.correct, '0') + ' ' + t('Correct') + ' · '
                            + asText(metric.incorrect, '0') + ' ' + t('Incorrect'),
                        translate: false,
                    })
                );
                grid.appendChild(card);
            });
            metricSection.appendChild(grid);
            refs.calibrationBody.appendChild(metricSection);
        }

        const predictionSection = sectionBlock('Recent predictions');
        const predictionList = node('div', { className: 'calib-pred-list' });
        if (asArray(predictions).length) {
            asArray(predictions).forEach((prediction) => {
                if (isRecord(prediction)) predictionList.appendChild(calibrationPrediction(prediction));
            });
        } else {
            predictionList.appendChild(textLine('No evaluable prediction has been recorded yet.', 'calib-empty'));
        }
        predictionSection.appendChild(predictionList);
        refs.calibrationBody.appendChild(predictionSection);

        if (isRecord(usage)) {
            const usageSection = sectionBlock('Usage in the last 30 days');
            usageSection.appendChild(detailGrid([
                ['Request', formatNumber(clampNumber(usage.requests, 0, Number.MAX_SAFE_INTEGER, 0))],
                ['Input tokens', formatNumber(clampNumber(usage.input_tokens, 0, Number.MAX_SAFE_INTEGER, 0))],
                ['Output tokens', formatNumber(clampNumber(usage.output_tokens, 0, Number.MAX_SAFE_INTEGER, 0))],
                ['cache', formatNumber(clampNumber(usage.cached_requests, 0, Number.MAX_SAFE_INTEGER, 0))],
            ]));
            refs.calibrationBody.appendChild(usageSection);
        }
        refs.calibrationBody.appendChild(textLine(
            'Directional accuracy is only the mechanical result of matured predictions and does not guarantee financial performance.',
            'intel-disclaimer'
        ));
    }

    async function openTrackRecord(trigger) {
        openDialog(refs.calibrationDialog, trigger);
        setPanelLoading(refs.calibrationBody, 'Calculating track record and usage…');
        const results = await Promise.allSettled([
            apiRequest('/api/calibration', {
                timeout: API_TIMEOUT.read,
                key: 'calibration',
            }),
            apiRequest('/api/predictions', {
                timeout: API_TIMEOUT.read,
                key: 'predictions',
            }),
            apiRequest('/api/usage', {
                timeout: API_TIMEOUT.read,
                key: 'usage-track',
            }),
        ]);
        const stats = results[0].status === 'fulfilled' ? unwrapData(results[0].value) : null;
        const predictions = results[1].status === 'fulfilled'
            ? listFrom(results[1].value, ['predictions'])
            : [];
        const usage = results[2].status === 'fulfilled' ? unwrapData(results[2].value) : null;
        if (!isRecord(stats) && !predictions.length && !isRecord(usage)) {
            setPanelEmpty(refs.calibrationBody, 'The track record is currently unavailable.');
            return;
        }
        state.calibration = isRecord(stats) ? stats : null;
        state.calibrationPredictions = predictions;
        if (isRecord(usage)) state.currentUsage = usage;
        renderTrackRecord(stats, predictions, usage);
    }

    async function refreshContextPreviews() {
        await Promise.allSettled([
            loadGoals(false, true),
            loadProfile(true),
            loadUsage(true),
        ]);
    }

    async function loadHealthStatus() {
        if (!refs.systemState || !refs.systemStateLabel || !refs.systemStateDetail) return;
        refs.systemState.dataset.status = 'checking';
        setUiText(refs.systemStateLabel, 'Checking AI service');
        setUiText(refs.systemStateDetail, 'Verifying analysis and storage availability…');
        try {
            const payload = await apiRequest('/api/health', {
                timeout: API_TIMEOUT.read,
                key: 'health',
                silent: true,
            });
            const health = unwrapData(payload);
            if (!isRecord(health)) throw new ApiError('Invalid health response.', 502, 'invalid_health');
            if (health.ready === true && health.ai_ready === true) {
                refs.systemState.dataset.status = 'ready';
                setUiText(refs.systemStateLabel, 'AI service available');
                setUiText(
                    refs.systemStateDetail,
                    health.demo_mode === true
                        ? 'Demo mode is active.'
                        : 'Analysis runs only after you choose Generate analysis.'
                );
                return;
            }
            refs.systemState.dataset.status = 'degraded';
            if (health.ai_ready !== true) {
                setUiText(refs.systemStateLabel, 'AI service not configured');
                setUiText(refs.systemStateDetail, 'Configure the provider before generating an analysis.');
            } else if (health.storage_ready !== true) {
                setUiText(refs.systemStateLabel, 'Storage service unavailable');
                setUiText(refs.systemStateDetail, 'Analysis history and saved context may be unavailable.');
            } else {
                setUiText(refs.systemStateLabel, 'Service is degraded');
                setUiText(refs.systemStateDetail, 'Some analysis features may be temporarily unavailable.');
            }
        } catch {
            refs.systemState.dataset.status = 'unavailable';
            setUiText(refs.systemStateLabel, 'Service status unavailable');
            setUiText(refs.systemStateDetail, 'You can keep editing your decision and try again.');
        }
    }

    function isMobileSidebar() {
        return typeof window.matchMedia === 'function'
            && window.matchMedia('(max-width: 61.99rem)').matches;
    }

    function sidebarFocusableElements() {
        if (!refs.sidebar) return [];
        return Array.from(refs.sidebar.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )).filter((element) => !element.hidden && element.getClientRects().length > 0);
    }

    function setSidebarOpen(open, restoreFocus = true) {
        const mobile = isMobileSidebar();
        const wasExpanded = refs.mobileNavToggle?.getAttribute('aria-expanded') === 'true';
        const expanded = Boolean(open) && mobile;
        if (refs.sidebar) {
            refs.sidebar.classList.toggle('is-open', expanded);
            refs.sidebar.inert = mobile && !expanded;
            if (mobile) refs.sidebar.setAttribute('aria-hidden', expanded ? 'false' : 'true');
            else refs.sidebar.removeAttribute('aria-hidden');
        }
        if (refs.sidebarBackdrop) refs.sidebarBackdrop.hidden = !expanded;
        if (refs.mobileNavToggle) {
            refs.mobileNavToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            setUiAttribute(refs.mobileNavToggle, 'aria-label', expanded ? 'Close main menu' : 'Open main menu');
        }
        document.body.classList.toggle('sidebar-open', expanded);
        if (expanded) {
            window.requestAnimationFrame(() => sidebarFocusableElements()[0]?.focus({ preventScroll: true }));
        } else if (wasExpanded && restoreFocus && refs.mobileNavToggle?.isConnected) {
            refs.mobileNavToggle.focus({ preventScroll: true });
        }
    }

    function resetForNewAnalysis() {
        state.intake = null;
        state.questions = [];
        state.questionIndex = 0;
        state.answers = Object.create(null);
        state.knownFacts = Object.create(null);
        state.currentAnalysis = null;
        state.currentIntelligence = null;
        state.currentAnalysisId = null;
        state.messages = [];
        state.chatExecutionKits = [];
        state.selectedResultTab = 'overview';
        hideWizard();
        if (refs.resultsContainer) {
            clear(refs.resultsContainer);
            refs.resultsContainer.hidden = true;
            refs.resultsContainer.classList.add('hidden');
        }
        if (state.chatList) clear(state.chatList);
        if (refs.conversationThread) refs.conversationThread.hidden = true;
        if (refs.conversationEmptyState) refs.conversationEmptyState.hidden = false;
        if (refs.followUpForm) refs.followUpForm.hidden = true;
        renderFollowUpSuggestions([]);
        if (refs.newAnalysisButton) refs.newAnalysisButton.hidden = true;
        if (refs.queryInput) {
            refs.queryInput.value = '';
            refs.queryInput.disabled = false;
            refs.queryInput.focus();
        }
        removeStorage('omni-draft-v2');
        renderContextSummary();
        updateCharacterCount();
        setStatus('Describe your next decision.', false);
        safeScrollIntoView(refs.analysisForm, { block: 'center' });
    }

    function bindTierControls() {
        if (refs.tierB2C) {
            if (refs.tierB2C.matches('input[type="radio"]')) {
                refs.tierB2C.addEventListener('change', () => {
                    if (refs.tierB2C.checked) {
                        setTier('B2C');
                        void loadProfile(true);
                    }
                });
            } else {
                refs.tierB2C.addEventListener('click', () => {
                    setTier('B2C');
                    void loadProfile(true);
                });
            }
        }
        if (refs.tierB2B) {
            if (refs.tierB2B.matches('input[type="radio"]')) {
                refs.tierB2B.addEventListener('change', () => {
                    if (refs.tierB2B.checked) {
                        setTier('B2B');
                        void loadProfile(true);
                    }
                });
            } else {
                refs.tierB2B.addEventListener('click', () => {
                    setTier('B2B');
                    void loadProfile(true);
                });
            }
        }
    }

    function bindHorizonControl() {
        if (!refs.strategicToggle) return;
        if (refs.strategicToggle.matches('input[type="checkbox"]')) {
            refs.strategicToggle.addEventListener('change', () => {
                setHorizon(refs.strategicToggle.checked ? 'strategic' : 'instant');
            });
            return;
        }
        refs.strategicToggle.addEventListener('click', () => {
            setHorizon(state.horizon === 'strategic' ? 'instant' : 'strategic');
        });
        refs.strategicToggle.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                setHorizon(state.horizon === 'strategic' ? 'instant' : 'strategic');
            }
        });
    }

    function bindAnalysisForm() {
        if (refs.analysisForm) {
            refs.analysisForm.addEventListener('submit', (event) => {
                event.preventDefault();
                void beginIntake();
            });
        } else if (refs.analyzeButton) {
            refs.analyzeButton.addEventListener('click', () => void beginIntake());
        }
        if (refs.queryInput) {
            refs.queryInput.addEventListener('input', updateCharacterCount);
            refs.queryInput.addEventListener('keydown', (event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                    event.preventDefault();
                    void beginIntake();
                }
            });
        }
        document.querySelectorAll('[data-query-preset]').forEach((button) => {
            button.addEventListener('click', () => {
                if (!refs.queryInput) return;
                refs.queryInput.value = asText(button.dataset.queryPreset).slice(0, INPUT_LIMIT);
                updateCharacterCount();
                refs.queryInput.focus();
            });
        });
        if (refs.newAnalysisButton) refs.newAnalysisButton.addEventListener('click', resetForNewAnalysis);
        if (refs.navAnalysisButton) {
            refs.navAnalysisButton.addEventListener('click', () => {
                setSidebarOpen(false);
                safeScrollIntoView(refs.analysisForm, { block: 'center' });
                refs.queryInput?.focus({ preventScroll: true });
            });
        }
    }

    function bindWizard() {
        if (refs.wizardBack) {
            refs.wizardBack.addEventListener('click', () => {
                readCurrentAnswer(false);
                state.questionIndex = Math.max(0, state.questionIndex - 1);
                renderWizardStep();
            });
        }
        if (refs.wizardNext) {
            refs.wizardNext.addEventListener('click', () => {
                if (!readCurrentAnswer(true)) return;
                state.questionIndex = Math.min(state.questions.length - 1, state.questionIndex + 1);
                renderWizardStep();
            });
        }
        if (refs.wizardSkip) {
            refs.wizardSkip.addEventListener('click', skipCurrentQuestion);
        }
        if (refs.clarificationForm) {
            refs.clarificationForm.addEventListener('submit', (event) => {
                event.preventDefault();
                void submitAnalysis(false);
            });
        } else if (refs.wizardSubmit) {
            refs.wizardSubmit.addEventListener('click', () => void submitAnalysis(false));
        }
    }

    function bindConversation() {
        if (refs.followUpForm) {
            refs.followUpForm.addEventListener('submit', (event) => {
                event.preventDefault();
                void sendFollowUp();
            });
        }
        if (refs.followUpInput) {
            refs.followUpInput.addEventListener('input', updateFollowUpCount);
            refs.followUpInput.addEventListener('keydown', (event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                    event.preventDefault();
                    void sendFollowUp();
                }
            });
        }
        if (refs.followUpSuggestions) {
            refs.followUpSuggestions.addEventListener('click', (event) => {
                const button = event.target.closest('button[data-follow-up-prompt]');
                if (!button || !refs.followUpSuggestions.contains(button) || !refs.followUpInput) return;
                refs.followUpInput.value = asText(button.dataset.followUpPrompt).slice(0, FOLLOW_UP_LIMIT);
                refs.followUpInput.focus();
            });
        }
    }

    function bindDialog(dialog) {
        if (!dialog) return;
        dialog.addEventListener('click', (event) => {
            if (event.target === dialog) closeDialog(dialog);
        });
        dialog.addEventListener('cancel', () => {
            window.setTimeout(() => {
                const trigger = state.lastDialogTrigger.get(dialog);
                if (trigger && trigger.isConnected) trigger.focus({ preventScroll: true });
            }, 0);
        });
        dialog.addEventListener('close', () => {
            const trigger = state.lastDialogTrigger.get(dialog);
            if (trigger && trigger.isConnected) trigger.focus({ preventScroll: true });
        });
    }

    function bindDialogsAndPanels() {
        [refs.vaultDialog, refs.goalsDialog, refs.memoryDialog, refs.calibrationDialog].forEach(bindDialog);
        const closeButtons = new Set([
            refs.closeVaultButton,
            refs.closeGoalsButton,
            refs.closeMemoryButton,
            refs.closeCalibrationButton,
            ...document.querySelectorAll('[data-dialog-close]'),
        ]);
        closeButtons.forEach((button) => {
            if (!button) return;
            button.addEventListener('click', () => closeDialog(button.closest('dialog, [role="dialog"]')));
        });

        if (refs.openVaultButton) {
            refs.openVaultButton.addEventListener('click', () => {
                setSidebarOpen(false);
                void openVaultDialog(refs.openVaultButton);
            });
        }
        if (refs.openGoalsButton) {
            refs.openGoalsButton.addEventListener('click', () => {
                setSidebarOpen(false);
                void loadGoals(true, false, refs.openGoalsButton);
            });
        }
        if (refs.openMemoryButton) {
            refs.openMemoryButton.addEventListener('click', () => {
                setSidebarOpen(false);
                void openMemoryDialog(refs.openMemoryButton);
            });
        }
        if (refs.openCalibrationButton) {
            refs.openCalibrationButton.addEventListener('click', () => {
                setSidebarOpen(false);
                void openTrackRecord(refs.openCalibrationButton);
            });
        }

        if (refs.vaultSearchInput) refs.vaultSearchInput.addEventListener('input', applyVaultFilters);
        if (refs.vaultFilter) refs.vaultFilter.addEventListener('change', applyVaultFilters);

        if (refs.goalForm) {
            refs.goalForm.addEventListener('submit', (event) => {
                event.preventDefault();
                void createManualGoal();
            });
        }
        if (refs.goalCancelButton) {
            refs.goalCancelButton.addEventListener('click', () => {
                refs.goalForm?.reset();
                if (refs.goalEditor) refs.goalEditor.hidden = true;
            });
        }
        document.querySelectorAll('[data-goal-create]').forEach((button) => {
            button.addEventListener('click', () => {
                if (refs.goalEditor) refs.goalEditor.hidden = false;
                refs.goalTitleInput?.focus();
            });
        });
        document.querySelectorAll('[data-memory-filter]').forEach((button) => {
            button.addEventListener('click', () => {
                const requested = asText(button.dataset.memoryFilter);
                state.memoryFilter = ['all', 'profile', 'constraint', 'preference'].includes(requested)
                    ? requested
                    : 'all';
                document.querySelectorAll('[data-memory-filter]').forEach((candidate) => {
                    const active = candidate === button;
                    candidate.classList.toggle('is-active', active);
                    candidate.setAttribute('aria-pressed', active ? 'true' : 'false');
                });
                renderMemory(state.currentProfile || { tier: state.tier, memory: {} });
            });
        });

        const directlyBound = new Set([
            refs.openVaultButton,
            refs.openGoalsButton,
            refs.openMemoryButton,
            refs.openCalibrationButton,
        ]);
        document.querySelectorAll('[data-dialog-target]').forEach((button) => {
            if (directlyBound.has(button)) return;
            button.addEventListener('click', () => {
                const target = asText(button.dataset.dialogTarget);
                if (target === 'vault-container') void openVaultDialog(button);
                else if (target === 'goals-container') void loadGoals(true, false, button);
                else if (target === 'memory-container') void openMemoryDialog(button);
                else if (target === 'calibration-container') void openTrackRecord(button);
            });
        });
        if (refs.memoryClearButton) refs.memoryClearButton.addEventListener('click', () => void clearMemory());
        if (refs.memoryExportButton) refs.memoryExportButton.addEventListener('click', exportMemory);
    }

    function bindSidebar() {
        if (refs.mobileNavToggle) {
            refs.mobileNavToggle.addEventListener('click', () => {
                const open = refs.mobileNavToggle.getAttribute('aria-expanded') !== 'true';
                setSidebarOpen(open);
            });
        }
        if (refs.sidebarBackdrop) refs.sidebarBackdrop.addEventListener('click', () => setSidebarOpen(false));
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && refs.mobileNavToggle?.getAttribute('aria-expanded') === 'true') {
                setSidebarOpen(false);
                return;
            }
            if (event.key === 'Tab' && refs.mobileNavToggle?.getAttribute('aria-expanded') === 'true') {
                const focusable = sidebarFocusableElements();
                if (!focusable.length) {
                    event.preventDefault();
                    refs.mobileNavToggle?.focus();
                    return;
                }
                const first = focusable[0];
                const last = focusable[focusable.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            }
        });
        if (typeof window.matchMedia === 'function') {
            const sidebarMedia = window.matchMedia('(max-width: 61.99rem)');
            sidebarMedia.addEventListener?.('change', () => setSidebarOpen(false, false));
        }
    }

    function cacheReferences() {
        refs.themeColorMeta = byId('theme-color-meta');
        refs.appShell = byId('app-shell');
        refs.sidebar = byId('app-sidebar');
        refs.mobileNavToggle = byId('mobile-nav-toggle');
        refs.sidebarBackdrop = byId('sidebar-backdrop');
        refs.systemState = byId('system-state');
        refs.systemStateLabel = byId('system-state-label');
        refs.systemStateDetail = byId('system-state-detail');
        refs.mainContent = byId('main-content');
        refs.navAnalysisButton = byId('nav-analysis-btn');
        refs.heroToggle = byId('hero-toggle-btn');
        refs.contextRailToggle = byId('context-rail-toggle');
        refs.contextRailContent = byId('context-rail-content');

        refs.themeToggle = byId('theme-toggle-btn');
        refs.themeToggleLabel = byId('theme-toggle-label');
        refs.tierB2C = byId('btn-b2c');
        refs.tierB2B = byId('btn-b2b');
        refs.strategicToggle = byId('strategic-toggle');
        refs.analysisForm = byId('analysis-form');
        refs.queryInput = byId('omni-input');
        refs.analyzeButton = byId('analyze-btn');
        refs.analysisFormError = byId('analysis-form-error');
        refs.queryCharCount = byId('query-char-count');

        refs.clarificationWizard = byId('clarification-wizard');
        refs.wizardTitle = byId('wizard-title');
        refs.wizardProgressBar = byId('wizard-progress-bar');
        refs.wizardStepLabel = byId('wizard-step-label');
        refs.clarificationForm = byId('clarification-form');
        refs.clarificationQuestions = byId('clarification-questions');
        refs.clarificationSummary = byId('clarification-summary');
        refs.clarificationSummaryContent = refs.clarificationSummary
            ? refs.clarificationSummary.querySelector('[data-summary-content]')
            : null;
        refs.wizardPrecisionLabel = byId('wizard-precision-label');
        refs.wizardPrecisionValue = byId('wizard-precision-value');
        refs.wizardBack = byId('wizard-back-btn');
        refs.wizardSkip = byId('wizard-skip-btn');
        refs.wizardNext = byId('wizard-next-btn');
        refs.wizardSubmit = byId('wizard-submit-btn');

        refs.conversationRegion = byId('conversation-region');
        refs.conversationThread = byId('conversation-thread');
        refs.resultsContainer = byId('results-container');
        refs.conversationEmptyState = byId('conversation-empty-state');
        refs.analysisStatus = byId('analysis-status');
        refs.analysisStatusLabel = byId('analysis-status-label');
        refs.systemLogs = byId('system-logs');
        refs.newAnalysisButton = byId('new-analysis-btn');
        refs.followUpForm = byId('follow-up-form');
        refs.followUpSuggestions = refs.followUpForm
            ? refs.followUpForm.querySelector('.follow-up-suggestions')
            : null;
        refs.followUpInput = byId('follow-up-input');
        refs.followUpButton = byId('follow-up-btn');
        refs.followUpError = byId('follow-up-error');

        refs.contextSummaryList = byId('context-summary-list');
        refs.precisionMeter = byId('precision-meter');
        refs.precisionMeterFill = byId('precision-meter-fill');
        refs.precisionLabel = byId('precision-label');
        refs.activeGoalPreview = byId('active-goal-preview');
        refs.memoryPreview = byId('memory-preview');
        refs.usagePreview = byId('usage-preview');

        refs.openVaultButton = byId('open-vault-btn');
        refs.vaultDialog = byId('vault-container');
        refs.closeVaultButton = byId('close-vault-btn');
        refs.vaultList = byId('vault-list');
        refs.vaultSearchInput = byId('vault-search-input');
        refs.vaultFilter = byId('vault-filter');
        refs.vaultCountBadge = byId('vault-count-badge');

        refs.openGoalsButton = byId('open-goals-btn');
        refs.goalsDialog = byId('goals-container');
        refs.closeGoalsButton = byId('close-goals-btn');
        refs.goalsList = byId('goals-list');
        refs.activeGoalsCount = byId('active-goals-count');
        refs.completedGoalsCount = byId('completed-goals-count');
        refs.newGoalButton = byId('new-goal-btn');
        refs.goalEditor = byId('goal-editor');
        refs.goalForm = byId('goal-form');
        refs.goalTitleInput = byId('goal-title-input');
        refs.goalTargetInput = byId('goal-target-input');
        refs.goalDeadlineInput = byId('goal-deadline-input');
        refs.goalTimeInput = byId('goal-time-input');
        refs.goalBudgetInput = byId('goal-budget-input');
        refs.goalCancelButton = byId('goal-cancel-btn');
        refs.goalSaveButton = byId('goal-save-btn');

        refs.openMemoryButton = byId('open-memory-btn');
        refs.memoryDialog = byId('memory-container');
        refs.closeMemoryButton = byId('close-memory-btn');
        refs.memoryList = byId('memory-list');
        refs.memoryEmpty = byId('memory-empty');
        refs.memoryExportButton = byId('memory-export-btn');
        refs.memoryClearButton = byId('memory-clear-btn');

        refs.openCalibrationButton = byId('open-calibration-btn');
        refs.calibrationDialog = byId('calibration-container');
        refs.closeCalibrationButton = byId('close-calibration-btn');
        refs.calibrationBody = byId('calibration-body');

        refs.toastRegion = byId('toast-region');
        refs.assertiveLiveRegion = byId('assertive-live-region');
        refs.globalProgress = byId('global-progress');
        refs.globalProgressText = byId('global-progress-text');
    }

    function initialize() {
        cacheReferences();
        i18n.apply(document);
        initializeTheme();

        const checkedTier = document.querySelector('input[name="tier"]:checked');
        if (checkedTier && checkedTier.value === 'B2B') state.tier = 'B2B';
        if (refs.strategicToggle?.matches('input[type="checkbox"]') && refs.strategicToggle.checked) {
            state.horizon = 'strategic';
        }
        restoreDraft();
        setTier(state.tier, false);
        setHorizon(state.horizon, false);
        updateCharacterCount();
        renderContextSummary();
        updatePrecision();
        clearError(refs.analysisFormError);
        clearError(refs.followUpError);
        state.defaultFollowUps = refs.followUpSuggestions
            ? Array.from(refs.followUpSuggestions.querySelectorAll('[data-follow-up-prompt]'))
                .map((button) => asText(button.dataset.followUpPrompt).trim())
                .filter(Boolean)
            : [];
        renderFollowUpSuggestions([]);

        bindTierControls();
        bindHorizonControl();
        bindAnalysisForm();
        bindWizard();
        bindConversation();
        bindDialogsAndPanels();
        bindSidebar();
        bindProgressiveDisclosure();

        if (refs.conversationThread) refs.conversationThread.hidden = true;
        if (refs.followUpForm) refs.followUpForm.hidden = true;
        if (refs.newAnalysisButton) refs.newAnalysisButton.hidden = true;
        setSidebarOpen(false, false);
        void loadHealthStatus();
        void refreshContextPreviews();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true });
    } else {
        initialize();
    }

})();
