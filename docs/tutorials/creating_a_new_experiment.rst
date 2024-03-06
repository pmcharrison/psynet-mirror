=========================
Creating a new experiment
=========================

When you decide it's time to implement your own experiment,
we generally recommend that you start your implementation by copying
and pasting a pre-existing experiment.
This can either be a demo from PsyNet's demos directory,
or a code repository for a fully-fledged experiment.

Suppose we've copied the PsyNet demo ``demos/audio``,
pasted it to a new location on our computer,
and named this new directory ``my-audio``.
It's best if you put this somewhere outside your PsyNet package installation directory;
for example, you could put in a new folder called ``~/psynet-experiments``.
The first step is then to open this directory in PyCharm
(click File, Open, then select your project, then click Open).
If asked, click New Window.

You should then see a dialog box titled ``Creating virtual environment``.
The next step depends on whether you are using the Docker mode for running PsyNet,
or whether you are using the Developer (i.e. ``virtualenv``) mode.


Docker mode
-----------

If you are using the Docker mode, click ``Cancel`` and then follow the instructions in ``INSTALL.md``
to set up your project. You can then follow the instructions in ``RUN.md`` to run the experiment.

Developer mode
--------------

If you are using the Developer mode, you will want to use this dialog box to create a virtual environment
for your project. The default name of this virtual environment will be the name of your folder,
that normally works well. The dialog box will have selected a particular version of Python to use for this
virtual environment (e.g. Python 3.11); have a look at this and make sure it's what you were expecting
(we don't want really old versions of Python here because they would be incompatible with PsyNet).
By default, the dialog box will probably have specified ``requirements.txt`` as the source for your
dependencies. Instead, you should replace ``requirements.txt`` with ``constraints.txt``, which
provides a fuller list of the precise packages that your experiment depends on.
When you've finished configuring these elements, press OK.
Assuming you have internet access, PyCharm should then automatically download and install
the experiment dependencies. This might take a few minutes.

When the process is done, you should see ``Python 3.xx (<your-project-name>)`` in the bottom
right corner of your screen.
If you then open a new terminal window in PyCharm, you should see ``(<your-project-name)``
prefixed to the terminal prompt. This indicates that you are in the desired virtual environment.
You should be able to run ``psynet --version`` in this terminal to confirm that you have
successfully installed PsyNet.
You should then be able to run ``psynet debug local`` to launch a local version of your experiment.

If you decide at some point you want to make a fresh virtual environment for a pre-existing project,
you can do this by clicking on the Interpreter button in the bottom right corner of your screen
(which might currently say something like ``Python 3.xx (<your-project-name>)``),
click ``Add New Interpreter``, then click ``Add Local Interpreter``.
Select the ``virtualenv`` option, then press OK.
This will create the new environment, but it won't install any dependencies.
To install the dependencies, you should open a new terminal, verify you are in the correct virtual environment
(by confirming that you see ``(<your-project-name)`` prefixed to the terminal prompt)
then run ``pip3 install -r constraints.txt``.

Updating PsyNet
---------------

If you are working from an old experiment, it might be implemented using an older version of PsyNet.
You can see what version of PsyNet it uses by looking inside ``requirements.txt``
for a number that looks like ``10.1.0``. For example, you might see something like this:

::

    psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.1.0#egg=psynet

It's a good idea to check what the latest released version of PsyNet is.
You can do this by looking at the CHANGELOG on GitLab
(https://gitlab.com/PsyNetDev/PsyNet/-/blob/master/CHANGELOG.md?ref_type=heads).
This CHANGELOG lists the changes that happen with each new version of PsyNet.
You can compare the PsyNet version in your experiment to the latest PsyNet version listed here
to work out how PsyNet has changed in the meantime, and what (if anything) you might need to
change about your experiment in order to make it compatible with the latest PsyNet version.
In general, the rule is that only 'major' version changes should require changes to your experiment.
A major change is signified by the first number in the version tag increasing,
so for example from 10.3.1 to 11.0.0.
If both version tags begin with the same number, then you should probably be fine,
and you can just go ahead and increase the PsyNet version number in ``requirements.txt``.

If you have indeed increased the PsyNet version number, you need to update ``constraints.txt``.
On Docker, this means running:

::

    bash docker/generate-constraints

Without Docker, this means running:

::

    psynet generate-constraints

This command requires internet access and may take a minute or so to run.
Once it is complete, you should be able to run ``psynet debug local`` as before.
