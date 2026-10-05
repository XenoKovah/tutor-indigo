// OST2: dark theme for the Studio unit preview embedded in the Authoring MFE.
// The Authoring MFE header has the Indigo light/dark toggle, but the unit preview
// is a cross-origin Studio iframe (studio.<host>/container_embed/...), so the MFE
// cannot style it. This script (appended to Studio's base_vendor bundle) gives the
// iframe the same `indigo-dark-theme` body class the LMS unit iframe gets: from the
// shared `indigo-toggle-dark` cookie on load, and from the toggle's postMessage at
// runtime. The rules live in partials/cms/theme/_preview-dark.scss. Legacy Studio
// pages, and Studio pages not embedded in the MFE, are left alone.
(function() {
    'use strict';
    {% if INDIGO_ENABLE_DARK_TOGGLE %}
    if (window === window.parent || window.location.pathname.indexOf('/container_embed/') !== 0) {
        return;
    }

    function cookieTheme() {
        var match = document.cookie.match(/(?:^|;\s*)indigo-toggle-dark=([^;]*)/);
        return match && match[1] === 'dark' ? 'dark' : 'light';
    }

    function applyTheme(theme) {
        document.body.classList.toggle('indigo-dark-theme', theme === 'dark');
    }

    function init() {
        applyTheme(cookieTheme());
        window.addEventListener('message', function(event) {
            var theme = event.data && event.data['indigo-toggle-dark'];
            if (theme === 'dark' || theme === 'light') {
                applyTheme(theme);
            }
        });
    }

    if (document.body) {
        init();
    } else {
        document.addEventListener('DOMContentLoaded', init);
    }
    {% endif %}
}());
