PsyNet Documentation
====================

PsyNet is a powerful new Python package for designing and running the next generation of online behavioural experiments.
It streamlines the development of highly complex experiment paradigms, ranging from simulated cultural evolution to
perceptual prior estimation to adaptive psychophysical experiments. Once an experiment is implemented, it can be
deployed with a single terminal command, which looks after server provisioning, participant recruitment, data-quality
monitoring, and participant payment. Researchers using PsyNet can enjoy a paradigm shift in productivity, running many
high-powered variants of the same experiment in the time it would ordinarily take to run an experiment once.

To try some real-world PsyNet experiments for yourself, visit the following repositories:

- `Consonance profiles for carillon bells <https://github.com/pmcharrison/2022-consonance-carillon>`_
- `Emotional connotations of musical scales <https://github.com/pmcharrison/2022-musical-scales>`_
- `Vocal pitch matching in musical chords <https://github.com/pmcharrison/2022-vertical-processing-test>`_

To get a broader overview of the kinds of experiments you can implemented in PsyNet,
follow this link.

To get an overview of how you can start learning PsyNet,
follow this link.

For a full table of contents of this documentation website, see below:

Table of contents
-----------------

.. toctree::
   :maxdepth: 1
   :caption: Introduction

   introduction/about
   introduction/how_to_use
   introduction/command_line
   introduction/demo

.. toctree::
   :maxdepth: 2
   :caption: Installation

   installation/docker
   installation/macos
   installation/linux

.. toctree::
   :maxdepth: 2
   :caption: Experimenter documentation
   :glob:

   experimenter/basic_usage
   experimenter/timeline
   experimenter/trial_overview
   experimenter/ad_page
   experimenter/modular_page
   experimenter/graphics
   experimenter/unity_page
   experimenter/pre_deploy_routines
   experimenter/payment_limits
   experimenter/deploy_tokens

.. toctree::
   :maxdepth: 2
   :caption: Specific implementations
   :glob:

   implementations/*

.. toctree::
   :maxdepth: 2
   :caption: Developer documentation
   :glob:

   developer/working_with_git
   developer/basic_workflow
   developer/prescreening_tasks
   developer/updating_documentation
   developer/releasing_new_versions

.. toctree::
   :maxdepth: 2
   :caption: Low-level documentation
   :glob:

   low_level/demography
   low_level/Experiment
   low_level/Participant
   low_level/prescreen
   low_level/timeline
   low_level/trial
   low_level/VarStore
