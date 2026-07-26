.. _experiment_directory:

Experiment directory
====================

A PsyNet experiment implementation is defined by a particular *experiment directory*.
This directory contains all the files you need to run your experiment.
When you deploy an experiment, its deployable files are assembled into the Docker image
that runs on the experiment server.

When you are developing a PsyNet experiment it is good practice to use a *version control system*
for keeping track of changes to your experiment directory.
We recommend *Git*. During the ``deploy.toml`` compatibility prototype, PsyNet
requires an active Git repository because Dallinger compares the policy's
membership with legacy Git-based selection. To learn more visit
`Version control with Git <../tutorials/version_control_with_git.html>`_.
PsyNet records the deployed Git commit and whether the working tree contained
uncommitted changes. For reproducible live deployments, commit your changes
before deploying. A future major Dallinger release is expected to remove Git
from deployment membership after the compatibility period.

.. warning::

   The ``deploy.toml`` compatibility prototype currently requires POSIX
   descriptor-relative filesystem traversal and is not supported on Windows. A
   safe Windows-support carve-out is required before production rollout.
   Policy-free experiments retain Dallinger's existing legacy, cross-platform
   behavior outside this all-migrated PsyNet prototype.

Your experiment directory contains various important files and directories.
Let's talk through what these different files and directories do.
While reading this document, have a look at the experiment directory from a real
PsyNet experiment, the `Carillon Experiment <https://github.com/pmcharrison/2022-consonance-carillon>`_.

-   ``docker`` contains various scripts for a deprecated Docker API. We are considering this in a future version of PsyNet.

-   ``static`` can be used as a storage place for files that the front-end browser can access directly via HTTP.
    Put public, immutable resources such as scripts, images, audio, and video here,
    and then access them via ``https://your-experiment-url/static/your-file.png``.
    These files are baked into the experiment's Docker image. Use PsyNet's asset
    management system instead for generated files, participant recordings, private
    data, or files that need storage-backed caching and export; see
    `Assets <../tutorials/assets.html>`_.

    Dallinger applies an experiment-package size limit, currently 256 MB by default.
    Set the ``EXP_MAX_SIZE_MB`` environment variable when intentionally baking a
    larger static corpus into an image.

-   ``templates`` is used for customising PsyNet’s front-end. It contains
    `Jinja2 templates <https://jinja.palletsprojects.com/en/2.11.x/>`_; Jinja2 is a popular templating library for Python.
    Most experiments do not need to use this folder, but for an example of how to use it, see
    `Writing custom frontends <../tutorials/writing_custom_frontends.html>`_.

-   ``.gitignore`` controls which files Git tracks. It does not directly control
    target deployment selection when ``deploy.toml`` is present, but it still
    defines the legacy selection used by the compatibility comparison.

-   ``deploy.toml`` controls which files enter Dallinger's deployment plan and
    therefore the debug staging directory, Docker build context, or remote
    deployment package. Version 1 selects every regular file below the experiment
    directory except the listed literal, root-relative path prefixes. Git-style
    globs and negation are not supported. Hidden, untracked, and Git-ignored files
    are selected unless explicitly excluded, so review local files carefully and run
    ``dallinger deployment-files check`` when migrating an existing experiment.
    During the compatibility period, this command reports both target-only and
    legacy-only paths; any difference must be reviewed and acknowledged.
    Source ``.dockerignore`` files are not supported with this policy; migrate their
    rules to ``deploy.toml`` and remove them. Experiments without ``deploy.toml``
    retain the legacy Git-based selection behavior during the compatibility period.

-   ``Dockerfile`` is used by Docker to define the experiment's Docker image. Normally you should not edit this file
    directly, but instead use the boilerplate file provided by PsyNet. You can update this file to
    their latest PsyNet versions by running ``psynet update-scripts`` within an experiment directory.

-   ``Dockertag`` determines the name of the Docker image that is built for the present experiment.
    It defaults to the name of the current directory.

-   ``README.md`` is a README file. You should put information about your experiment here for future readers.

-   ``__init__.py`` is created automatically when you deploy the experiment; it tells Python to treat the directory as a
    package. You don’t need to worry about this file in practice.

-   ``carillon_samples.csv`` is specific to the Carillon Experiment implementation, we don't need to worry about it now.

-   ``config.txt`` is a configuration file. It defines various important configuration parameters for when you deploy an
    experiment online.

-   ``constraints.txt`` stores the versions of the different Python packages that will be used when you deploy your
    experiment. It is automatically generated, don’t edit it yourself. **Note**: the role of this file is currently
    unclear for Docker experiments. At the time of writing (April 2023) this file is ignored in Docker deployments,
    but this may change.

-   ``experiment.py`` is a Python file that defines the primary experiment logic.

-   ``instructions.py`` is specific to the Carillon Experiment implementation, we don't need to worry about it now.

-   ``prepare_docker_image.sh`` is an optional file that provides extra setup code that is run when preparing
    the experiment's Docker image. Here we use it to install a particular dependency for stimulus generation.

-   ``pytest.ini`` is a boilerplate PsyNet file, you should not have to edit it yourself.

-   ``questionnaire.py`` is specific to the Carillon Experiment implementation, we don't need to worry about it now.

-   ``requirements.txt`` is where you specify the packages that your experiment will depend on.
    This file should always contain a link to the PsyNet library, for example:

    ::

        psynet@git+https://gitlab.com/psynetdev/psynet@d54c3f7a0afddebe1e53676c47c9a31f9cb9a827#egg=psynet

    This particular example indicates that the experiment should use a particular version of PsyNet from
    GitHub. The version is specified here by the long string that comes after the ``@`` symbol:
    ``d54c3f7a0afddebe1e53676c47c9a31f9cb9a827``.
    This string corresponds to a particular commit hash.
    You can also specify a particular version number here, for example ``10.3.0``.

-   ``server.log`` is an automatically generated log file, don’t worry about it.

-   ``synth.py`` is specific to the Carillon Experiment implementation, we don't need to worry about it now.

-   ``test.py`` is a boilerplate PsyNet file that defines generic tests for the experiment.
    You can run these tests in Docker by running ``docker/run pytest test.py``.
    If you want to customize these tests you should normally override specific methods in the Experiment class,
    for example ``Experiment.test_experiment`` and ``Experiment.test_check_bots``.

    ``volume_calibration.py`` is specific to the Carillon Experiment implementation, we don't need to worry about it now.
