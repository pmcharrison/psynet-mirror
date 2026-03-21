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
The first step is then to open this directory in your IDE.
Click File > Open in your IDE, then select your project folder.
If asked, click New Window.

The next step depends on whether you are using the Docker mode for running PsyNet,
or whether you are using the *virtual environment* mode.

Some demos now keep a deliberately small repository footprint. If the copied demo
doesn't include helper files such as ``Dockerfile``, ``test.py``, or ``config.txt``,
run ``psynet scaffold`` in the project directory to generate the standard PsyNet
boilerplate before continuing.


Docker mode
-----------

If you are using the Docker mode, follow the instructions in ``INSTALL.md``
to set up your project. You can then follow the instructions in ``RUN.md`` to run the experiment.

Virtual environment mode
------------------------

If you are using the *virtual environment* mode, you will need to create a virtual environment
for your project. You can do this by opening a terminal in your IDE and running:

.. code-block:: bash

    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    uv pip install -r constraints.txt

.. note::

    Your IDE will typically detect the virtual environment automatically when you open the project.
    If it doesn't, you may need to manually select the virtual environment's Python interpreter in your IDE's settings.
    In most IDEs, you can do this by looking for an interpreter or Python environment selector (often in the bottom-right corner
    or in settings/preferences), and selecting the Python executable from the ``.venv`` folder you just created.

.. note::

    If you are using PyCharm, when you open a new project you should see a dialog box that says something like
    "File requirements.txt contains project dependencies. Would you like to create a virtual environment using it?".
    In the dependencies field you should see a path ending in requirements.txt. Replace "requirements.txt"
    with "constraints.txt" and then click "OK". PyCharm will then create a virtual environment for you
    and install all the required packages. Note that PyCharm remote debugging is currently not working (as of February 2025).

When the process is done, if you open a new terminal window in your IDE, you should see ``(<your-project-name)``
prefixed to the terminal prompt. This indicates that you are in the desired virtual environment.
You should be able to run ``psynet --version`` in this terminal to confirm that you have
successfully installed PsyNet.
You should then be able to run ``psynet debug local`` to launch a local version of your experiment.

If you decide at some point you want to make a fresh virtual environment for a pre-existing project,
you can do this by creating a new virtual environment using the commands above, then selecting it in your IDE's
interpreter settings. To install the dependencies, open a new terminal, verify you are in the correct virtual environment
(by confirming that you see ``(<your-project-name)`` prefixed to the terminal prompt),
then run ``uv pip install -r constraints.txt``.

Updating PsyNet
---------------

If you are working from an old experiment, it might be implemented using an older version of PsyNet.
You can see what version of PsyNet it uses by looking inside ``requirements.txt``
for a number that looks like ``10.1.0``. For example, you might see something like this:

::

    psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.1.0#egg=psynet

It's a good idea to check what the latest released version of PsyNet is.
You should be able to see this in the top-left corner of the online documentation website.
Alternatively, you can look at the `CHANGELOG on GitLab <https://gitlab.com/PsyNetDev/PsyNet/-/blob/master/CHANGELOG.md?ref_type=heads>`_.
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

.. code:: bash

    psynet generate-constraints

Once it is complete, you should be able to run ``psynet debug local`` as before.

If your project uses a minimal demo layout, you can also regenerate the standard
boilerplate files at any time with:

.. code:: bash

    psynet scaffold
