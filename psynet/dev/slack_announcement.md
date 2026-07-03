# Slack Announcement Guidance

This file is runtime configuration for `psynet dev release announce`
(implemented in the sibling `slack_announcement.py`). It controls how
`CHANGELOG.md` entries are condensed into a short Slack announcement.

## Stable Release Description

This is a stable minor release with new experiment-building features, demo
updates, export improvements, and deployment/dependency cleanups.

## Experimenter Summary Intro

Here are the key changes relevant for experimenters:

## Stable Upgrade Instructions

Upgrade options:

- Standard PyPI: `pip install --upgrade psynet`
- PyPI with demo dependencies: `pip install --upgrade "psynet[demos]"`
- Editable installation: `git fetch --tags && git checkout v{version} && pip install -e .`
- Editable installation with demos: `git fetch --tags && git checkout v{version} && pip install -e ".[demos]"`

## Category Order

- Breaking
- Added
- Changed
- Deprecated
- Removed
- Fixed

## Include Patterns

Include changelog entries matching these regular expressions. These should
describe changes that are likely to matter to experimenters running or
developing PsyNet experiments.

- `\bdemo\b`
- `\bdemos\b`
- `element`
- `modular pages`
- `timeline elements`
- `trial maker`
- `ChainTrialMaker`
- `GraphChainTrialMaker`
- `network_structure`
- `make_next_definition`
- `Assets?`
- `basic data`
- `exports?`
- `\bCSV\b`
- `config\.txt`
- `experiment\.config`
- `dependencies`
- `\bPyPI\b`
- `private GitLab`
- `repp`
- `sing4me`
- `participant`
- `recruitment`
- `recruiters?`
- `Prolific`
- `Lucid`
- `\btrials?\b`
- `translations?`
- `translators?`
- `\blocales?\b`
- `psynet (deploy|debug|export|test)`
- `\bchains?\b`
- `sync group`
- `sync barrier`
- `websocket`

## Exclude Patterns

Exclude changelog entries matching these regular expressions. These are
generally internal implementation, CI, testing, documentation, or maintenance
items that should remain in the full release notes but not the Slack summary.

- `AGENTS\.md`
- `psynet dev\b`
- `demo regeneration`
- `demo test`
- `\bdemo\b.*\btest\b`
- `release skill`
- `Cursor skill`
- `CI[ _]job`
- `CI[ _]test`
- `CI[ _]config`
- `pre-commit`
- `Playwright`
- `Sphinx`
- `GitLab CI`
- `Ruff`
- `PgBadger`
- `pytest`
- `bot WebDriver`
- `moto`
- `S3 emulator`
- `performance.test`
- `Cursor workflow`
- `branch-review`
- `CHANGELOG`
- `perf_test`
- `PerformanceTester`
- `demo coverage`
- `failure diagnostics`
- `bump-my-version`
- `\.bumpversion`
- `formatting from black`
- `cached_property`
- `docstring`
- `type hint`
- `@classmethod`
- `unreachable code`
- `variable shadowing`
- `f-string prefix`
- `super\(\)`
- `quote escaping`
- `Unicode typo`
- `Removed unused(?! participant)`
- `Removed redundant`
- `Removed unreachable`
- `regression test`
- `test code`
- `test failure`
- `\x60test_`
- `version-checking helper`
- `Reformatted`
- `WaitPage time`
- `AsyncProcess duration`
- `async process queue delay`
- `trial count stats`
- `scaling slowdown`
- `requests/sec`
- `bot initialization`
- `detection and reporting of bots`
- `RQ worker count`
- `performance-test`
- `bot duration`
- `bot output`
- `tabulate-based`
- `ANSI-colored`
- `Refactored performance`
- `Separated bot`
- `Redirected bot`
- `Improved performance`
- `\x60_Py`
- `\x60get_package`
- `\x60get_locales`
- `\x60check_translations`
- `\x60linspace`
- `\x60format_timedelta`
- `\x60get_fitting_font`
- `\x60pretty_format`
- `\x60S3Storage`
- `\x60NumpySerializer`
- `\x60SVGLogo`
- `\x60os\.path\.remove`
- `translation test`
- `translation validation`
- `translation_contains`
- `_experiment_variables`
- `pybabel`
- `Installed demo dependencies`
- `\x60@local_only`
- `\x60@ci_only`
- `docs/scripts`
- `documentation navigation`
- `documentation builds for`
- `strip_url_parameters`
- `custom \x60cache\x60`
- `dict_to_js_vars`
- `Standardized.*capitalization`
- `IDE recommendations`
- `experiment scripts where they were unused`
- `demo and test experiment classes`
- `generate_version_switcher`
- `Refactored timeline page`
- `Updated S3 test`
- `Replaced.*S3 emulator`
- `Switched docs deployment`
- `auto-cancel redundant`
- `Expanded Playwright`
- `stabilized visual snapshots`
- `Disallow PsyNet requirements pinned to master`
- `Exported datetimes`
- `Suppressed.*DeprecationWarning`
- `\x60CI\x60 environment variable`
- `StretchedTimbre`
- `Lucid.*error message`
- `incorrect Sphinx`
- `malformed Sphinx`
- `experiment status payload`
- `chatroom to Rock`
- `getting started.*section`
- `\.vscode`
- `demo/docs example`
- `Removed.*\bCI\b`
- `Removed \x60dict_to_js_vars\x60`
- `Removed the PgBadger`
- `\x60generate_text_file\x60`
- `\x60WorkerAsyncProcess\x60`
- `\x60Notifier\x60.*memory`
- `\x60Participant\.fail\x60.*wrong argument`
- `resource type mismatch`
- `incorrect property name`
