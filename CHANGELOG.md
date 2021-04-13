# Changelog

# [1.13.0] Unreleased

#### Added
- Add `auto_advance` option to `AudioRecordControl`. 
- Integration of external recruiter with new CapRecruiter classes.
- Filter options for customising stimulus, stimulus version, and network selection.
- Unity integration including a WebGL demo.

#### Updated
- Update for compatibility with SQLAlchemy v1.4.
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
- Added new pre-screenings `AttentionCheck`, `LanguageVocabularyTest`, `LexTaleTest`, `REPPMarkersCheck`, `REPPTappingCalibration`, `REPPVolumeCalibrationMarkers`, and `REPPVolumeCalibrationMusic`.
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
