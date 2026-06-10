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
 && sed -i "s#tabs: data.tabs.map(tab => ({#tabs: data.tabs.filter(tab => tab.tabId !== 'dates').map(tab => ({#" src/course-home/data/api.js
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
