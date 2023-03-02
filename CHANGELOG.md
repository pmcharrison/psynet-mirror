# CHANGELOG

# [10.0.0rc3] Release candidate 2023-03-02

#### Fixed
- Removed RSTCloth dependency (author: Pol van Rijn, reviewer: Peter Harrison).
- Fixed for compatibility with new Dallinger dashboard code (author: Pol van Rijn, reviewer: Peter Harrison).

#### Added
- Added support in pyproject.toml for making PyPi releases (author: Frank Höger, reviewer: Peter Harrison).
- Added Video Gibbs support (author: Pol van Rijn, reviewers: Peter Harrison, Frank Höger).

#### Changed
- Migrated build system requirements and project metadata from setup.py/setup.cfg to pyproject.toml, (see https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/) (author: Frank Höger, reviewer: Peter Harrison).
- Migrated AWS CLI (awscli) functionality to `boto3` to reduce dependencies (author: Pol van Rijn, reviewer: Peter Harrison).

# [10.0.0rc2] Release candidate 2023-02-07

#### Fixed
- Scroll current item in sidebar menu into view when navigating Sphinx documentation (author: Frank Höger, reviewer: Peter Harrison).

#### Added
- Added Prolific documentation with screenshots (author: Pol van Rijn).

#### Changed
- Demographics are now saved in the participant table (author: Peter Harrison).
- Check if amount in cents/predicted duration in minutes for Prolific is identical to the hourly rate of the experiment (author: Pol van Rijn, reviewers: Peter Harrison, Frank Höger).

#### Removed
- Removed unnecessary field `mode` in config.txt of all demos (author: Pol van Rijn, reviewers: Peter Harrison, Frank Höger).
- Removed old deprecated code (author: Frank Höger, reviewer: Peter Harrison):
  - psynet/consent.py
    - `MTurkStandardConsent`
    - `MTurkStandardConsentPage`
    - `MTurkAudiovisualConsent`
    - `MTurkAudiovisualConsentPage`
  - psynet/modular_page.py
    - `NAFCControl`
  - psynet/page.py
    - `NAFCPage`
    - `TextInputPage`
    - `SliderPage`
    - `AudioSliderPage`
    - `NumberInputPage`
  - psynet/timeline.py
    - `multi_page_maker`

# [10.0.0rc1] Release candidate 2023-01-27

#### Added
- Added RUN.md instructions for running experiments in Docker (author: Peter Harrison).
- Drafted 'generic recruiter', an improved version of Dallinger's hot-air recruiter (author: Peter Harrison).
- Added missing parts of API documentation to Sphinx website (author: Frank Höger, reviewer: Peter Harrison).
- Added `config_defaults` to experiment class, which allows for specifying default config variables programmatically (author: Peter Harrison, reviewer: Frank Höger).

#### Changed
- Store assets in `static/assets` rather than `static/local_storage` (author: Peter Harrison).

#### Fixed
- Make assets display properly in dashboard again (author: Peter Harrison).
- Fix Unity integration with Prolific (author: Peter Harrison).

# [10.0.0rc0] Release candidate 2023-01-17

#### Added
- Marked translatable parts of the PsyNet UI, consent, and demographics (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).
- Added a locale variable to the participant (default: experiment language) which can be changed during the experiment (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).
- Added a `currency` variable to the experiment, which allows using a currency different than dollars, e.g., in Prolific (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).
- Wrote documentation for translating experiments (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).

#### Fixed
- Updated the translation demo (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).
- Use latin-1 encoding for pickling JSON instead of ASCII to work well with non-ASCII characters (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).
- Add additional dependencies to PsyNet: `babel` and `python-gettext` (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).
- Replaced typo in `participant` (author: Pol van Rijn, reviewer: Frank Höger and Peter Harrison).

# [9.4.1] Released on 2023-01-11

#### Added
- Added Princeton University consent for CAP-Recruiter deployment (author: Frank Höger, reviewer: Peter Harrison).

#### Fixed
- Fixed warnings when building the Sphinx documentation (author: Frank Höger, reviewer: Peter Harrison).

# [9.4.0] Released on 2022-12-21

#### Added
- Added MIT license.
- Added and updated experimenter and developer documentation; changed layout to `furo` theme (author: Peter Harrison, reviewer: Frank Höger).

#### Fixed
- Fixed node details visualization in dashboard monitor (author: Peter Harrison).

#### Updated
- Updated `Dallinger` to `v9.3.0` which comes with many Docker improvements. See the complete release notes at https://github.com/Dallinger/Dallinger/releases/tag/v9.3.0.
- Updated README.md (author: Peter Harrison).

# [9.3.0] Released on 2022-11-26

#### Added
- Added support for panning in JSSynth (author: Peter Harrison).
- Added new parameter `show_free_text_option` to `RadioButtonControl` which appends a free text option to the list of options (author: Pol van Rijn, reviewer: Peter Harrison).

#### Fixed
- Fixed typo in `LexTaleTest` (author: Pol van Rijn).

#### Changed
- Changed gender questionnaire (author: Pol van Rijn, reviewer: Peter Harrison).
- Renamed 'hits' to 'tasks' in `CapRecruiter` API calls (author: Frank Höger).

#### Updated
- Updated `Dallinger` to `v9.2.1` fixing the issue of not being able to deploy to Heroku. See the complete release notes at https://github.com/Dallinger/Dallinger/releases/tag/v9.2.1.
- Updated references for new GitLab repository path (`computational-audition-lab` -> `PsyNetDev`).
- Updated `README.md`.
- Updated Linux installation instructions.

# [9.2.0] Released on 2022-11-10

#### Fixed
- Fixed display of `ExperimentConfigs`, `LucidRIDs`, and `Responses` database tables in dashboard (author: Peter Harrison, reviewer: Frank Höger).
- Hotfix that fixes import errors for experiment containing stimulus sets. Will be superceded by the storage branch, to be merged soon (author: Peter Harrison).
- Fixed bug where the wrong participant information was given in error pages (author: Peter Harrison, reviewer: Frank Höger).
- Renamed `psynet` to `PsyNet` in .gitlab-ci.yml (author: Frank Höger).
- Removed failing detection of `editable mode` in `psynet update` command (author: Frank Höger).

#### Added
- Added `utils.get_experiment`, an easy way to get an `Experiment` instance from an arbitrary part of your code (author: Peter Harrison, reviewer: Pol van Rijn).
- Added the ability to customize the SQLAlchemy polymorphic identity of a given class by setting the `polymorphic_identity` attribute in the class definition (author: Peter Harrison, reviewer: Pol van Rijn).
- Added new tools for creating bots in PsyNet. Bots are artificially simulated participants that progress through the experiment in much the same way as ordinary PsyNet participants, with the exception that they never interact with the web browser itself, but instead interact with the Python objects that underlie the timeline. Bots can be used for creating tests for PsyNet experiments, for simulating emergent network dynamics, or for introducing controllable characters into the actual experiment deployment (author: Peter Harrison, reviewer: Pol van Rijn):

A bot is created with a command like the following:

``` py
from psynet.bot import Bot

bot = Bot()
```

At this point you can set custom variables within that bot object, for example to correspond to relevant participant parameters such as gender or musicianship. You might do this deterministically or stochastically, depending on your interest.

```py
import random

bot.var.gender = "female"
bot.var.is_musician = random.sample([True, False], 1][0]
```

You can also define a universal bot initialization method on the Experiment class, like this:

``` py
class Exp(...):
    def initialize_bot(self, bot):
        bot.var.is_musician = random.sample([True, False], 1)[0]
```

This method will be called automatically whenever a bot is initialized.

PsyNet needs to be told how bots respond to particular pages. This can be done in two ways.

The first way is to pass a `bot_response` function to the Page or Control constructor. For example:

```py
ModularPage(
    "How many years of musical training do you have?",
    TextControl(
        ...
        bot_response=lambda bot: 10 if bot.var.is_musician else 0,
    )
)
```

This `bot_response` can take various other parameters, including the `experiment`, the `page`, and the `prompt`, so that you have all the information you need to define the bot's response.

Alternatively, if you are defining a custom Page or Control class, you can define a custom `get_bot_response` method, which achieves much the same response.

To tell the bot to progress through the experiment, you can use one of two functions: `take_page` and `take_experiment`. The first advances by just one page, whereas the latter progresses through the experiment. The speed of advancement can be determined by a parameter that acts as a multiplier on each page's `time_estimate` value.

There are various ways to configure bots to take part in a real experiment. One of the easiest currently is to define a scheduled task that occurs periodically in the background of the experiment and runs a bot participant.

```py
    @staticmethod
    @scheduled_task("interval", minutes=5 / 60, max_instances=1)
    def run_bot_participant():
        # Every 7 seconds, runs a bot participant.
        experiment = get_experiment()
        if experiment.var.launched:
            bot = Bot()
            bot.take_experiment()
```
- Added `psynet generate-constraints` to command line (author: Frank Höger; reviewer: Peter Harrison).

#### Updated
- Updated `Dallinger` to `v9.2.0` adding experimental support for Docker deployment. See the complete release notes at https://github.com/Dallinger/Dallinger/releases/tag/v9.2.0.

# [9.1.2] Released on 2022-08-13

#### Fixed
- Fixed a bug that caused incorrect participant details in error messages (author: Peter Harrison, reviewer: Frank Höger).

# [9.1.1] Released on 2022-08-03

#### Fixed
- Fixed a bug that introduced import errors for experiments containing stimulus sets (author: Peter Harrison, reviewer: Frank Höger).

# [9.1.0] Released on 2022-07-11

#### Added
- Added PsyNetRecruiter base class passing down the missing `notify_duration_exceeded` method to `BaseLucidRecruiter`. (author: Frank Höger; reviewer: Peter Harrison)

#### Fixed
- Fixed further issues with database tables not being exported properly. (author: Peter Harrison, reviewer: Frank Höger)

#### Changed
- Prevent opening a new window when clicking on the `Begin Experiment` button on the Ad page when using `LucidRecruiter`. (author: Frank Höger, reviewer: Peter Harrison)
- Register `cap_recruiter_auth_token` config variable; cleanup CAP-Recruiter demo. (author: Frank Höger, reviewer: Peter Harrison)
- Changed fields of the `LucidRIDs` database table: Removed fields `failed`, `failed_reason`, and `time_of_death`; added field `termination_requested_at`.
 `termination_requested_at` is now set each time a termination request is made to Lucid Marketplace. (author: Frank Höger; reviewer: Peter Harrison)
- Ensure that `Exp.setup()` only happens in the once, in the launch routine. (author: Peter Harrison, reviewer: Frank Höger)

# [9.0.1] Released on 2022-07-08

#### Added
- Added more comprehensive tests for data export. (author: Peter Harrison, reviewer: Frank Höger)

#### Fixed
- Fixed problem where not all database tables were being exported. (author: Peter Harrison, reviewer: Frank Höger)
- Fixed problem where two 'ExperimentConfig' database objects were being created. (author: Peter Harrison, reviewer: Frank Höger)

#### Changed
- PsyNet now just exports data as CSV files, not JSON files; doing both seemed redundant. (author: Peter Harrison, reviewer: Frank Höger)
- PsyNet's exported CSV files now correspond directly to the class names of the exported objects,
  without any automatic conversion from CamelCase to snake_case. This seems more transparent and less error-prone. (author: Peter Harrison, reviewer: Frank Höger)

# [9.0.0] Released on 2022-06-17

#### Breaking changes
- The URL format for PsyNet experiments is now a bit cleaner, looking something like this:
  `http://127.0.0.1:5000/timeline?participant_id=1&auth_token=63252608-ee35-40cc-89be-9bbb82120c5d`
  (author: Peter Harrison, reviewer: Frank Höger).

#### Fixed
- Fixed bug in `cls.inherits_table` (author: Peter Harrison, reviewer: Frank Höger).
- Fixed bug in `openwindow` JavaScript function in `ad.html` which prevented propagation
  of Prolific specific URL parameters (author: Frank Höger, reviewer: Peter Harrison).
- Refreshing the first page of the experiment no longer causes an error,
  as the participant's authentication token is now loaded automatically into the URL
  (author: Peter Harrison, reviewer: Frank Höger).
- Patched unreliable behavior in `dallinger.identity.participantId`
  (author: Peter Harrison; reviewer: Frank Höger).

#### Added
- Added explicit support for `dict` and `list` types in `claim_field`; importantly, these now provide
  mutation tracking, so that in-place modifications to these fields will be picked up properly
  by SQLAlchemy (author: Peter Harrison, reviewer: Frank Höger).
- Added demos for `Prolific` and `CAP-Recruiter` recruitment (author: Frank Höger).
- Added Unity autoplay demo test (author: Frank Höger, reviewer: Peter Harrison).

#### Changed

- Updated the Unity C# code to adapt to the new URL format (author: Frank Höger, reviewer: Ofer Tchernichovski).
- `PageMaker` has been made much more flexible. Instead of being constrained to
  returning just one page, they may now return pretty much any kind of
  (arbitrarily nested) logic. This flexibility likewise now applies to `show_trial`
  and `show_feedback` (author: Peter Harrison, reviewer: Frank Höger).
- It is no longer required to specify `num_pages` or `check_num_pages` when defining a custom `Trial` class,
  and such specifications will be ignored (author: Peter Harrison, reviewer: Frank Höger).
- `participant.elt_id` now takes a different form. Instead of comprising a single integer, it now
  corresponds to a list of integers, which index into nested page makers of arbitrary depth.
  This should not affect most PsyNet users directly (author: Peter Harrison, reviewer: Frank Höger).
- Made the test suite more scalable by splitting the single job which ran all tests into multiple (5) smaller jobs
  that run in parallel.The overall time to run the tests was thereby reduced from ~18 min. to ~8 min
  (author: Frank Höger, reviewer: Peter Harrison).
- Renamed the PsyNet base layout template to `psynet_layout.html` (author: Peter Harrison, reviewer: Frank Höger).
- Prevented opening a new window when clicking on the `Begin Experiment` button on the Ad page
  when using `LucidRecruiter` (author: Frank Höger, reviewer: Peter Harrison).

# [8.0.0] Released on 2022-05-23

#### Breaking changes
- Dropped support for Python 3.7.

#### Fixed
- Fixed bug whereby kwargs were not propagated properly in `TextInputPage`.
  (author: Peter Harrison, reviewer: Frank Höger)

#### Added
- `var.get()` now supports default arguments.
  (author: Peter Harrison, reviewer: Frank Höger)

#### Updated
- Updated `Dallinger` to `v9.0.0`, see release notes at https://github.com/Dallinger/Dallinger/releases/tag/v9.0.0.
  Includes a bugfix which adds `clock` support in Docker.
  (author: Frank Höger, reviewer: Peter Harrison)
- Update Google Chrome and driver to version 101.x in `.gitlab-ci.yml`.
  (author: Frank Höger)

# [7.2.0] Released on 2022-05-16

#### Fixed
- Fixed broken loop in `AudioPrompt` when `controls=False`
  (author: Peter Harrison, reviewer: Frank Höger)
- More aggressive DB commits in `finalize_trial`
  (author: Peter Harrison)
- More robust jsonification in data export
  (author: Peter Harrison)
- Remove unintended timeout behavior from `run_subprocess_with_live_output`
  (author: Peter Harrison)
- Fixed participant resuming via the dashboard, which was broken by the introduction of the `auth_token`
  functionality.
  (author: Peter Harrison, reviewer: Frank Höger)

#### Added
- Added LUCID Marketplace recruiting integration:
  * Added `DevLucidRecruiter` and `LucidRecruiter` classes.
  * Added HTML templates for final pages for the three cases 'successful', 'unsuccessful',
    and 'rejected consent').
  * Added LUCID recruiting demo.
  NOTE: Currently only to be used in conjunction with Dallinger branch `docker-clock`.
  (author: Frank Höger, reviewer: Peter Harrison)
- Added `failure_tags` to `RejectedConsentPage`; added `failed_reason` to data returned from
  `BaseCapRecruiter`'s `reward_bonus` method.
  (author: Frank Höger, reviewer: Peter Harrison)
- Notify the CAP-Recruiter API when a participant has failed.
  (author: Frank Höger, reviewer: Peter Harrison)

#### Changed
- Replaced deprecated MTurk consents in demos with new consents `AudiovisualConsent` and `MainConsent`.
  (author: Frank Höger, reviewer: Peter Harrison)

# [7.1.0] Released on 2022-04-25

#### Fixed
- Fixed developer mode by calling reset_console
  (author: Peter Harrison, reviewer: Frank Höger)

- Fixed an error which occasionally happened when PsyNet tried to close down zombie processes,
  when the process would close itself before PsyNet managed to close it, causing a
  psutil.NoProcessFound error. Now such errors are ignored. The implementation uses a new function
  called psynet.command_line.safely_kill_process.
  (author: Peter Harrison, reviewer: Pol van Rijn)

- Fixed Unity demo by replacing it with a new autoplay version containing updated WebGL files.
  (author: Ofer Tchernichovski, reviewers: Peter Harrison, Frank Höger)

#### Added
- PsyNet now supports the definition of custom SQL classes that are not subclasses of pre-existing
  PsyNet/Dallinger objects.
  (author: Peter Harrison, reviewer: Pol van Rijn)

  These objects are stored in their own tables and can be seen in the dashboard. The API is very simple:

  ```py
  from psynet.data import SQLBase, SQLMixin, register_table

  @register_table
  class Bird(SQLBase, SQLMixin):
      __tablename__ = "bird"

  class Sparrow(Bird):
      pass

  class Robin(Bird):
      pass
  ```

  The above example defines a new database table called 'bird', in which we can store robins and sparrows.

- Added new demos custom_table_simple and custom_table_complex that illustrate sqlalchemy usage via this new PsyNet feature.
  (author: Peter Harrison, reviewer: Pol van Rijn)
- Added a new, more robust version of init_db for resetting database state: psynet.data.init_db
  (author: Peter Harrison, reviewer: Pol van Rijn)
- Added auth_token and authToken to be used by the Unity API.
  (author: Frank Höger, reviewer: Peter Harrison)

#### Changed
- Changed the visual behavior of the five consent pages recently introduced by always showing the buttons at the bottom of the pages and making the text overall smaller.
  (author: Frank Höger, reviewer: Peter Harrison)

# [7.0.0] Released on 2022-03-27

#### Fixed
- Fixed problem in `auth_token` verification for JS logging.
  (author: Peter Harrison, reviewer: Frank Höger)
- Fixed long-standing issue where console would behave strangely after cancelling Dallinger/PsyNet commands.
  (author: Peter Harrison, reviewer: Frank Höger)
- Bugfix in imitation chain demo.
  (author: Peter Harrison)
- Fixed out-of-date dependency in PsyNet timeline demos.
  (author: Peter Harrison, reviewer: Frank Höger)
- PsyNet now uses Dallinger's functionality from PR 2324 for supporting custom Participant classes. This should solve some occasional database inconsistency errors.
  (author: Peter Harrison, reviewer: Frank Höger)

#### Added
- Added `start_trial_automatically` option to PsyNet pages (`default=True`), which can be used e.g. to disable autoplay for audio.
  (author: Peter Harrison, reviewer: Frank Höger)

#### Changed
- Remove time estimate text in new consents.
  (author: Frank Höger)
- Increase timeout in regression tests.
  (author: Peter Harrison)
- Set default number of threads to 1 in `psynet debug`, which saves about a second off the start-up time.
  (author: Peter Harrison, reviewer: Frank Höger)
- Optimised some import logic to improve import times. This should become particularly relevant once a
  pending Dallinger pull request is merged.
  (author: Peter Harrison, reviewer: Frank Höger)
- PsyNet now detects and kills old Heroku and Chrome sessions before starting a new debug session.
  (author: Peter Harrison, reviewer: Frank Höger)
- Disabled `check_participant_opened_devtools` by default; detecting participants opening developer tools
seems to be unstable, so experimenters should only enable this check at their own risk.
  (author: Peter Harrison, reviewer: Frank Höger)
- Updated the categories in the dashboard database table to make more sense with PsyNet objects (e.g. replacing Infos with Trials).
  (author: Peter Harrison, reviewer: Frank Höger)
- The regression test fixtures have been updated with the goal of fixing recent problems with test unreliability.
  (author: Peter Harrison, reviewer: Frank Höger)
- `psynet debug` now provides hot-refresh functionality by default. This means that you can edit the experiment code and see your changes without relaunching the experiment, simply instead refreshing your web browser. This can be disabled by passing the `--legacy` option to `psynet debug`.
  (author: Peter Harrison, reviewer: Frank Höger)

#### Updated
- Updated Dallinger to v8.1.0, see release notes at https://github.com/Dallinger/Dallinger/releases/tag/v8.1.0

# [6.0.1] Released on 2022-03-02

#### Fixed
- Changed logic for verifying the participant identity by replacing `fingerprintHash`/`fingerprint_hash` with a randomly generated `authToken`/`auth_token` stored in the participant table.s
  (author: Frank Höger, reviewer: Peter Harrison)
- Fix Dallinger version in demos' constraints.
  (author: Frank Höger)

#### Added
- Added new participant variable auth_token.
  (author: Frank Höger, reviewer: Peter Harrison)

# [6.0.0] Released on 2022-02-23

#### Fixed
- The response buttons in the headphone screening task now are disabled until the audio has finished playing 
  (author: Pol van Rijn, reviewer: Peter Harrison)
- Fix deprecation warnings by replacing Selenium `find_element_by_*` commands with `find_element`
  (author: Frank Höger)

#### Added
- Add new consent pages:
  `MainConsentPage`,
  `DatabaseConsentPage`,
  `AudiovisualConsentPage`,
  `OpenScienceConsentPage`,
  `VoluntaryWithNoCompensationConsentPage`
  (author: Frank Höger, reviewer: Nori Jacoby)
- Added new experiment variables `window_width` and `window_height` to allow for customization of
  the experiment window's size. Default: 1024 x 768
  (author: Fotini Deligiannaki, reviewer: Peter Harrison)
- Added new optional property `block_copy_paste` in `TextControl` that prevents copying, cutting and
  pasting in text input pages
  (author: Raja Marjieh, reviewer: Peter Harrison)
- Added functionality for detecting users opening the developer console in their web browser. If
  users open the developer console, they are shown a warning message telling them that they might be
  in trouble. The event is then logged in the participant table. This functionality can be disabled
  by setting `check_participant_opened_devtools=False` in the experiment variables 
  (author: Pol van Rijn, reviewer: Peter Harrison)
- Added pre-sandbox/deploy sanity checks that check whether the values of
  `initial_recruitment_size` and `us_only` are set appropriately
  (author: Erika Tsumaya, reviewer: Peter Harrison)
- Added Python version to experiment variables
  (author: Frank Höger, reviewer: Peter Harrison)

#### Changed
- Use `fingerprintHash`/`fingerprint_hash` instead of `assignmentId`/`assignment_id` to verify
  participant identity
  (author: Frank Höger, reviewer: Peter Harrison)
- Changed text under ASCII logo in command line output
  (author: Frank Höger, reviewer: Peter Harrison)
- Changed signature of `BaseCapRecruiter.reward_bonus` method due to breaking change in Dallinger v8.0.0
  (author: Frank Höger)

#### Updated
- Updated Dallinger to v8.0.0, see release notes at https://github.com/Dallinger/Dallinger/pull/3853
  (author: Frank Höger)
- Updated Python to version 3.10 and Dallinger to version 8.0.0. in `.gitlab-ci.yml`
  (author: Frank Höger)
- Update docs for Python 3.10
  (author: Frank Höger)
- Updated black, isort, and flake8 to latest versions (used when running the Git pre-commit hooks)
  (author: Frank Höger)

#### Deprecated
  - Deprecated `MTurkStandardConsentPage` and `MTurkAudiovisualConsentPage`
  (author: Frank Höger)

# [5.2.0] Released on 2022-01-21

#### Fixed
- Fixed `psynet export` failure for large databases.
- Temporary fix for missing `time_taken` in `UnityPage` response's metadata.
- Fixed breaking changes of new `time_estiamte` in demo `imitation_chain`.
- Improved the error message for duplicated module IDs.

#### Added
- Added a new parameter `fail_on_timeout` (default = `True`) to `wait_while`;
  if this is set to `False`, the participant is no longer failed once the
  `max_wait_time` is exceeded, but instead continues with the experiment.
- Added `source` and `participant` attributes for `Network` classes.
- Added command-line tool `psynet rpdb`, which is an alias for `nc` allowing
  to easily perform (remote) debugging.
- Added `degree` and `phase` as `export_vars` in `ChainSource`.
- Added `phase` as `export_var` in `ChainNode`.
- Added `degree`, `phase` and `node_id` as `export_vars` in `ChainTrial`.
- Added GitLab merge request template.
- Added `username` attribute to `HelloPrompt`.
- Added regression test for data export.
- Added Monterey installation documentation.

#### Changed
- Link 'Edit in GitLab' button to `master`, not `docs-staging` branch.

# [5.1.0] Released on 2021-11-30

#### Added
- Added 'Edit on GitLab' button to documentation pages.
- Added `FreeTappingRecordTest` to prescreens.

#### Fixed
- Renamed `clickedObject` to `clicked_object` in the graph experiment demo's `format_answer` method.

#### Updated
- Updated Dallinger to v7.8.0.
- Updated google-chrome and chromedriver to v96.x in .gitlab-ci.yml.

# [5.0.2] Released on 2021-11-15

#### Changed
- The time taken by the participant is now stored as a property of the `Trial` object
  (`Trial.time_taken`).
- By default, dynamic updating of progress bar and bonus display now only occurs
  for Unity pages. This makes the logs cleaner for standard PsyNet pages.

#### Fixed
- Updated `get_template` to remove use of deprecated function `read_text`.
- (Re-)Added `jQuery` (v3.6.0) to the HTML head section of timeline-page.html. In Dallinger jQuery
  only gets loaded in the body section which causes a `$ is not defined` JS error when using the
  `AudioRecordControl` in PsyNet.

# [5.0.1] Released on 2021-11-10

#### Fixed
- Fixed regressions in prescreening tasks.
- Fixed demos' constraints.
- Improved changelog notes for v5.0.0.

# [5.0.0] Released on 2021-11-10

#### Added
- Added ability to disable progress bar (`experiment.var.show_progress_bar`).
- Added dallinger version to `psynet --version` output.
- Added `dallinger_version` experiment variable.
- Added audio-forced-choice prescreening task (thanks Pol van Rijn, Harin Lee).

#### Breaking changes
- Refactored JavaScript variable and function names to camelCase,
  and HTML IDs and attributes to kebab-case.
  Experiments referring explicitly to these components may need to be
  updated accordingly.

The time estimation process has been revised in PsyNet, resulting in the following changes:

- Time-based bonuses now work differently for page makers and multi-page makers. 
  Instead of allocating bonus according to the (multi-)page maker's `
  time_estimate` attribute, bonuses are now allocated according to the 
  `time_estimate` attributes of the page(s) generated by the (multi-)page maker.
  The (multi-)page maker's own `time_estimate` is now only used for time estimation purposes,
  determining for example the progress bar and the predicted experiment duration/bonus 
  displayed in the ad. In the case where the generated page(s) is/are missing a time estimate,
  the time estimate from the page maker object will be used instead, as before.
  - As a result of the above improvement, inaccurate `num_pages` attributes in multi-page trials 
    no longer cause inaccurate bonus estimations, only inaccurate progress bars. In these cases
    PsyNet now displays a warning message advising the experimenter to set the appropriate 
    number of pages, with this appropriate number of pages being displayed on the basis of 
    the current run-time evaluation.
- The mechanism for setting the time estimates for trials has now changed. 
  Previously such time estimates were specified by passing an argument called
  `time_estimate_per_trial` to the trial maker. This introduced an undesirable
  non-locality to PsyNet implementations, whereby changes to the trial class 
  that impacted on time estimation had to be propagated far away to the 
  trial maker constructor call, which was easy to forget.
  In the new version, trial time estimates are specified by setting a 
  class attribute called `time_estimate` in the custom trial class, for example:
  
```py
class CustomTrial(Trial):
    time_estimate = 5
```

  An error will be thrown if the user neglects to set this `time_estimate`, 
  or if they try to set it via the trial maker.

  To update PsyNet code to follow this new convention, see below.
  Here's an example of what the code might look like before:

```py
class CustomTrial(Trial):
    def show_trial(self, experiment, participant):
        return InfoPage("Hello!", time_estimate=5)

trial_maker = TrialMaker(**params, time_estimate_per_trial=5)
```

The updated code should look like this:

```py
class CustomTrial(Trial):
    time_estimate = 5
    
    def show_trial(self, experiment, participant):
        return InfoPage("Hello!", time_estimate=self.time_estimate)

trial_maker = TrialMaker(**params)
```

- New ``Trial`` fields have been added to help keep track of how time credit was assigned for trials:
  ``time_credit_before_trial``, ``time_credit_after_trial``, and ``time_credit_from_trial``.
  If a trial turned out to give an unexpected amount of time credit,
  PsyNet now delivers a warning message and recommends a revised value for ``time_estimate``.
  
#### Other changes
- PsyNet now supports serialization of arbitrary objects to database fields.
  Serialization is accomplished using `jsonpickle`.
  No change should be necessary to experiment implementations;
  however the underlying database representation for some fields
  will have changed slightly. As a result, it is unlikely to be possible
  to relaunch experiments from zip files using PsyNet >=5.0.0 if the original version
  was deployed on PsyNet <5.0.0.

#### Fixed
- Removed external references to `jQuery` and `platform` JavaScript libraries.
- Specified the version of Dallinger in gitlab-ci.yml.

# [4.2.1] Released on 2021-10-31

#### Fixed
- Implemented fix for networks not growing properly in within-participant experiments 
  with asynchronous processing.

# [4.2.0] Released on 2021-10-27

#### Added
- Added new argument 'mirrored' to VideoRecordControl and VideoPrompt allowing
  the video to be displayed as if looking into a mirror.
- Added a button "Abort experiment" to the ad and error page, including two new environment
  variables 'show_abort_button' and 'min_accumulated_bonus_for_abort'. These additions
  make it possible for the experimenter to allow the participant to abort an experiment and
  be compensated automatically given the minimum amount of bonus has already been accumulated.
  The default is to not display the button.

#### Changed
- Replaced the Audio Gibbs demo with an implementation of the emotional prosody
  experiment from our 2020 NeurIPS paper (Harrison et al., 2020)
  (thanks Pol van Rijn!).

# [4.1.0] Released on 2021-10-15

#### Added
- Added new dashboard panel called 'Participant'.
  Here one can search participants by participant ID, worker ID, or assignment ID,
  and easily see the current status of the participant 
  as well as their current estimated bonus.
  Functionality is also provided for resuming a given participant's session
  via a special URL.
- Added documentation for the ``compute_bonus`` method.

#### Changed
- Reduced the default performance threshold in `LexTaleTest` from 10 to 8.
  The previous performance threshold was found to be much too stringent.
- Migrated the ``compute_bonus`` method from the ``Experiment`` class to the 
  ``Participant`` class. Researchers should not be using this method directly,
  so this change should not affect most people.

#### Fixed
- Fixed ReppMarkersTest

#### Updated
- Updated Dallinger to v7.7.0.

# [4.0.0] Released on 2021-09-13

#### Added
- Added a collection of dense rating paradigms (see `psynet.trial.dense`).
  These are still experimental, but they do have draft documentation.
  
#### Changed
- Refactored the logic for queueing asynchronous processes, and created a new method
  ``queue_async_method`` that makes it easy to queue asynchronous functions for 
  database objects such as networks and trials.
  See the ``async_pruning`` demo for an example.

#### Fixed
- Fixed bug in ``AudioSliderControl`` (renaming of ``wrap`` to ``random_wrap`` 
  and deletion of ``phase`` arguments not propagated properly).
- The `promptEnd` event of JSSynth is now triggered by `promptStart` rather than `trialStart`.
  This facilitates customization where the JSSynth is triggered multiple times in
  the same trial.

#### Renamed
- Renamed `check_timeout_interval` to `check_timeout_interval_sec`.

#### Breaking changes
- Repeat trials are now constructed in a slightly different way. 
  Previously, they were constructed in a way that permitted slight variation
  in surface features between a repeat trial and its originator;
  in the case of GSP, for example, this would mean a different randomized
  starting location for the slider. However, this behavior ended up 
  being problematic for extensibility. In the new implementation, repeat 
  trials are by default exact clones of their parents.
- `with_trial_maker_namespace` is now changed to remove the leading hyphens
  from trial-maker variables as they are stored in the database.
  This has the consequence that these variables (e.g. performance check results)
  will now be exported directly by `psynet export` into the main CSV files,
  rather than only being available in `db-snapshot`. 
  This is a breaking change in that it will not be possible to relaunch
  experiments from zip file that were originally deployed with a 
  previous PsyNet version.

# [3.1.0] Released on 2021-08-10

#### Added
- Added `show_footer` experiment variable.
- Added `psynet update` command.

#### Changed
- In the footer, only display detailed bonus (basic + extra) if `performance_bonus` > 0.

#### Fixed
- Fixed display of progress and bonus on Unity pages.
- Fixed wrong `import` documentation.
- Fixed code for black, isort, and flake8.

#### Updated
- Updated Dallinger to v7.6.0.
- Updated singing_iterated and tapping_* demos.

# [3.0.0] Released on 2021-08-03

#### Fixed
- Fixed bug in 'stop' button for `AudioPrompt`.
- Fixed bug when displaying tooltip and module details in dashboard.
- Removed temporary fix for 'assignmenId' from start page.

#### Added
- Added demo of translation workflow (see `demos/translation`).
- Added new iterated singing demo (see `demos/singing_iterated`).
- Added a new type of slider for `SliderControl`: `circular_slider`.
- Added optional `random_wrap` functionality to `SliderControl`.
- Prepared PsyNet for new Docker functionality. 
  Note new format of requirements in `requirements.txt`.
  The functionality will be ready-to-use once the Dallinger pull request
  https://github.com/Dallinger/Dallinger/pull/3016 is merged.
- Added `generate_constraints.py` for regenerating constraints for all PsyNet demos.
- Added experimental graph network API.

#### Changed
- Revised implementation for `audio_gibbs_demo`.
- Added more detailed info to the bonus displayed in the footer.

#### Breaking changes

- The API for `ProgressDisplay` and `ProgressStage` has now been improved.
  `ProgressDisplay` no longer takes a `duration` argument, the duration
  is instead computed automatically from the provided `ProgressStage` objects.
  `ProgressStage` now accepts a single number as the `time` argument,
  which determines the duration of the stage. The start time and end time 
  are then inferred automatically with respect to the previous stage in the sequence.
  One can therefore write something like this:
  
````python
from psynet.timeline import ProgressDisplay, ProgressStage

ProgressDisplay(
    stages=[
        ProgressStage(0.75, "Wait a moment...", color="grey"),
        ProgressStage(1, "Red!", color="red"),
        ProgressStage(1, "Green!", color="green"),
        ProgressStage(1, "Blue!", color="blue"),
    ],
),
````

# [2.4.0] Released on 2021-07-21

#### Fixed
- Improved efficiency of StimulusVersion queries.
- Fixed experiment network display bug.
- Fixed bug in GSP seed generation, 
  whereby the initial `active_index` selection was not entirely uniform.

#### Added
- Added failed_reason text to nodes and infos when calling their respective fail methods
- Use bumpversion for incrementing release versions.
- Added MANIFEST.in
- Added installation instructions for macOS Big Sur 11.3/M1

#### Changed
- Pin Dallinger to version >=7.5.0

# [2.3.0] Released on 2021-07-07

#### Added
- Store browser and platform information in participant table.

#### Changed
- New way of how the contents of the `Ad page` are specified. See https://computational-audition-lab.gitlab.io/psynet/experimenter/ad_page.html for details.
- PsyNet now enforces at least one consent element to be included in a timeline. See `psynet/consent.py` for available consent modules. If you're sure you want to omit the consent form, include a ``NoConsent`` element.
- Minor improvement to video synchronization.

#### Updated
- Updated repp and tapping demos.
- Updated Dallinger to v7.5.0.

#### Fixed
- Fixed SQLAlchemy start-up error introduced in v2.2.1.

# [2.2.1] Released on 2021-06-21

#### Fixed
- Fixed bug to make pre-deployment routines work again

# [2.2.0] Released on 2021-06-16

#### Added
- Added new experiment variable ``hard_max_experiment_payment`` which allows for setting a hard, absolute limit on the amount spent in an experiment. Bonuses are not paid from the point the value is reached and the amount of unpaid bonus is saved in the participant's `unpaid_bonus` variable. Default is $1100.
- Allow for changing the soft and hard spending limits from the dashboard's timeline tab. Clicking on the upper, green progress bar shows/hides the corresponding UI widgets.

#### Changed
- Renamed the `media_url` property of `RecordTrial` to `recording_url` so as to not clash with the same method name in `StaticTrial`. 

#### Fixed
- Fixed bug with wrong `minimal_interactions` functionality of `SliderControl` due to duplicate event handling in `control.html`.
- The renamed `recording_url` method incorrectly only returned camera urls. This was replaced with the correct `url` key. 
- Fixed issue where `max_loop_time_condition` would be logged to the participant table
  every trial in a trial maker.

# [2.1.2] Released on 2021-06-15

#### Fixed
- Hotfix for bonus/time estimation bug: `time_estimate` for `EndPage`
  is now set to zero. This means that experiment estimated durations
  (and corresponding bonuses) will decrease slighly.

# [2.1.1] Released on 2021-06-10

#### Fixed
- Fixed incorrect version number.

# [2.1.0] Released on 2021-06-10

#### Added
- Added new support for trial-level answer scoring and performance bonuses, 
  via the `Trial.score_answer` and `Trial.compute_bonus` methods.
- Added `fade_out` option to `AudioPrompt`.

#### Fixed
- Improved robustness of browser-based regression tests.
- Fixed incorrect performance bonus assignment for trial makers initialized with `check_performance_every_trial = True`. 
- Various bugfixes in audio-visual playback/recording interfaces.
- Reverted the new language config.txt parameter, which was causing problems in various situations.
  This functionality will be reinstated in the upcoming Dallinger release.

# [2.0.0] Released on 2021-05-31

#### Added
- Added support for video imitation chains and camera/screen record trials.
- Added a new system for organizing the timing of front-end events.
The API for some `Prompt` and `Control` elements has changed somewhat as a result.
- Added `ProgressDisplay` functionality, which visualizes the  current progress in the trial with text messages and/or
progress bars. 
- Added `controls`, `muted`, and `hide_when_finished` arguments to `VideoPrompt`. 
- PsyNet now requires a `language` argument in config.txt.
- New function: `psynet.utils.get_language`, which returns the language
specified in config.txt.
- Added the ability to parallelize stimulus generation in `AudioGibbs` experiments.
- Added `current_module` to a participant's export data.
- Allow for arbitrary number of audio record channels in `VideoRecordControl`.
- Update Dallinger to v7.4.0.

#### Renamed
- Changed several methods from English to US spelling: `synthesise_target` (now `synthesize_target`), 
`summarise_trial` (now `summarize_trial`), `analyse_trial` (now `analyze_trial`), 
and all prompts and pre-screening tasks involving `colour` (now `color`).
- The output format for `TimedPushButtonControl` has now changed to use 
camel case consistently, e.g. writing `buttonId` instead of `button_id`.
This reflects the camel case formatting conventions of the trial
scheduler and the JS front-end.
- Renamed `REPPMarkersCheck` -> `REPPMarkersTest`.
- Renamed `AttentionCheck` -> `AttentionTest`.
- Renamed `HeadphoneCheck` -> `HeadphoneTest`.
- Renamed `active_balancing_across_chains` -> `balance_across_chains`.
- Renamed `NonAdaptive` -> `Static`.

#### Fixed
- make `play_window` work in `VideoPrompt`.
- Add `try`/`except` blocks in case of an `SMTPAuthenticationError`/`Exception` when calling `admin_notifier()`.
- Make `switch` work when a `TrialMaker` is given as a branch.
- Add `max_wait_time` and `max_loop_time` to `wait_while` and `while_loop`,  resp., to prevent participants from waiting forever.

#### Changed
- PsyNet now forces `disable_when_duration_exceeded = False` in `config.txt`.
This is done to avoid a rare bug where recruitment would be shut down erroneously in long-running experiments.
- `psynet debug` now warns the user if the app title is too long.
- Allow varying numbers of arguments in function argument of `StartSwitch`.

#### BREAKING CHANGES
- Required `language` argument in config.txt.
- Required `disable_when_duration_exceeded = False` argument in config.txt
- Various renamings, see section 'Renamed' above.


# [1.14.0] Released on 2021-05-17

#### Added
- It is now possible to use `save_answer` to specify a participant variable
in which the answer should be saved:

```python
from psynet.modular_page import ModularPage, Prompt, NumberControl

ModularPage(
    "weight",
    Prompt("What is your weight in kg?"),
    NumberControl(),
    time_estimate=5,
    save_answer="weight",
)
```

The resulting answer can then be accessed, in this case, by `participant.var.weight`.

- Implement consent pages as `Module`s to be added to an experiment `Timeline` (CAPRecruiterStandardConsent, CAPRecruiterAudiovisualConsent, MTurkStandardConsent, MTurkAudiovisualConsent, PrincetonConsent).

#### Changed
- Migrate background tasks to Dallinger's new `scheduled_task` API.
This means that the tasks now run on the clock dyno,
and are now robust to dyno restarts, app crashes etc.
- Apply DRY principle to demo directories (delete redundant error.html and layout.html files).
- Change the way experiment variables are set. For details on this important change, see the documentation at https://computational-audition-lab.gitlab.io/psynet/low_level/Experiment.html
- PsyNet now uses the `experiment_routes` and `dashboard_tab` functionality 
implemented in Dallinger v7.3.0.

#### Fixed
- Fix bug in static experiments related to SQLAlchemy.
- Prevent multiple instances of `check_database` from running simultaneously.

# [1.13.1] Released on 2021-05-05

#### Fixed
- Fix name attribute default value for RadioButtonControl, DropdownControl, and CheckboxControl
- Fix some deprecation warnings in tests
- Update black, isort, and flake8 versions in pre-commit hook config
- Update google chrome and chromedriver to v90.x in .gitlab-ci.yml
- Implement missing notify_duration_exceeded method for CAPRecruiter
- Update Dallinger to v7.2.1

# [1.13.0] Released on 2021-04-15

#### Added
- Video and screen recording
- Unity integration including a WebGL demo.
- Filter options for customising stimulus, stimulus version, and network selection.
- Integration of external recruiter with new CapRecruiter classes.
- Add `auto_advance` option to `AudioRecordControl`. 

#### Fixed
- Update for compatibility with SQLAlchemy v1.4.

#### Updated
- Pin to Dallinger v7.2.0
- Replace deprecated `Page` classes with `ModularPage` class.


# [1.12.0] Released on 2021-02-22

#### Added
- Enforce standard Python code style with `"black" <https://black.readthedocs.io/en/stable/>`__ and `"isort" <https://github.com/pycqa/isort/>`__.
- Enforce Python code style consistency with `"flake8" <https://flake8.pycqa.org>`__.
- Added a new section 'INSTALLATION' to the documentation page with installation instructions for *macOS* and *Ubuntu/GNU Linux*, restructured low-level documentation section.

#### Changed
- Revert recode_wav function to an older, non scipy-dependent version.

#### Updated
- Updated Google Chrome and Chromedriver versions to 88.x in `.gitlab-ci.yml`.
- Updated Python to version 3.9 and Dallinger to version 7.0.0. in `.gitlab-ci.yml`.


# [1.11.1] Released on 2021-02-19

#### Fixed

- Fix export command by loading config.
- Remove quotes from PushButton HTML id.
- Use Dallinger v7.0.0 in gitlab-ci.
- Fix minor spelling mistake.


# [1.11.0] Released on 2021-02-13

#### Added
- Added `NumberControl`, `SliderControl`, `AudioSliderControl` controls.
- Added new `directional` attribute to `Slider`.
- Added optional reset button to `CheckboxControl` and `RadioButtonControl`.
- Added new pre-screenings `AttentionTest`, `LanguageVocabularyTest`, `LexTaleTest`, `REPPMarkersTest`, `REPPTappingCalibration`, `REPPVolumeCalibrationMarkers`, and `REPPVolumeCalibrationMusic`.
- Added demos for new pre-screenings.
- Added favicon.ico.

#### Fixed
- Fixed `visualize_response` methods for `checkboxes`, `dropdown`, `radiobuttons`, and `push_buttons` macros.
- Fixed erroneous display of reverse slider due to changes in Bootstrap 4.
- Fixed compatibility with new Dallinger route registration.

#### Deprecated
- Deprecated `NAFCPage`, `TextInputPage`, `SliderPage`, `AudioSliderPage`, and `NumberInputPage` and refactored them into `ModularPage`s using controls.

#### Removed
- Deleted obsolete `psychTestR` directory.


# [1.10.1] - Released on 2021-02-11

#### Fixed
-  Fixed compatibility with new Dallinger route registration.


# [1.10.0] Released on 2020-12-21

#### Added

- Demographic questionnaires (`general`, `GMSI`, `PEI`).
- Improved visual feedback to `TimedPushButtonControl`.


# [1.9.1] - Released on 2020-12-15

#### Fixed

- Fix bug in `active_balancing_within_participants`.


# [1.9.0] Released on 2020-12-15

#### Added

- Added a new ``Trial`` attribute called ``accumulate_answers``.
If True, then the answers to all pages in the trial are accumulated
in a single list, as opposed to solely retaining the final answer
as was traditional.
- Improved JS event logging, with events saved in the `event_log` portion of `Response.metadata`.
- New `Control` class, `TimedPushButtonControl`.
- Added a new `play_window` argument for `AudioControl`.

#### Changed

- Renamed ``reactive_seq`` to ``multi_page_maker``.
- ``show_trial`` now supports returning variable numbers of pages.
- Moved `demos` directory to project root.

#### Fixed

- Fixed audio record status text.
- Fixed bug in ``get_participant_group``.


# [1.8.1] Released on 2020-12-11

- Fix regression where across-participant chain experiments fail unless the networks
used participant groups.


# [1.8.0] Released on 2020-12-07

#### Added
- Participant groups can now be set directly via the participant object, writing
  for example ``participant.set_participant_group("my_trial_maker", self.answer)``.
- Chain networks now support participant groups. These are by default read from the
  network's ``definition`` slot, otherwise they can be set by overriding
  ``choose_participant_group``.

#### Changed
- Update IP address treatment (closes CAP-562).
- Update experiment network `__json__` method to improve dashboard display.

#### Fixed
- Fix problem where wrong assignment_x `super` functions are being called.
- Fix bug in `fail_participant_trials`.


## [1.7.1] Released on 2020-12-01

- Fix regression in ColorVocabulary Test.

## [1.7.0] Released on 2020-11-30

#### Added
- Stimulus media extension to allow multiple files.
- New OptionControl class with subclasses: CheckboxControl, DropdownControl, RadiobuttonControl, and PushButtonControl.
- New Canvas drawing module and demo 'graphics' based on Raphaël vector graphics library.
- Ability to disable bonus display by setting `show_bonus = False` in the Experiment class.

#### Changes
- Optimization of 'estimated_max_bonus' function.
- Refactor ad and consent pages using new default templates.

#### Fixed
- Register pre-deployment routines.
- Missing role attribute for experiment_network in dashboard.
- Make recode_wav compatible with 64-bit audio files.


## [1.6.1] Released on 2020-11-16

#### Fixed
- Error when using psynet debug/sandbox/deploy


## [1.6.0] Released on 2020-11-12

#### Added
- Command-line functions ``psynet debug``, ``psynet sandbox``, ``psynet deploy``.
- ``PreDeployRoutine`` for inclusion into an experiment timeline.
- Limits for participant and experiment payments by introducing ``max_participant_payment`` and ``soft_max_experiment_payment`` including a visualisation in the dashboard and sending out notification emails.
- `psynet estimate` command for estimating a participant's maximum bonus and time to complete the experiment.
- `client_ip_address` attribute to `Participant`.
- Reorganisation of documentation menu, incl. new menu items `Experimenter documentation` and `Developer documentation`.
- Documentation for creating deploy tokens for custom packages and a deploy token for deployment of the ``psynet`` package.
- Ubuntu 20.04 installation documentation (``INSTALL_UBUNTU.md``)


## [1.5.1] Released on 2020-10-14

#### Changes

- Improve data export directory structure


## [1.5.0] Released on 2020-10-13

#### Added

- Add a new tab to the dashboard in order to monitor the progress been made in the individual modules included in a timeline and to provide additional information about a module in a details box and tooltip.
- Improve upload of audio recordings to S3 by auto-triggering the upload right after the end of recording.
- Add new export command for saving experiment data in JSON and CSV format, and as the ZIP-file generated by the Dallinger export command.
- Document existing pre-screening tasks and write a tutorial
- Update deployment documentation

#### Changes

- Move pre-screening tasks into new prescreen module.
- Attempt to fix networks not growing after async post trial
- Bugfix: Enable vertical arrangement of buttons in NAFCControl


## [1.4.2]

- Fixing recruitment bug in chain experiments.


## [1.4.0]

- Extending extra_vars as displayed in the dashboard.


## [1.3.0]

- Added video visualisation.


## [1.2.1]

- Bugfix, now `reverse_scale` works in slider pages.


## [1.2.0]

- Introducing aggregated MCMCP.


## [1.0.0]

- Added regression tests.
- Upgraded to Bootstrap 4 and improved UI elements.
