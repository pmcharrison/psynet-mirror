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
