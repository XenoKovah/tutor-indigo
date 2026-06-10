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
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-post-npm-install-learning",
        """
RUN grep -q "defaultMessage: 'Discover'," node_modules/@edx/frontend-component-header/dist/learning-header/messages.js \\
 && sed -i "s/defaultMessage: 'Discover',/defaultMessage: 'Discover New Courses',/" node_modules/@edx/frontend-component-header/dist/learning-header/messages.js
RUN grep -qF "a {color: #ccc;}" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s/a {color: #ccc;}/a {color: #AEC7F6;}/" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
RUN grep -qF "color: #ccc;" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js \\
 && sed -i "s/color: #ccc;/color: #F8F8F8;/g" node_modules/@edx/frontend-component-header/dist/ThemeToggleButton.js
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

# OST2 dark-mode fix: the course-home "Updates" panel (the WelcomeMessage /
# whats-new box, e.g. "I updated both the ARM and x86 VMs...") renders LIGHT in
# dark mode. The visible white box is NOT the parent-document alert
# (WelcomeMessage's Paragon <Alert> carries `.alert-content`, which the brand
# CSS makes `background: none` in BOTH modes - confirmed transparent on the
# deployed page) but the LmsHtmlFragment IFRAME inside it: the iframe srcDoc
# loads the legacy lms-main.css and renders a white body (class="inline-link").
# Parent-document CSS (the brand dark partial) cannot reach inside that iframe,
# so the prescribed "append to the dark partial" approach is impossible here.
#
# The header's ThemeToggleButton DOES inject a dark <style> into every iframe -
# but ONLY on a toggle CLICK (addDarkThemeToIframes); when a course is OPENED
# with dark mode already on, that injection never runs and the Updates iframe
# stays white. We close that initial-load gap at the source: LmsHtmlFragment
# builds the iframe srcDoc, and at render time `document.body` already carries
# `indigo-dark-theme` (applied by the AddDarkTheme footer widget on load). Inject
# a dark <style> into the srcDoc head whenever the parent body is dark. The
# style's body bg/colour intentionally match the ThemeToggleButton's injected
# block (`background-color: #0D0D0E;` + `color: #F8F8F8;`) so the toggle's
# removeDarkThemeFromiframes() - which finds a style containing BOTH of those
# substrings - cleanly removes ours when the user later toggles to light,
# keeping runtime toggling consistent (verified live: the iframe goes dark on
# load and the remove-matcher catches the injected style). Runs at the
# pre-npm-build anchor (src/ present); grep-guarded on the unique
# LmsHtmlFragment.css <link> so the build fails loudly if upstream restructures
# the srcDoc. Single-quoted sed keeps the `${...}` JSX interpolation literal
# (no shell expansion); `'\\''` emits the shell escape `'\''`.
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-dockerfile-pre-npm-build-learning",
        """
RUN grep -qF '/static/LmsHtmlFragment.css">' src/course-home/outline-tab/LmsHtmlFragment.jsx \\
 && sed -i 's@/static/LmsHtmlFragment.css">@/static/LmsHtmlFragment.css">${document.body.classList.contains('\\''indigo-dark-theme'\\'') ? '\\''<style>body{background-color: #0D0D0E; color: #F8F8F8;} a{color: #AEC7F6;} a:hover{color: #d3d3d3;}</style>'\\'' : '\\'''\\''}@' src/course-home/outline-tab/LmsHtmlFragment.jsx
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
