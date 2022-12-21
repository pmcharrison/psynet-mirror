Overview
========

.. warning::
    At the time of writing (December 2022) PsyNet is under heavy development as we prepare
    for an official release in 2023. Most of its features are ready, but some important
    details are still undocumented or unfinished. We recommend contacting the PsyNet developers
    for advice before starting to adopt PsyNet for your own research projects.

PsyNet is a new platform for running advanced behavioral experiments
ranging from adaptive psychophysics to simulated cultural evolution.
Its goal is to enable researchers to implement and deploy experiments as efficiently as possible,
while placing minimal constraints on the complexity of the experiment design.

This website contains a variety of resources to help you learn more about PsyNet.
Some particularly useful resources are highlighted below,
but see the sidebar for a full list.

- :ref:`When to use PsyNet? <applications>`: Learn about the use cases for which PsyNet is optimized.

- :ref:`Demos <demos_introduction>`: Learn about the use cases for which PsyNet is optimized.

- :ref:`Example experiments <example_experiments_introduction>`: See code repositories for real-world PsyNet experiments.

- :ref:`History <history>`: Read about the origins of PsyNet.

- `GitLab repository <https://gitlab.com/PsyNetDev/PsyNet>`_: Explore PsyNet's source code.


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Introduction

   self
   introduction/applications
   introduction/history
   introduction/example_implementations
   introduction/docker
   introduction/learning_psynet
   introduction/team

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Installation

   installation/windows_installation
   installation/unix_installation

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Demos

   demos/introduction
   demos/hello_world
   demos/timeline
   demos/survey_js
   demos/trial
   demos/trial_2

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Example experiments

   example_experiments/carillon
   example_experiments/scales
   example_experiments/pitch-matching

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation

   installation/docker
   installation/macos
   installation/linux

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Experimenter documentation
   :glob:

   experimenter/basic_usage
   experimenter/command_line
   experimenter/timeline
   experimenter/trial_overview
   experimenter/ad_page
   experimenter/modular_page
   experimenter/graphics
   experimenter/unity_integration
   experimenter/writing_custom_frontends
   experimenter/event_management
   experimenter/communicating_with_backend
   experimenter/payment_limits
   experimenter/deploy_tokens

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Specific implementations
   :glob:

   implementations/*

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Developer documentation
   :glob:

   developer/version_control_with_git
   developer/prescreening_tasks
   developer/updating_documentation
   developer/introduction_to_sql_alchemy

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Low-level documentation
   :glob:

   low_level/demography
   low_level/Experiment
   low_level/Participant
   low_level/prescreen
   low_level/timeline
   low_level/trial
   low_level/VarStore
