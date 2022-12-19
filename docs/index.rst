About
=====

PsyNet is a new platform for running advanced behavioral experiments
ranging from adaptive psychophysics to simulated cultural evolution.
Its goal is to enable researchers to implement and deploy experiments as efficiently as possible,
while placing minimal constraints on the complexity of the experiment design.

This website contains a variety of resources to help you learn more about PsyNet.
Some particularly useful resources are highlighted below,
but see the sidebar for a full list.

- :ref:`Use cases <Use_cases>`: Learn about the use cases for which PsyNet is optimized.

- :ref:`Software stack <Software_stack>`: Learn about the open-source software that underpins PsyNet.

- :ref:`History <history>`: Read about the origins of PsyNet.

- :ref:`Example implementations <example_implementations>`: See code repositories for real-world PsyNet experiments.

- :ref:`Learning PsyNet <learning_psynet>`: Get advice on learning PsyNet.

- `GitLab repository <https://gitlab.com/PsyNetDev/PsyNet>`_: Explore PsyNet's source code.


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Introduction

   self
   introduction/team
   introduction/about
   introduction/applications
   introduction/history
   introduction/how_to_use
   introduction/example_implementations
   introduction/learning_psynet
   introduction/command_line
   introduction/demo

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
   :hidden:
   :caption: Specific implementations
   :glob:

   implementations/*

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Developer documentation
   :glob:

   developer/working_with_git
   developer/basic_workflow
   developer/prescreening_tasks
   developer/updating_documentation
   developer/releasing_new_versions

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
