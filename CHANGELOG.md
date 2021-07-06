# CHANGELOG

#### Changed
- Minor improvement to video synchronization.

#### Fixed
- Fixed SQLAlchemy start-up error induced by v2.2.1. 

# [2.2.1] Released on 2021-06-21

#### Fixed
- Fixed bug to make pre-deployment routines work again 

# [2.2.0] Released on 2021-06-16

#### Added
- Add new experiment variable ``hard_max_experiment_payment`` which allows for setting a hard, absolute limit on the amount spent in an experiment. Bonuses are not paid from the point the value is reached and the amount of unpaid bonus is saved in the participant's `unpaid_bonus` variable. Default is $1100.
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
