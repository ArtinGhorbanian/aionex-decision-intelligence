(() => {
    'use strict';

    const APP_LOCALE = 'en';
    const translate = (value, params = {}) => Object.entries(params).reduce(
        (message, [name, replacement]) => message.replaceAll('{' + name + '}', String(replacement)),
        String(value ?? '')
    );

    window.OmniI18n = Object.freeze({
        apply(root = document) {
            const html = root.documentElement || document.documentElement;
            html.lang = APP_LOCALE;
            html.dir = 'ltr';
        },
        bindAttribute(element, attribute, value) {
            element.setAttribute(attribute, translate(value));
            return element;
        },
        bindText(element, value) {
            element.textContent = translate(value);
            return element;
        },
        date(value, options = {}) {
            const parsed = value instanceof Date ? value : new Date(value);
            if (Number.isNaN(parsed.getTime())) return value ? String(value) : '—';
            return new Intl.DateTimeFormat('en-US', options).format(parsed);
        },
        direction: () => 'ltr',
        getLocale: () => APP_LOCALE,
        list: (values) => new Intl.ListFormat('en-US', {
            style: 'long',
            type: 'conjunction',
        }).format(values),
        number(value, options = {}) {
            const numeric = Number(value);
            return Number.isFinite(numeric)
                ? new Intl.NumberFormat('en-US', options).format(numeric)
                : String(value);
        },
        percent(value, options = {}) {
            const numeric = Number(value);
            if (!Number.isFinite(numeric)) return '—';
            return new Intl.NumberFormat('en-US', {
                style: 'percent',
                maximumFractionDigits: 1,
                ...options,
            }).format(numeric / 100);
        },
        t: translate,
    });
})();
