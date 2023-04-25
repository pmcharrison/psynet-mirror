Overview
========

.. warning::
    At the time of writing (December 2022) PsyNet is under heavy development as we prepare
    for an official release in 2023. Most of its features are ready, but some important
    details are still undocumented or unfinished. We recommend contacting the PsyNet developers
    for advice before starting to adopt PsyNet for your own research projects.

PsyNet is a new platform for running advanced behavioral experiments
ranging from adaptive psychophysics to simulated cultural evolution.
It builds on the virtual lab framework `Dallinger <https://dallinger.readthedocs.io/en/latest/>`_.
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
   introduction/how_to_learn
   introduction/command_line

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Dependencies

   dependencies/dallinger
   dependencies/docker

.. toctree::
   :hidden:
   :caption: INSTALLATION

   installation/index

.. toctree::
   :maxdepth: 2
   :hidden:

   developer_installation/index

.. toctree::
   :hidden:
   :caption: EXPERIMENT DEVELOPMENT

   experiment_directory
   development_workflow
   troubleshooting
   demos/index

.. toctree::
   :hidden:

   example_experiments/index

.. toctree::
   :hidden:

   tutorials/index

.. toctree::
   :hidden:

   api/index

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: DEPLOYING

   deploy/web_servers
   deploy/aws_server_setup
   deploy/ssh_server
   deploy/heroku_server
   deploy/prolific
   deploy/export
   deploy/troubleshooting

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Contributing to PsyNet
   :glob:

   developer/running_tests
   developer/prescreening_tasks
   developer/updating_documentation

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Dashboards
   :glob:

   dashboards/translation
