.. _experiment_directory:

Experiment directory
====================

A PsyNet experiment implementation is defined by a particular *experiment directory*.
This directory contains all the files you need to run your experiment.
When you deploy an experiment, a slimmed down version of this directory is created and uploaded
to a web server.

When you are developing a PsyNet experiment it is good practice to use a *version control system*
for keeping track of changes to your experiment directory.
In particular, we advise that you use *Git* because PsyNet itself uses some Git features
as part of its deployment process. To learn more visit
`Version control with Git <tutorials/version_control_with_git.html>`_.

Your experiment directory contains various important files and directories.
Let's talk through what these different files and directories do.
While reading this document, have a look at the experiment directory from a real
PsyNet experiment, the `Carillon Experiment <https://github.com/pmcharrison/2022-consonance-carillon>`_.

-   ``docker`` contains various scripts for working with Docker. These are used when you run commands
    such as ``bash docker/psynet debug``. Normally you should not edit these files directly,
    but instead use the boilerplate files provided by PsyNet. You can update these files to
    their latest PsyNet versions by running ``psynet update-scripts`` within an experiment directory.

-   ``docs`` contains documentation for your experiment. PsyNet provides boilerplate documentation
    files for running your experiment, which you can update by running ``psynet update-scripts`` within
    an experiment directory. If you like you can also add extra documentation specific to your
    experiment here.

-   ``static`` can be used as a storage place for files that the front-end browser can access directly via HTTP.
    If you wanted to bypass PsyNet's asset management system, you could put individual scripts or media files in here,
    and then access them via ``https://your-experiment-url/static/your-file.png``.
    If you are storing large files you may want instead to use PsyNet's asset management system,
    see `Assets <tutorials/assets>`_ for more details.

-   ``templates`` is used for customising PsyNet’s front-end. It contains
    `Jinja2 templates <https://jinja.palletsprojects.com/en/2.11.x/>`_; Jinja2 is a popular templating library for Python.
    Most experiments do not need to use this folder, but for an example of how to use it, see
    `Writing custom frontends <tutorials/writing_custom_frontends.html>`_.

-   ``.gitignore`` controls which files Git tracks. It takes a standard format that comes from Git;
    you can learn more by Googling ``gitignore``. If a file is included within ``.gitignore``, it will not
    be included in your Git repository and hence won't be visible on (for example) GitHub.
    Importantly, files included in ``gitignore`` are **also** excluded from experiment deployments.
    This means for example that if you specify media files in ``gitignore`` then they won't be uploaded
    to the remote server's experiment directory.
    By default, there are some files/folders that are always excluded from this upload process,
    and this list is hard-coded into Dallinger. Currently it looks like this:

        - ``.git``
        - ``config.txt``
        - ``*.db``
        - ``*.dmg``
        - ``node_modules``
        - ``snapshots``
        - ``data``
        - ``develop``
        - ``server.log``
        - ``__pycache__``

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
