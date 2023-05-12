.. _dependencies:


Dependencies
============

Python packages
^^^^^^^^^^^^^^^

PsyNet experiments can include arbitrary Python packages as dependencies.
Such dependencies should be specified in ``requirements.txt``,
with one line per dependency.

If you specify a package simply as its name,
then the latest version of this package will be pulled from the PyPi repository
when you deploy the experiment.
If running your experiment using the Docker workflow, this package will be automatically
installed when you next run ``bash docker/psynet debug``;
if you are running your experiment in a local virtual environment then you will have
to install that package manually using pip.

::

    librosa
    praat-parselmouth

You can pin a particular package version using ``==`` notation:

::

    librosa==1.0.0

You can specify dependencies on packages hosted on version control systems using the following notation:

::

    dallinger@git+https://github.com/Dallinger/Dallinger.git@98d529e537221bf67bf587c1598578d3ffb7cc3f#egg=dallinger

Here the string after the ``@`` symbol is the commit hash. This could equivalently be a branch name or a tag name.


System dependencies
^^^^^^^^^^^^^^^^^^^

It is also possible to specify arbitrary system dependencies if you are using PsyNet with Docker.
To do this, add a file called ``prepare_docker_image.sh`` to your experiment directory.
This should be a Linux shell script.
You might include something like the following, to install the unzip utility:

::

    apt update
    apt install unzip

.. warning::

    This shell script should not place any files into the experiment directory itself,
    as these files won't be accessible during ``psynet debug local``, which overlays the local machine's
    experiment directory onto the Docker container's experiment directory.
    If you need to store files at this point you can put them elsewhere in the container.
