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

- :ref:`Demos <demos_introduction>`: See demos of different PsyNet features.

- :ref:`Example experiments <example_experiments_introduction>`: See code repositories for real-world PsyNet experiments.

- `GitLab repository <https://gitlab.com/PsyNetDev/PsyNet>`_: Explore PsyNet's source code.


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Introduction

   self
   introduction/applications
   introduction/history
   introduction/team

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Architecture

   architecture/dallinger
   architecture/docker
   architecture/web_servers

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
   demos/gibbs
   demos/audio_gibbs
   demos/imitation_chains
   demos/tapping_imitation_chain
   demos/mcmcp


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Example experiments

   example_experiments/introduction
   example_experiments/carillon
   example_experiments/emotions-scales
   example_experiments/pitch-matching

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation (Docker route)

   installation/unix_installation
   installation/windows_installation

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation (legacy route)

   legacy_installation/linux
   legacy_installation/macos

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Tutorials
   :glob:

   tutorials/classes
   tutorials/timeline
   tutorials/assets
   tutorials/command_line
   tutorials/specifying_dependencies
   tutorials/ad_page
   tutorials/modular_page
   tutorials/graphics
   tutorials/demography
   tutorials/prescreening_tasks
   tutorials/pre_deploy_routines
   tutorials/experiment_variables
   tutorials/unity_integration
   tutorials/writing_custom_frontends
   tutorials/event_management
   tutorials/communicating_with_backend
   tutorials/payment_limits
   tutorials/deploy_tokens
   tutorials/introduction_to_sql_alchemy
   tutorials/version_control_with_git
   tutorials/upgrading_to_psynet_10

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Contributing to PsyNet
   :glob:

   developer/prescreening_tasks
   developer/updating_documentation

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: API documentation
   :glob:

   api/overview
   api/demography
   api/Experiment
   api/Participant
   api/prescreen
   api/timeline
   api/trial
   api/VarStore
