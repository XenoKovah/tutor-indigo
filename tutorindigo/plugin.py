from __future__ import annotations

import os
import typing as t
from glob import glob

import importlib_resources
from tutor import hooks
from tutor.__about__ import __version_suffix__
from tutormfe.hooks import PLUGIN_SLOTS

from .__about__ import __version__

# Handle version suffix in main mode, just like tutor core
if __version_suffix__:
    __version__ += "-" + __version_suffix__


################# Configuration
config: t.Dict[str, t.Dict[str, t.Any]] = {
    # Add here your new settings
    "defaults": {
        "VERSION": __version__,
        "WELCOME_MESSAGE": "\"The more you learn, the more you earn.\" - Warren Buffet",
        "PRIMARY_COLOR": "#3b85ff",
        "ENABLE_DARK_TOGGLE": True,
        # Footer links are dictionaries with a "title" and "url"
        # To remove all links, run:
        # tutor config save --set INDIGO_FOOTER_NAV_LINKS=[]
        "FOOTER_NAV_LINKS": [
            {"title": "About", "url": "https://ost2.fyi/About.html"},
            # Per-box ToS: the MFE footer is served from apps.<LMS_HOST>, so a bare
            # relative "/tos" would resolve against the MFE host and 404. Build the
            # absolute LMS URL instead, so every box links to its own ToS page.
            {"title": "ToS", "url": "{{ 'https' if ENABLE_HTTPS else 'http' }}://{{ LMS_HOST }}/tos"},
            {"title": "Learning Paths", "url": "https://ost2.fyi/Learning-Paths.html"},
            {"title": "How to Help", "url": "https://ost2.fyi/How-to-Help.html"},
        ],
    },
    "unique": {},
    "overrides": {},
}

# Theme templates
hooks.Filters.ENV_TEMPLATE_ROOTS.add_item(
    str(importlib_resources.files("tutorindigo") / "templates")
)
# This is where the theme is rendered in the openedx build directory
hooks.Filters.ENV_TEMPLATE_TARGETS.add_items(
    [
        ("indigo_OST2_teak", "build/openedx/themes"),
        ("indigo_OST2_teak/env.config.jsx", "plugins/mfe/build/mfe"),
    ],
)

# Force the rendering of scss files, even though they are included in a "partials" directory
hooks.Filters.ENV_PATTERNS_INCLUDE.add_items(
    [
        r"indigo_OST2_teak/lms/static/sass/partials/lms/theme/",
        r"indigo_OST2_teak/cms/static/sass/partials/cms/theme/",
    ]
)

# OST2: redirect the platform "About" marketing link to the external ost2.fyi
# About page (matching the MFE footer "About" in FOOTER_NAV_LINKS above). The
# legacy LMS footer/nav About AND the certificate page's "Learn more about
# OpenSecurityTraining2" link both resolve via marketing_link('ABOUT')
# (certificate page: branding_api.get_about_url() -> get_url('ABOUT') ->
# marketing_link, returned verbatim with no re-absolutization). MKTG_URL_OVERRIDES
# is checked FIRST in marketing_link() (top priority, no ENABLE_MKTG_SITE needed),
# so this single override redirects EVERY marketing_link('ABOUT') -- there are no
# hardcoded /about links -- to https://ost2.fyi/About.html. LMS-only (the About
# link is never rendered in Studio). globals().get keeps any pre-existing overrides
# and is NameError-safe if MKTG_URL_OVERRIDES is somehow undefined upstream.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        'MKTG_URL_OVERRIDES = {**globals().get("MKTG_URL_OVERRIDES", {}), "ABOUT": "https://ost2.fyi/About.html"}',
    )
)


# init script: set theme automatically
with open(
    os.path.join(
        str(importlib_resources.files("tutorindigo") / "templates"),
        "indigo_OST2_teak",
        "tasks",
        "init.sh",
    ),
    encoding="utf-8",
) as task_file:
    hooks.Filters.CLI_DO_INIT_TASKS.add_item(("lms", task_file.read()))


# Override openedx & mfe docker image names
@hooks.Filters.CONFIG_DEFAULTS.add(priority=hooks.priorities.LOW)
def _override_openedx_docker_image(
    items: list[tuple[str, t.Any]],
) -> list[tuple[str, t.Any]]:
    openedx_image = ""
    mfe_image = ""
    for k, v in items:
        if k == "DOCKER_IMAGE_OPENEDX":
            openedx_image = v
        elif k == "MFE_DOCKER_IMAGE":
            mfe_image = v
    if openedx_image:
        items.append(("DOCKER_IMAGE_OPENEDX", f"{openedx_image}-indigo"))
    if mfe_image:
        items.append(("MFE_DOCKER_IMAGE", f"{mfe_image}-indigo"))
    return items


# Load all configuration entries
hooks.Filters.CONFIG_DEFAULTS.add_items(
    [(f"INDIGO_{key}", value) for key, value in config["defaults"].items()]
)
hooks.Filters.CONFIG_UNIQUE.add_items(
    [(f"INDIGO_{key}", value) for key, value in config["unique"].items()]
)
hooks.Filters.CONFIG_OVERRIDES.add_items(list(config["overrides"].items()))


#  MFEs that are styled using Indigo
indigo_styled_mfes = [
    "learning",
    "learner-dashboard",
    "profile",
    "account",
    "discussions",
]


for mfe in indigo_styled_mfes:
    hooks.Filters.ENV_PATCHES.add_items(
        [
            (
                f"mfe-dockerfile-post-npm-install-{mfe}",
                """
RUN npm install '@edx/frontend-component-header@npm:@edly-io/indigo-frontend-component-header@^4.0.0'
RUN npm install '@edx/brand@npm:@edly-io/indigo-brand-openedx@^2.2.2'

""",
            ),
        ]
    )


hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-authn",
        "RUN npm install '@edx/brand@npm:@edly-io/indigo-brand-openedx@^2.2.2'",
    )
)

# OST2 fix: on the authn Register/Sign-in pages the hero heading
# ("Start learning with OpenSecurityTraining2") clips its trailing "2". The
# heading is frontend-app-authn's image-layout hero - a Paragon `display-2`
# h1 (font-size 4.875rem) constrained to mw-sm (max-width 708px) in the w-50
# banner, with the site name in one long unbreakable word. The word is wider
# than the box and `#root .layout` is overflow:hidden, so the right edge
# (the "2") is cut off. Let the long word wrap instead of overflowing by
# adding overflow-wrap/word-break to the hero heading - both the LargeLayout
# h1 (.banner__image .display-2) and the Medium/ExtraSmall h1
# (.banner__heading). Appended to the brand's paragon/_overrides.scss, which
# authn @imports (src/index.scss) and which is light/theme-agnostic, so the
# fix applies regardless of theme and is scoped to the authn hero only.
# Guarded on a known selector so the build fails loudly if the partial moves.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-authn",
        """
RUN grep -qF '.container-xl {' node_modules/@edx/brand/paragon/_overrides.scss \\
 && printf '%s\\n' \\
 '.banner__image .display-2, .banner__heading { overflow-wrap: break-word; word-break: break-word; }' \\
 >> node_modules/@edx/brand/paragon/_overrides.scss
""",
    )
)

# OST2 fix (DEFAULT layout): the same hero-heading clipping happens on the
# no-banner-image default layout that dev.ost2.fyi actually renders, where the
# heading is `.bg-primary-400 h1` / `.text-accent-a` (not `.banner__heading`),
# so the block above never matches it. At >=1200px the page is side-by-side
# (`.w-50` hero | `.content` white form panel) and the long one-word site name
# slid UNDER the white panel; below 1200px `.layout` is flex-direction:column
# (stacked) and the h1 max-width:564px made the word overflow there too. Fix:
# (a) >=1200px shrink `.content` to hug the form (564px) and flex the hero to
# fill the rest; (b) make the hero a CSS container and fluid-size the heading
# to the hero's OWN width (cqi) with word-break:keep-all + max-width:100%, so
# the long name is always on ONE line - never split, never overflowing - in
# both side-by-side and stacked layouts (min() keeps the full 52/64px wide).
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-authn",
        """
RUN grep -qF '.container-xl {' node_modules/@edx/brand/paragon/_overrides.scss \\
 && printf '%s\\n' \\
 '@media (min-width:1200px){ #root .layout{display:flex!important;flex-wrap:nowrap!important}#root .layout>.w-50.d-flex{flex:1 1 auto!important;width:auto!important;max-width:none!important;min-width:0!important}#root .layout>.content{flex:0 0 564px!important;width:564px!important;max-width:564px!important;margin:0!important}}' \\
 '#root .layout .bg-primary-400{container-type:inline-size!important}' \\
 '#root .layout .bg-primary-400 h1{max-width:100%!important;width:100%!important;overflow-wrap:normal!important;word-break:keep-all!important;white-space:normal!important;font-size:min(52px,5.3cqi)!important;line-height:1.15!important}' \\
 '#root .layout .bg-primary-400 h1 .text-accent-a{overflow-wrap:normal!important;word-break:keep-all!important;font-size:min(64px,6.5cqi)!important;line-height:1.1!important}' \\
 >> node_modules/@edx/brand/paragon/_overrides.scss
""",
    )
)

# OST2: reword the authn hero lead-in "Start learning" -> "Level up your
# skills" (keeps "with {siteName}"). Source string in default-layout/
# messages.js, so it runs at the pre-npm-build anchor (src/ is COPY'd in just
# before this; post-npm-install is too early). Guarded so the build fails
# loudly if the string moves.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-authn",
        """
RUN grep -qF "defaultMessage: 'Start learning'" src/base-container/components/default-layout/messages.js \\
 && sed -i "s#defaultMessage: 'Start learning'#defaultMessage: 'Level up your skills'#" src/base-container/components/default-layout/messages.js
""",
    )
)

# OST2 dark-mode fix: the discussions posts-list filter bar ("All ... posts
# sorted by ...") renders with a WHITE background on the topic route
# (/discussions/<course>/topics/<id>) while it is correctly dark on /posts.
# The bar is PostFilterBar's Collapsible card (.filter-bar.collapsible-card-lg).
# The brand dark partial only darkens that card via
#   #root .header-action-bar + .d-flex.flex-row.position-relative ... .collapsible-card-lg
# which relies on the content pane being the ADJACENT sibling of the action
# bar. On the topic route a .breadcrumb-menu is inserted between them, so the
# `+` adjacency breaks, the dark rule misses, and the light Paragon default
# (.collapsible-card-lg{background:#fff}) wins. Append a dark-only,
# bar-only rule that darkens the same card under .discussion-posts to the dark
# surface ($primary-light = #292A2C, the colour the working /posts bar uses).
# The partial's other selectors are bare and get the `body.indigo-dark-theme`
# prefix from the importing stylesheet, so we append a bare selector too.
# Guard on a known selector in the brand partial so the build fails loudly if
# the file is renamed/restructured upstream.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-discussions",
        """
RUN grep -qF '.discussion-posts {' node_modules/@edx/brand/themes/dark/_extras.scss \\
 && printf '\\n.discussion-posts .filter-bar.collapsible-card-lg { background-color: $primary-light !important; }\\n' >> node_modules/@edx/brand/themes/dark/_extras.scss
""",
    )
)

# OST2 dark-mode fix (Topics view, remaining light element): on the discussions
# TOPIC route the breadcrumb bar (DiscussionsHome's <LegacyBreadcrumbMenu />,
# rendered BETWEEN the action bar and the posts pane) renders LIGHT in dark
# mode. Its markup is `<div class="breadcrumb-menu d-flex flex-row bg-light-200
# box-shadow-down-1 ...">`; the only thing painting its background is Paragon's
# `.bg-light-200 { background-color: #f8f7f6 !important; }` (light near-white).
# The brand dark theme darkens `.bg-light-200` only in specific contexts
# (.raised-card / .post-preview / .outline-sidebar-heading-wrapper) and never
# defines `.breadcrumb-menu` (deployed CSS: `.breadcrumb-menu { z-index: 1 }`
# only), so the breadcrumb bar keeps the light default. Append two bare,
# dark-only rules (the brand wraps `_extras.scss` in `body.indigo-dark-theme {}`
# via paragon/_dark.scss, so bare selectors inherit that prefix): darken the
# bar to $primary-light (#292A2C, the same dark surface the working /posts
# filter bar uses), and lighten the breadcrumb's `variant="outline"`
# DropdownButtons (.btn-outline-primary, default text #374151 dark-grey) to
# $text-color-primary (#DDDFE2) so they stay readable on the dark bar.
# `body.indigo-dark-theme .breadcrumb-menu` (0,2,1) + !important beats
# `.bg-light-200` (0,1,0) + !important. Appended to the same _extras.scss as the
# filter-bar fix and guarded on the `.discussion-posts {` opener so the build
# fails loudly if the brand restructures the dark partial. $primary-light /
# $text-color-primary are defined in themes/dark/_variables.scss, imported
# before extras in paragon/_dark.scss, so they are in scope.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-discussions",
        """
RUN grep -qF '.discussion-posts {' node_modules/@edx/brand/themes/dark/_extras.scss \\
 && printf '%s\\n' \\
 '.breadcrumb-menu { background-color: $primary-light !important; }' \\
 '.breadcrumb-menu .btn-outline-primary { color: $text-color-primary !important; }' \\
 >> node_modules/@edx/brand/themes/dark/_extras.scss
""",
    )
)

# OST2 dark-mode fix (2026-06-17): the standalone Discussions-MFE post-DETAIL
# pane card (.discussion-comments + its response/comment .card list) renders
# white in dark mode on the CATEGORY/topic route. The brand dark partial only
# darkens that card via the `#root .header-action-bar + .d-flex...` adjacency,
# and on a category route the breadcrumb is inserted between the action bar and
# the content pane, so the `+` no longer matches and the cards fall back to
# Paragon's light `.card{background:#fff}` (near-white-on-near-white, ~1:1). The
# plain post route keeps the adjacency intact so it stays dark -- which is why
# this only shows on the category/topic route, and on every box equally. Rather
# than chase the fragile adjacency, darken EVERY card under #main to the dark
# surface so the detail pane is covered on all routes (the post-LIST cards are
# `.discussion-post` anchors, not `.card`, so they're untouched). Guarded on
# `.discussion-posts {` like the rules above.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-discussions",
        """
RUN grep -qF '.discussion-posts {' node_modules/@edx/brand/themes/dark/_extras.scss \\
 && printf '\\n#main .card { background-color: $primary-light !important; }\\n' >> node_modules/@edx/brand/themes/dark/_extras.scss
""",
    )
)

# OST2: two build-time rewrites of the learning MFE, both grep-guarded so the
# image build fails loudly if upstream moves or rewords the targeted code.
#
# 1. Relabel the learning header's course-banner "Discover" link to "Discover
#    New Courses". The string is the Edly header package's compiled
#    defaultMessage (used for every locale - the package ships no
#    translations). The user-menu "Discover" item that shares this message is
#    hidden by frontend-rgg-widgets, so the banner link is the only remaining
#    use.
# 2. Remove the per-unit course-license footer. Sequence.jsx mounts
#    <CourseLicense /> under every unit and parseLicense() DEFAULTS to
#    "All Rights Reserved" when the course has no license set, so every unit
#    page shows a copyright notice that cannot be disabled by configuration.
# 3. Brighten the dark-theme iframe text. The header's ThemeToggleButton
#    injects a stylesheet into XBlock iframes setting body/link color #ccc
#    (grey); recolour the body text to the brand near-white (#F8F8F8) and the
#    links to the accent (#AEC7F6) so iframe-rendered units match native
#    content. The matching .includes('color: #ccc;') in the toggle's removal
#    path is rewritten too, so toggling dark off still strips the style.
#    The body{color} rule alone does NOT cover headings/titles: legacy XBlock
#    HTML (e.g. the FAQ block "How can I submit corrections to video
#    subtitles?") loads lms-main.css, whose `h1{color:#212529}` (and similar
#    bare, non-!important heading/body colours) override the iframe body colour
#    and render grey on the dark surface. Add (after the body recolour) a rule
#    forcing common text elements (h1-h6, p, li, span, div, table cells, dl,
#    label, blockquote, figcaption) to #F8F8F8 !important - an !important
#    declaration beats every (non-!important) lms-main.css colour regardless of
#    specificity - and upgrade the link rule to `a, a * {color: #AEC7F6
#    !important;}` so link text (and inline children) stay the accent and are
#    NOT swept up by the span/div force-light (`a *` (0,0,2) beats `span`/`div`
#    (0,0,1)). The same recolour+heading block is mirrored in the AddDarkTheme
#    on-load injector (mfe-env-config-buildtime-definitions) so load-in-dark and
#    toggle-to-dark paint identically. The added rules keep both
#    `background-color: #0D0D0E;` and `color: #F8F8F8;` substrings, so the
#    toggle's removeDarkThemeFromiframes() matcher still strips the style on
#    toggle-to-light. Guarded on the post-recolour `a {color: #AEC7F6;}` anchor.
# 4. Broadcast the theme to ALL iframes on toggle (Task A). The toggle's
#    onToggleTheme() posted the {indigo-toggle-dark} message only to the
#    #unit-iframe; the course-home LmsHtmlFragment iframes (no id) never heard
#    it, so their self-managing srcDoc <script> (see the LmsHtmlFragment patch)
#    could not react to a runtime toggle. Prepend an all-iframes broadcast that
#    posts the same payload to every iframe's contentWindow with targetOrigin
#    '*' (srcDoc iframes inherit the MFE origin, not the LMS origin the original
#    post used, so '*' is required to reach them; the payload is a non-sensitive
#    'dark'/'light' signal the receiver validates). The original #unit-iframe
#    post is left intact (harmless redundant delivery). Guarded on the exact
#    getElementById('unit-iframe') line; `&&` escaped `\\&` for sed; the result
#    is valid JS (node --check) against @edly-io/...-header@4.1.0.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -q "defaultMessage: 'Discover'," node_modules/@edx/frontend-component-header/dist/learning-header/messages.js \\
 && sed -i "s/defaultMessage: 'Discover',/defaultMessage: 'See All Courses',/" node_modules/@edx/frontend-component-header/dist/learning-header/messages.js
RUN grep -qF "a {color: #ccc;}" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s/a {color: #ccc;}/a {color: #AEC7F6;}/" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
RUN grep -qF "color: #ccc;" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s/color: #ccc;/color: #F8F8F8;/g" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
RUN grep -qF 'a {color: #AEC7F6;}' node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i 's|a {color: #AEC7F6;}|h1,h2,h3,h4,h5,h6,p,li,span,div,td,th,dt,dd,label,blockquote,figcaption {color: #F8F8F8 !important;} a, a * {color: #AEC7F6 !important;}|' node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
RUN grep -qF "var learningMFEUnitIframe = document.getElementById('unit-iframe');" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s|var learningMFEUnitIframe = document.getElementById('unit-iframe');|Array.from(document.getElementsByTagName('iframe')).forEach(function(f){if(f\\&\\&f.contentWindow){try{f.contentWindow.postMessage({'indigo-toggle-dark': theme}, '*');}catch(e){}}}); var learningMFEUnitIframe = document.getElementById('unit-iframe');|" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
""",
    )
)

# OST2 dark-mode IFRAME fixes (P2 - the header ThemeToggleButton). Three root
# causes, split into three separate ENV_PATCHES blocks below so each fix is
# self-contained. ALL of these blocks MUST run AFTER the block above (they depend
# on its output: the `color: #ccc;` -> `color: #F8F8F8;` rename and the
# heading-block CSS are already in place). Every sed is grep-guarded on the EXACT
# post-previous-block string so the build fails loudly if upstream (or the
# previous block) changes. The dark <style> injected here uses the SAME id
# (`ost2-iframe-dark`) and equivalent CSS as P1 (mfe-env-config-buildtime-
# definitions) and P3 (the LmsHtmlFragment srcDoc script), so every iframe has
# exactly ONE owner of its dark style across all three mechanisms.
#
# JINJA/SED NOTES (apply to all three blocks): the sed replacements contain no
# `|` (the sed delimiter) - e.g. the idempotency guard is split into two
# `if (!x) { return; }` statements rather than one `if (!a || !b)` to avoid a
# literal `|` closing the substitution - and no unescaped `&` (no `&`/`&&` in any
# replacement; the RC2 remove-guard's `&&` is in the MATCH side, written
# `\\&\\&` as elsewhere in this file). The RC3 forum-nav CSS is APPENDED after the
# unique, newline-free `a:hover{color: #d3d3d3;}` anchor rather than by rewriting
# the multi-line `style.textContent` (whose source has literal `\\n` sequences
# that sed's `\\n` would misread as newlines). No `{{`/`{%`/`{#` appears in any
# string. Verified: full sed chain applied to the real upstream file
# (post-previous-block) + `node --check` passes.

# ROOT CAUSE 1 - the toggle could not go light->dark on MFEs (dark->light and
# legacy pages worked). onToggleTheme() chose its direction from
# `cookies.get(themeCookie) === 'dark'`, which desyncs from what the user SEES
# when a stale/duplicate `indigo-toggle-dark` cookie reads 'dark' - so the
# toggle always took the "remove -> light" branch and never re-darkened. FIX:
# decide direction from the ACTUAL visible state
# (`document.body.classList.contains('indigo-dark-theme')`) so the toggle always
# flips relative to what is on screen, immune to cookie desync. It still writes
# the cookie to match the new state afterward (left intact). The checkbox
# `defaultChecked` is switched to the same visible-state read for consistency.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -qF "if (cookies.get(themeCookie) === 'dark') {" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s|if (cookies.get(themeCookie) === 'dark') {|if (document.body.classList.contains('indigo-dark-theme')) {|" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
RUN grep -qF "defaultChecked: cookies.get(themeCookie) === 'dark'," node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s|defaultChecked: cookies.get(themeCookie) === 'dark',|defaultChecked: document.body.classList.contains('indigo-dark-theme'),|" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
""",
    )
)

# ROOT CAUSE 2 - LmsHtmlFragment handout iframes stayed BLACK on dark->light.
# addDarkThemeToIframes() appended a NEW <style> every call, and the P1
# MutationObserver fires on every DOM mutation for 15s, so an iframe accumulated
# MANY duplicate dark <style> tags; removeDarkThemeFromiframes() used a single
# `.find()` and removed only ONE, leaving the rest. FIX: make the ADD idempotent
# (id-keyed `ost2-iframe-dark`, skip if one already exists in that iframe head ->
# at most one per iframe) and the REMOVE complete (select `style#ost2-iframe-dark`
# and remove ALL of them; the `.find()` callback removes each node and returns
# false so `.find()` walks the whole static snapshot). This also drops the
# brittle textContent-substring matcher.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -qF "        var style = document.createElement('style');" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s|        var style = document.createElement('style');|        var iframeDoc = iframes[ind].contentDocument; if (!iframeDoc) { return; } if (!iframeDoc.head) { return; } if (iframeDoc.getElementById('ost2-iframe-dark')) { return; } var style = iframeDoc.createElement('style'); style.id = 'ost2-iframe-dark';|" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
RUN grep -qF "querySelectorAll('style')" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s|querySelectorAll('style')|querySelectorAll('style#ost2-iframe-dark')|" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
RUN grep -qF "return style.textContent.includes('background-color: #0D0D0E;') && style.textContent.includes('color: #F8F8F8;');" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s|return style.textContent.includes('background-color: #0D0D0E;') \\&\\& style.textContent.includes('color: #F8F8F8;');|style.remove(); return false;|" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
""",
    )
)

# ROOT CAUSE 3 - inline-discussion (legacy XBlock) light bars stayed light in
# dark mode because the injected CSS only set body bg + text/link colours, not
# element-specific light backgrounds. The inline Discussion XBlock's grey filter
# bar is `.forum-nav-refine-bar` (background `theme-color("light")` in
# lms/static/sass/discussion/elements/_navigation.scss), as are
# `.forum-nav-load-more` and the select controls. FIX: extend the injected dark
# CSS (here AND in P1 AND P3) to darken the common forum-nav grey
# bars/containers to #0D0D0E and their control text to #F8F8F8. Kept tight: post
# threads (`.forum-nav-thread`, `$forum-color-background`) are intentionally NOT
# targeted so post cards/readability are preserved.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -qF 'a:hover{color: #d3d3d3;}' node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i 's|a:hover{color: #d3d3d3;}|a:hover{color: #d3d3d3;}.forum-nav-refine-bar,.forum-nav-sort-control,.forum-nav-thread-list,.forum-nav,.forum-nav-load-more {background-color: #0D0D0E !important;}.forum-nav-refine-bar,.forum-nav-refine-bar *,.forum-nav-sort-control,.forum-nav-sort-control select,.forum-nav-load-more a {color: #F8F8F8 !important;}|' node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
""",
    )
)

# ROOT CAUSE 4 - content <table> headers and the RGG done-block toggle kept their
# LIGHT backgrounds in the injected iframe dark style (audit 2026-06-12). The
# recolour block (ROOT CAUSE / line ~322) sets td,th + span TEXT to #F8F8F8 but
# never their background, so a markdown/HTML <th> (platform light-grey) and the
# .done_unmark / .done_mark pill (#EEE) render white-on-light-grey in the
# class-absent iframe state (the .indigo-dark-theme _xblock.scss rules only cover
# the class-PRESENT state). FIX: darken <th> and the done pills to #292A2C in the
# same injected style, appended after the unique RC3 forum-nav tail so it joins
# the single ost2-iframe-dark owner. Mirrored in P3 (LmsHtmlFragment) below.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -qF '.forum-nav-load-more a {color: #F8F8F8 !important;}' node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i 's|.forum-nav-load-more a {color: #F8F8F8 !important;}|.forum-nav-load-more a {color: #F8F8F8 !important;}table th,table thead th {background-color: #292A2C !important;}.done_unmark,.done_mark {background-color: #292A2C !important;}|' node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
""",
    )
)

# OST2 dark-mode fix: the learning MFE "Search this course" content-search
# modal renders LIGHT (white modal, white search box, black text) in dark
# mode. The brand dark theme DOES ship courseware-search rules, but they are
# keyed on `section.courseware-search` - and the Teak rewrite of
# frontend-app-learning renders the modal as <dialog class="courseware-search">
# (CoursewareSearch.jsx), so those `section.` rules never match and the
# light default (.courseware-search{background:#fff}) wins. Append dark-only
# rules keyed on the real `.courseware-search` element (which is unique to
# this modal) giving the dialog the dark page surface, the searchfield/input a
# dark surface with light text, and the summary/result titles light text.
# Appended to the brand dark partial the learning MFE compiles; it is
# @import-ed inside `body.indigo-dark-theme {}` and uses bare selectors, so the
# appended selectors are bare too and inherit the dark scope. Colours are the
# brand dark palette ($body-bg #0D0D0E, $primary-light #292A2C, $text-color
# #F8F8F8, $text-color-primary #DDDFE2); the border uses a plain hex (no brand
# var for it). Guarded on a known selector so the build fails loudly if the
# partial is renamed upstream.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -qF '.discussion-posts {' node_modules/@edx/brand/themes/dark/_extras.scss \\
 && printf '%s\\n' \\
 '.courseware-search { background: #0D0D0E !important; border-top-color: #777792 !important; color: #F8F8F8; }' \\
 '.courseware-search h1, .courseware-search .h2 { color: #F8F8F8 !important; }' \\
 '.courseware-search .pgn__searchfield, .courseware-search .pgn__searchfield-form, .courseware-search .pgn__searchfield_wrapper { background-color: #292A2C !important; }' \\
 '.courseware-search .form-control { background-color: #292A2C !important; color: #F8F8F8 !important; border-color: #777792 !important; }' \\
 '.courseware-search .courseware-search__results-summary { color: #DDDFE2 !important; }' \\
 '.courseware-search .courseware-search-results__title, .courseware-search .courseware-search-results__title > span { color: #F8F8F8 !important; }' \\
 '.courseware-search .courseware-search-results__item:not(:first-child) { border-top-color: #777792 !important; }' \\
 '.courseware-search .nav-link.active { color: #C9D6FF !important; }' \\
 '.courseware-search .pgn__searchfield__button.btn-primary { color: #F8F8F8 !important; }' \\
 >> node_modules/@edx/brand/themes/dark/_extras.scss
""",
    )
)

# OST2 dark-mode fix (audit 2026-06-13): the Progress page grade bar (an SVG with
# class "grade-bar") draws its "Your current grade" / "Passing grade" labels as
# <text> with fill #000 -> black-on-black, invisible on the dark page. Lighten the
# SVG text fill (the % marker bubbles are Paragon popovers, already light). Appended
# to the same brand dark partial; guarded on .discussion-posts.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -qF '.discussion-posts {' node_modules/@edx/brand/themes/dark/_extras.scss \\
 && printf '%s\\n' \\
 '.grade-bar text { fill: #F8F8F8 !important; }' \\
 >> node_modules/@edx/brand/themes/dark/_extras.scss
""",
    )
)

# OST2: hide the course-outline completion indicator circles. The outline
# section/sequence titles (SectionTitle.tsx / SequenceTitle.tsx) render a
# Paragon <Icon> completion marker - CheckCircleOutline (the grey "o",
# .text-gray-400) when incomplete, CheckCircle (the green check, .text-success)
# when complete - as the sole child of a `.col-auto.p-0` column next to the
# title. Completion is tracked differently here, so the user wants these
# outline indicators gone entirely (both states), in BOTH light and dark mode.
# Append a bare, NON-dark-scoped rule that hides ONLY those icons: scoped under
# `.course-outline-tab` and to the `.col-auto.p-0 > .pgn__icon` that holds the
# completion marker, so it cannot touch the Progress tab's own check icons
# (which use .text-success-300/500 and are not inside .course-outline-tab) nor
# the "hidden from TOC" DisabledVisible icon (which is not in a `.col-auto.p-0`).
# This is purely an outline indicator hide - it does NOT disable the Progress
# tab (no Pages&Resources / "Configure progress" change). Confirmed against the
# deployed learning DOM that this selector matches exactly the 8 outline circles,
# leaves titles intact (the emptied `.col-auto` collapses to 0px), and affects
# nothing outside the outline. Appended to the brand's paragon/_learning.scss,
# which is @import-ed BEFORE `@import "./dark"` so it is unscoped (both modes),
# and guarded on the `.course-outline-tab {` opener so the build fails loudly if
# the brand restructures the learning partial.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -qF '.course-outline-tab {' node_modules/@edx/brand/paragon/_learning.scss \\
 && printf '%s\\n' \\
 '.course-outline-tab .col-auto.p-0 > .pgn__icon.text-gray-400, .course-outline-tab .col-auto.p-0 > .pgn__icon.text-success { display: none !important; }' \\
 >> node_modules/@edx/brand/paragon/_learning.scss
""",
    )
)

# The license removal must run at the pre-npm-build anchor: post-npm-install
# executes in a layer that only has package.json/package-lock + node_modules
# (the app's src/ tree is COPY'd in afterwards, just before this anchor).
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN grep -qF "<CourseLicense license={license || undefined} />" src/courseware/course/sequence/Sequence.jsx \\
 && sed -i 's#<CourseLicense license={license || undefined} />##' src/courseware/course/sequence/Sequence.jsx
""",
    )
)

# OST2: suppress the phantom in-course notification-bell red dot. The learning
# MFE's sidebar Notifications trigger renders a red dot (NotificationIcon's
# <span class="bg-danger-500 rounded-circle ..."> shown when status==='active')
# whose `notificationStatus.<courseId>` localStorage value DEFAULTS to 'active'
# on first visit - the dot stays red "until seen" (the user opens the tray).
# OST2's Notification table is empty server-wide and this mechanism is unused,
# so the dot is purely phantom. Flip the first-visit default from 'active' to
# 'inactive' so NotificationIcon renders null (no dot). The default is set in
# the `if (!getLocalStorage(...)) { setLocalStorage(..., 'active'); }` init block
# of BOTH sidebar implementations bundled in Teak - the legacy
# sidebar/.../notifications/NotificationTrigger.jsx (the path that actually
# renders bg-danger-500 in the deployed bundle) and the new-sidebar
# .../discussions-notifications/DiscussionsNotificationsTrigger.tsx - so patch
# both for robustness regardless of which sidebar is active at runtime. The
# target line is uniquely identified by its trailing comment
# ("// Show red dot on notificationTrigger until seen"), which the UpgradeNotification
# re-show path's own `'active'` sets do NOT carry, so those are left intact
# (OST2 has no paid-upgrade track, so that path never fires anyway). Runs at the
# pre-npm-build anchor (src/ present); each sed is grep-guarded on the exact
# comment-bearing line so the build fails loudly if upstream rewords it.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN F=src/courseware/course/sidebar/sidebars/notifications/NotificationTrigger.jsx; \\
 grep -qF "'active'); // Show red dot on notificationTrigger until seen" "$F" \\
 && sed -i "s|'active'); // Show red dot on notificationTrigger until seen|'inactive'); // OST2: default inactive so no phantom red dot (no notifications mechanism)|" "$F"
RUN F=src/courseware/course/new-sidebar/sidebars/discussions-notifications/DiscussionsNotificationsTrigger.tsx; \\
 grep -qF "'active'); // Show red dot on notificationTrigger until seen" "$F" \\
 && sed -i "s|'active'); // Show red dot on notificationTrigger until seen|'inactive'); // OST2: default inactive so no phantom red dot (no notifications mechanism)|" "$F"
""",
    )
)

# OST2: drop the "Dates" tab from the learning header's course tab bar
# (Course / Progress / Dates / Discussion). The tab list is normalized in
# course-home/data/api.js, which maps the LMS tab metadata into the array
# CourseTabsNavigation.jsx renders. We inject a `.filter(...)` ahead of that
# `.map(...)` to discard the dates tab by its API id (`tab.tabId === 'dates'`,
# the camelCased `tab_id`). Runs at the pre-npm-build anchor so the app's src/
# tree is present; grep-guarded on the exact map opener so the build fails
# loudly if upstream reshapes the normalizer.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN grep -qF "tabs: data.tabs.map(tab => ({" src/course-home/data/api.js \\
 && sed -i "s|tabs: data.tabs.map(tab => ({|tabs: data.tabs.filter(tab => tab.tabId !== 'dates').map(tab => ({|" src/course-home/data/api.js
""",
    )
)

# OST2: remove the "Begin your course today / Start course" (and the matching
# "Resume course") outline card. The course-home OutlineTab mounts
# <StartOrResumeCourseCard /> at the top of the outline; the component renders a
# single Card whose title is messages.startBlurb ("Begin your course today") or
# messages.resumeBlurb and whose button is messages.start ("Start course") /
# messages.resume. It is the ONLY mount of that component (grep-confirmed in
# release/teak) and "Begin your course today" comes from nowhere else, so seding
# out the JSX mount removes the card everywhere it appears (course outline /
# home). Mirrors the CourseLicense removal: the now-unused
# `import StartOrResumeCourseCard` is left in place because the build is
# `fedx-scripts webpack` (no eslint gate), exactly as CourseLicense leaves its
# import. Runs at the pre-npm-build anchor so the app's src/ tree is present;
# grep-guarded on the exact mount token so the build fails loudly if upstream
# renames or restructures it.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN grep -qF "<StartOrResumeCourseCard />" src/course-home/outline-tab/OutlineTab.jsx \\
 && sed -i 's#<StartOrResumeCourseCard />##' src/course-home/outline-tab/OutlineTab.jsx
""",
    )
)

# OST2: remove the "Related links" sidebar box from the course Progress page.
# ProgressTab.jsx mounts <ProgressTabRelatedLinksSlot /> in the right-hand side
# panel; that slot's sole content is <RelatedLinks />, which renders the
# "Related links" card (an <h3>Related links</h3> over a "Course outline /
# A birds-eye view of your course content." link, plus an optional Dates link).
# It is the ONLY mount of that slot in release/teak (grep-confirmed: one import,
# one use at ProgressTab.jsx:42), so seding out the JSX mount removes the box
# entirely. Mirrors the CourseLicense / StartOrResumeCourseCard removals: the
# now-unused `import ProgressTabRelatedLinksSlot` is left in place because the
# build is `fedx-scripts webpack` (no eslint gate). Runs at the pre-npm-build
# anchor so the app's src/ tree is present; grep-guarded on the exact mount
# token so the build fails loudly if upstream renames/restructures the slot.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN grep -qF "<ProgressTabRelatedLinksSlot />" src/course-home/progress-tab/ProgressTab.jsx \\
 && sed -i 's#<ProgressTabRelatedLinksSlot />##' src/course-home/progress-tab/ProgressTab.jsx
""",
    )
)

# OST2: change the Progress page detailed-grades section toggles from a
# down/up caret to a disclosure triangle: RIGHT (toward the title) when
# collapsed, DOWN when expanded. SubsectionTitleCell.jsx renders the toggle as
# two mutually-exclusive Paragon <Collapsible.Visible> children inside the
# .collapsible-trigger - `whenClosed` shows <Icon src={ArrowDropDown} /> (the
# down triangle) and `whenOpen` shows <Icon src={ArrowDropUp} /> (the up
# triangle). Paragon's Collapsible.Visible MOUNTS/UNMOUNTS its child on
# open/close (it returns the child or null, with no persistent open/closed
# wrapper class - confirmed in the deployed bundle), so a CSS `transform:
# rotate(...)` keyed on a state class cannot work; the robust fix is to swap the
# icons in source. Repoint `whenClosed` to ArrowRight (Paragon's filled
# right-pointing triangle, path `M10 17l5-5l-5-5v10z`, already bundled in the
# deployed app) and `whenOpen` to ArrowDropDown (down), and add ArrowRight to
# the icon import. ArrowDropDown/ArrowDropUp are used ONLY here in the progress
# tab (grep-confirmed), so the swap is fully scoped. Runs at the pre-npm-build
# anchor (src/ present); each sed is grep-guarded on its exact target line so
# the build fails loudly if upstream rewords the toggle or the import.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN F=src/course-home/progress-tab/grades/detailed-grades/SubsectionTitleCell.jsx; \\
 grep -qF '<Collapsible.Visible whenClosed><Icon src={ArrowDropDown} /></Collapsible.Visible>' "$F" \\
 && grep -qF '<Collapsible.Visible whenOpen><Icon src={ArrowDropUp} /></Collapsible.Visible>' "$F" \\
 && grep -qF '  ArrowDropDown,' "$F" \\
 && sed -i 's#<Collapsible.Visible whenOpen><Icon src={ArrowDropUp} /></Collapsible.Visible>#<Collapsible.Visible whenOpen><Icon src={ArrowDropDown} /></Collapsible.Visible>#' "$F" \\
 && sed -i 's#<Collapsible.Visible whenClosed><Icon src={ArrowDropDown} /></Collapsible.Visible>#<Collapsible.Visible whenClosed><Icon src={ArrowRight} /></Collapsible.Visible>#' "$F" \\
 && sed -i 's#  ArrowDropDown,#  ArrowDropDown,\\n  ArrowRight,#' "$F"
""",
    )
)

# OST2 dark-mode fix: the course-home "Updates"/"Handouts" panels render inside
# LmsHtmlFragment IFRAMEs (srcDoc loading the legacy lms-main.css with a white
# body), which parent-document CSS cannot reach. The earlier approach (fcf4249)
# BAKED a conditional dark <style> into the srcDoc at React render time keyed on
# the parent body class. That made dark<->light TOGGLING get stuck/biased: there
# were then TWO independent dark-style mechanisms on the SAME iframes - the baked
# srcDoc <style> AND the header ThemeToggleButton's addDarkThemeToIframes() live
# <style> - and the toggle's removeDarkThemeFromiframes() (a single .find() that
# removes ONE matching <style> per iframe) could not reliably clear both, so
# toggle->light left a dark style behind (iframes stuck dark) and the
# cookie/checkbox/body state desynced (biased to dark on refresh).
#
# Replace the un-removable srcDoc bake with a SELF-MANAGING approach that makes
# each LmsHtmlFragment iframe the SOLE owner of its dark style and participates
# in BOTH the load path and the toggle cycle:
#  (1) Inject a tiny <script> into the srcDoc <head> (right after the
#      LmsHtmlFragment.css <link>). On its own load it reads the parent
#      `indigo-toggle-dark` cookie and, if dark, adds an id-keyed
#      `<style id="ost2-iframe-dark">` (idempotent - never duplicates); it also
#      listens for window 'message' {indigo-toggle-dark: 'dark'|'light'} and
#      adds/removes that same id-keyed style at runtime. This fixes load-in-dark
#      reliably (no dependence on the racy parent MutationObserver) AND responds
#      to toggles. CRUCIALLY the style uses `background:#0D0D0E;color:#F8F8F8;`
#      (NO spaces after the colons), so it does NOT contain the parent
#      remove-matcher substrings `background-color: #0D0D0E;` / `color: #F8F8F8;`
#      - the parent never touches it, so there is exactly one owner and no
#      duplicate-find ambiguity. The style also carries the Task-F heading/text
#      force-light + accent-link rules so iframe titles aren't grey.
#  (2) Make the ThemeToggleButton BROADCAST the theme to ALL iframes (see the
#      learning post-npm-install patch) instead of only #unit-iframe, with
#      targetOrigin '*' (srcDoc iframes inherit the MFE origin, not the LMS
#      origin the old code used, so an LMS-origin-targeted post would never
#      reach them). The script validates the payload is 'dark'/'light' before
#      acting, so '*' is safe for this non-sensitive theme signal.
# GUARANTEES: load-in-dark -> iframes dark; toggle->light -> ALL iframes light;
# toggle->dark -> ALL iframes dark; repeatable (id-keyed apply/remove is
# idempotent); refresh respects the cookie (nothing writes dark spuriously).
# The injected <script> is one line, uses only double-quoted JS strings (no
# single quotes -> the single-quoted sed needs no '\\'' escapes), has no
# backticks or `${...}` (safe inside the JSX template literal) and no `{#`/`{{`/
# `{%` (safe through Jinja). Runs at the pre-npm-build anchor (src/ present);
# grep-guarded on the unique LmsHtmlFragment.css <link>. The `&&` in the script
# is escaped `\\&` so sed does not expand `&` to the whole match. Verified: the
# resulting JSX parses (babel) and the script body is valid JS (node --check).
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN grep -qF '/static/LmsHtmlFragment.css">' src/course-home/outline-tab/LmsHtmlFragment.jsx \\
 && sed -i 's|/static/LmsHtmlFragment.css">|/static/LmsHtmlFragment.css"><script>(function(){var I="ost2-iframe-dark";var C="body{background:#0D0D0E;color:#F8F8F8;}h1,h2,h3,h4,h5,h6,p,li,span,div,td,th,dt,dd,label,blockquote,figcaption{color:#F8F8F8 !important;}a,a *{color:#AEC7F6 !important;}a:hover{color:#d3d3d3 !important;}.forum-nav-refine-bar,.forum-nav-sort-control,.forum-nav-thread-list,.forum-nav,.forum-nav-load-more{background-color:#0D0D0E !important;}.forum-nav-refine-bar,.forum-nav-refine-bar *,.forum-nav-sort-control,.forum-nav-sort-control select,.forum-nav-load-more a{color:#F8F8F8 !important;}table th,table thead th{background-color:#292A2C !important;}.done_unmark,.done_mark{background-color:#292A2C !important;}";function ap(on){var e=document.getElementById(I);if(on){if(!e){e=document.createElement("style");e.id=I;e.textContent=C;document.head.appendChild(e);}}else if(e){e.remove();}}ap(document.cookie.indexOf("indigo-toggle-dark=dark")!==-1);window.addEventListener("message",function(ev){var d=ev.data\\&\\&ev.data["indigo-toggle-dark"];if(d==="dark"){ap(true);}else if(d==="light"){ap(false);}});})();</script>|' src/course-home/outline-tab/LmsHtmlFragment.jsx
""",
    )
)

# OST2: on the learner-dashboard (Learner Home) remove the right-hand sidebar -
# the "Looking for a new challenge? / Find a course" promo
# (#looking-for-challenge-widget) lives in .sidebar-column > .widget-sidebar -
# and let the course list span the full row. The brand's paragon/_footer.scss
# (which the learner-dashboard compiles) sets `.course-list-column` to 70% and
# `.sidebar-column` to 30% at the lg breakpoint, so hiding the sidebar would
# otherwise leave the courses at 70%. Append a bare, NON-dark-scoped rule
# (applies in both light and dark) that hides the whole sidebar column and
# stretches the course list to 100%. The brand 70%/30% rules are qualified by
# `#dashboard-container` (an id), so bare appended selectors must use
# `!important` to win; verified against the deployed dashboard CSS/DOM that a
# bare `!important` rule overrides the brand widths and hides the sidebar.
# Appended to _footer.scss itself (where these exact selectors are defined) and
# guarded on the `.sidebar-column {` opener so the build fails loudly if the
# brand restructures the dashboard partial.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learner-dashboard",
        """
RUN grep -qF '.sidebar-column {' node_modules/@edx/brand/paragon/_footer.scss \\
 && printf '%s\\n' \\
 '.sidebar-column { display: none !important; }' \\
 '.course-list-column { flex: 0 0 100% !important; max-width: 100% !important; }' \\
 >> node_modules/@edx/brand/paragon/_footer.scss
""",
    )
)

# OST2: on the learner-dashboard remove the "Refine" filter control (the
# right-aligned outline button + its dropdown card). Course completion is
# tracked differently here, so the filter misbehaves; the user wants it gone.
# The control is .course-filter-controls-container (with #course-filter-controls-card
# inside) in the brand's paragon/_footer.scss. Append a bare, NON-dark-scoped
# rule (both modes) hiding the container. It is a block in the right column
# above the course list and carries no layout the list depends on (the list is
# already forced to 100% width by the sidebar-removal patch above), so hiding
# it leaves the course list intact - confirmed against the deployed DOM that
# hiding the container does not shift the course cards. Appended to _footer.scss
# and guarded on the `.course-filter-controls-container {` opener.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learner-dashboard",
        """
RUN grep -qF '.course-filter-controls-container {' node_modules/@edx/brand/paragon/_footer.scss \\
 && printf '%s\\n' \\
 '.course-filter-controls-container { display: none !important; }' \\
 >> node_modules/@edx/brand/paragon/_footer.scss
""",
    )
)

# Include js file in lms main.html, main_django.html, and certificate.html

hooks.Filters.ENV_PATCHES.add_items(
    [
        # for production
        (
            "openedx-common-assets-settings",
            """
javascript_files = ['base_application', 'application', 'certificates_wv']
dark_theme_filepath = ['indigo_OST2_teak/js/dark-theme.js']

for filename in javascript_files:
    if filename in PIPELINE['JAVASCRIPT']:
        PIPELINE['JAVASCRIPT'][filename]['source_filenames'] += dark_theme_filepath
""",
        ),
        # for development
        (
            "openedx-lms-development-settings",
            """
javascript_files = ['base_application', 'application', 'certificates_wv']
dark_theme_filepath = ['indigo_OST2_teak/js/dark-theme.js']

for filename in javascript_files:
    if filename in PIPELINE['JAVASCRIPT']:
        PIPELINE['JAVASCRIPT'][filename]['source_filenames'] += dark_theme_filepath

MFE_CONFIG['INDIGO_ENABLE_DARK_TOGGLE'] = {{ INDIGO_ENABLE_DARK_TOGGLE }}
MFE_CONFIG['INDIGO_FOOTER_NAV_LINKS'] = {{ INDIGO_FOOTER_NAV_LINKS }}
""",
        ),
        (
            "openedx-lms-production-settings",
            """
MFE_CONFIG['INDIGO_ENABLE_DARK_TOGGLE'] = {{ INDIGO_ENABLE_DARK_TOGGLE }}
MFE_CONFIG['INDIGO_FOOTER_NAV_LINKS'] = {{ INDIGO_FOOTER_NAV_LINKS }}
""",
        ),
    ]
)


# Apply patches from tutor-indigo
for path in glob(
    os.path.join(
        str(importlib_resources.files("tutorindigo") / "patches"),
        "*",
    )
):
    with open(path, encoding="utf-8") as patch_file:
        hooks.Filters.ENV_PATCHES.add_item((os.path.basename(path), patch_file.read()))


_footer_slot_ops = """
            {
                op: PLUGIN_OPERATIONS.Hide,
                widgetId: 'default_contents',
            },
            {
                op: PLUGIN_OPERATIONS.Insert,
                widget: {
                    id: 'default_contents',
                    type: DIRECT_PLUGIN,
                    priority: 1,
                    RenderWidget: <OST2Footer />,
                },
            },
            {
                op: PLUGIN_OPERATIONS.Insert,
                widget: {
                    id: 'read_theme_cookie',
                    type: DIRECT_PLUGIN,
                    priority: 2,
                    RenderWidget: AddDarkTheme,
                },
            },
  """

# Register the footer ops under both the legacy `footer_slot` alias and the
# namespaced id `org.openedx.frontend.layout.footer.v1`. Newer MFEs (e.g.
# learner-dashboard) render the new id and ignore the legacy alias, so the
# AddDarkTheme widget - which applies the `indigo-dark-theme` body class -
# only ran on the older MFEs and dark mode silently rendered light there.
footer_slots = [
    "footer_slot",
    "org.openedx.frontend.layout.footer.v1",
]

for mfe in indigo_styled_mfes:
    for footer_slot in footer_slots:
        PLUGIN_SLOTS.add_item(
            (
                mfe,
                footer_slot,
                _footer_slot_ops,
            ),
        )

# OST2: hide the in-course notifications bell. The legacy (live) NotificationTrigger.jsx
# now hides it ENTIRELY (returns null unconditionally) - OST2 has no notifications
# mechanism in use. The new-sidebar combined trigger below stays logged-out-only (it
# also fronts discussions, which must remain). Original logged-out rationale: The
# sidebar trigger renders for everyone, but its tray can never be valid
# without a session - clicking it as an anonymous user (public courses)
# throws inside the tray and the MFE error boundary replaces the page with
# "An unexpected error occurred. Please click the button below to refresh
# the page." Render nothing when frontend-platform has no authenticated
# user. Mirrors the red-dot patch above: BOTH sidebar implementations
# bundled in Teak are patched - the legacy
# sidebar/.../notifications/NotificationTrigger.jsx (the path live in the
# deployed bundle) and the new-sidebar
# .../discussions-notifications/DiscussionsNotificationsTrigger.tsx (its
# combined trigger also only opens auth-dependent trays). The legacy early
# return is injected just before the component's single top-level
# `  return (` so it runs after all hooks (auth state is fixed for the
# lifetime of the page, so hook order stays stable); the count check pins
# that line to exactly one occurrence. The new-sidebar edit extends the
# existing availability guard. Runs at the pre-npm-build anchor (src/
# present); every sed is grep-guarded so the build fails loudly if upstream
# reshapes the code.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN F=src/courseware/course/sidebar/sidebars/notifications/NotificationTrigger.jsx; \\
 grep -qF "import { useIntl } from '@edx/frontend-platform/i18n';" "$F" \\
 && [ "$(grep -c '^  return ($' "$F")" = 1 ] \\
 && sed -i "s#^  return (\\$#  return null; // OST2: in-course notification bell hidden entirely (notifications mechanism unused; tray is invalid logged-out and empty logged-in)\\n  return (#" "$F"
RUN F=src/courseware/course/new-sidebar/sidebars/discussions-notifications/DiscussionsNotificationsTrigger.tsx; \\
 grep -qF "import { useIntl } from '@edx/frontend-platform/i18n';" "$F" \\
 && grep -qF "if (!isDiscussionbarAvailable && !isNotificationbarAvailable) { return null; }" "$F" \\
 && sed -i "s#^import { useIntl } from '@edx/frontend-platform/i18n';\\$#&\\nimport { getAuthenticatedUser } from '@edx/frontend-platform/auth';#" "$F" \\
 && sed -i "s#if (!isDiscussionbarAvailable && !isNotificationbarAvailable) { return null; }#if ((!isDiscussionbarAvailable \\&\\& !isNotificationbarAvailable) || !getAuthenticatedUser()) { return null; } // OST2: hide for logged-out visitors#" "$F"
""",
    )
)
