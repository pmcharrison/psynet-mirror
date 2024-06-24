.. _development_workflow:

Development workflow
====================

Let's imagine we are working on a particular experiment implementation.
Perhaps we initialized our implementation by copying a demo from the PsyNet ``demos`` directory,
and have been converting the code to our needs.
This tutorial will cover various tips and tricks for making your development process
efficient and effective.


Version control
^^^^^^^^^^^^^^^

It's important to have some system for tracking changes to your code over time.
We recommend using Git alongside some Git host such as GitHub or GitLab.
There are lots of good Git tutorials available online;
see `version control with Git <../tutorials/version_control_with_git.html>`_
for a PsyNet-oriented introduction to Git.


PyCharm as an IDE
^^^^^^^^^^^^^^^^^

Interactive development environments (IDE)
help you to manage and run your source files. We particularly recommend PyCharm Professional,
which integrates well with the development requirements of PsyNet.
It is possible to get free educational licenses for PyCharm Professional,
see online for details.

PsyNet demos come with instructions about how to configure your PyCharm IDE.
The most important steps are (a) opening the experiment directory as a project (File > Open in PyCharm),
and (b) configuring your Python interpreter. The instructions for the latter depend on whether you are using
Docker or not. See ``docs/INSTALL.md`` in your PsyNet demo for these instructions.

Once you've set up your PyCharm interpreter, you will be able to see your experiment's source files
by clicking on the File navigator on the left side of the screen.
You will be able to interact with a bash console by clicking on the ``Terminal`` tab on the bottom of the screen,
and with a Python console by clicking on the ``Python Console`` tab on the bottom of the screen.
When you are writing PsyNet commands, you will probably be interacting directly with the ``Terminal`` tab.
See `Command line <../introduction/command_line.html>`_ for an overview of PsyNet commands.


Local debug mode
^^^^^^^^^^^^^^^^

The most important PsyNet command for local development is the following:

.. code:: bash

    psynet debug local

If you are running PsyNet via Docker, you need to prefix this and all other PsyNet commands
with ``bash docker/``. This means that you actually write this:

.. code:: bash

    bash docker/psynet debug local

The latter executes a bash script that builds a Docker image for your experiment,
creates a Docker container from that image, and executes the PsyNet command within that container.

This ``psynet debug local`` command creates a local development server that you can use
to prototype your experiment. This server recreates all the services (web nodes, worker nodes,
clock nodes, database) that would be running in a real experiment. If you run it via Docker,
then this is all done using the exact same virtualized environments that you would use
for your real experiment. This introduces some setup overhead, as all these environments and
processes need to be spun up, but it means that you have a very good approximation of the
'real' deployment environment right from the beginning, which is very helpful for avoiding
bugs later on.

The local development server should take about 10-15 seconds to spin up.
Once it has spun up, you should see in your console a link to the experiment dashboard.
Open that link in Chrome and you should see the dashboard. On the default dashboard page
you will see a button that allows you to create a new participant session.
Click that link and you can take the experiment.

Though the development server takes a while to spin up, it has the special feature
that you can preview edits to your code without having to restart the server from scratch.
For example, you can change the UI components of a given PsyNet page, save the source file,
then refresh the page in Chrome; the server processes should refresh and you should see
the changes to your page. You can likewise add new components to the timeline, change
code block logic, and so on; changes should be manifested immediately once you refresh
the page.

Certain changes need a full refresh of the development server to propagate. For example,
if you are making changes to assets included in the timeline, you will normally need
to close the debug session and create a new one for those assets to be incorporated
into the experiment. You can close a debug session by entering Ctrl-C into the bash terminal.


Breakpoints
^^^^^^^^^^^

Breakpoints are an essential tool for debugging experiments. They allow you to drop into
the Python environment at a particular point in your code, inspect local variables,
and try executing arbitrary code.

If you are developing your experiment in PyCharm we recommend using the PyCharm debugger.
We need to set this up in a particular way for it to work with PsyNet experiments,
which make heavy use of subprocesses, which cannot easily be accessed using standard
PyCharm breakpoints.

To set up the PyCharm debugger for Psynet, click Run, then Edit Configurations. Click + (Add new configuration), then
click Python debug server.

If you are using Docker, then under Name enter ‘Dockerized Python debug server. Under IDE host name, enter
host.docker.internal. Set Port to 12345.

Alternatively, if you are not using Docker, then under Name enter ‘Python debug server. Under IDE host name, enter
localhost. Set Port to 12345.

If you are not using Docker you will need to install the pydevd_pycharm package. There are instructions for this on the
New Configuration panel; copy those now, and run them in your bash terminal.

Now to insert a breakpoint, select ‘[Dockerized] Python debug server’ from the dropdown in the top right of your screen,
then click the green bug symbol. This will start your debug server running. You will see some instructions printed in
your console that look something like this:

.. code:: bash

    Starting debug server at port 12,345
    Use the following code to connect to the debugger:
    import pydevd_pycharm
    pydevd_pycharm.settrace('host.docker.internal', port=12345, stdoutToServer=True, stderrToServer=True)
    Waiting for process connection…

Copy and paste the two Python lines into the part of your code where you want to have the breakpoint.

.. code:: bash

    import pydevd_pycharm
    pydevd_pycharm.settrace('host.docker.internal', port=12345, stdoutToServer=True, stderrToServer=True)

Now run your PsyNet command as usual:

.. code:: bash

    bash docker/psynet debug local

Once PsyNet hits the breakpoint, your debug console should be activated. You should now be able to access the local
environment and execute arbitrary code.


Debugging tips
^^^^^^^^^^^^^^

Everyone runs into errors and bugs when they are programming. This is part of the normal process.
Your ability to efficiently resolve errors and bugs is an essential part of being an effective programmer.

PsyNet experiments take some care to debug because there are many moving parts. It can be intimidating at
first working out how to resolve problems.

Most errors and bugs have their first symptom in an error message that is printed to your bash console.
This error message will typically contain a traceback that tells you where in the code the error occurred.
Examine this carefully to work out where the error is being flagged. It might be in the code you wrote,
or it might be in the PsyNet library code. If the latter, you may want to find the corresponding part of the
PsyNet source code so you can get a better idea of the logical context of the error.

Often you can learn more about the origin of the error by inserting a breakpoint at the point just before
the error occurs. With this breakpoint, you can explore the local state of the environment, and work
out if a particular variable is taking an unexpected value, or a particular function is returning an unexpected output.

If an error is particularly hard to isolate, one trick is to progressively simplify your implementation to find
a minimal code example that still produces the error. The simpler the implementation, the less there is to understand,
and the clearer the bug will become. A minimal code example can be very good for sharing with others so that
they can help you to understand what's going on. A useful trick here can be to simply 'comment out' bits of your
experiment timeline. There is a useful PyCharm shortcut for this, CMD-/.


Dashboard
^^^^^^^^^

The PsyNet dashboard provides various useful tools for understanding the state of your experiment.
You should explore this as you develop your experiment. In particular the database tab is helpful
for showing you the state of the current database objects; this is complemented by the monitor tab,
which visualizes network structures in the experiment.


Tests
^^^^^

PsyNet experiments now come with built-in tests. These tests help you to validate that your experiment logic
works correctly. They focus on the back-end Python logic, rather than the front-end user interface;
however it is perfectly possible to write your own front-end tests too.

The PsyNet experiment's tests are defined in the experiment directory's ``test.py`` file.
The built-in test simply runs a simulated participant (a 'bot') through your experiment.
The way this works is that each PsyNet page comes with a ``bot_response`` attribute that determines
how the bot responds to the page. Many pages come with default ``bot_response`` attributes;
for example, by default a bot will respond to a multiple-choice page by clicking a random option.
This behavior is fully customizable, and you can pass arbitraily complex functions to this ``bot_response`` attribute.

PsyNet provides several hooks for customizing these built-in experiment tests.
These hooks are accessed by customizing your ``Experiment`` class in ``experiment.py``.

The simplest customization is to change ``Experiment.test_n_bots``, which determines the number of bots that are run through
the experiment. By default this is set to 1.

Another common customization is to override ``Experiment.test_check_bot`` and add additional code that validates
the state of the bot once it has completed the experiment. For example, you might check that it has completed
a certain number of trials, or that a certain participant variable has been set effectievly.

For more complete customization, you can override ``Experiment.test_experiment`` itself, and have complete control
over the initialization of bots and the checking of their status.

To run the experiment's tests, you can enter the following into your bash terminal:

.. code:: bash

    bash docker/run psynet test local

Or without docker:  

.. code:: bash

    psynet test local

The nice thing about running these tests in Docker is that it uses the exact operating system environment
(including Python version and dependencies) that your actual deployed experiment would use.
It's a great way of finding problems.
It's a good habit to run this test as a final check before you deploy your experiment.

.. note::

    You can also run your experiment's tests via PyCharm. 
    However, at the time of writing (June 2024) there is a bug in PyCharm's test result parser
    that causes full tracebacks to be omitted from test results in some cases. 
    To fix this problem we recommend editing your PyCharm's pytest run configurations to include
    the additional argument ``--tb=short``. To do this, click Run > Edit Configurations > 
    Edit configuration templates > Python tests > pytest, and then insert ``--tb=short``
    under Additional Arguments. Then press OK, then remove any existing pytest configurations for your
    current project by pressing the minus symbol in the top left. Future tests should then run 
    automatically using this option.


Local PsyNet and Dallinger installations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Writing PsyNet experiments often involves customizing underlying library code. This is part of the real power of
PsyNet: you can dig as deep as you want into the library classes and functions.

To take advantage of this capacity, you will normally want to have PsyNet (and perhaps also Dallinger)
source code libraries easily available on your computer. The recommended way to do this is to clone their
Git repositories into your home directory. Make sure to preserve the original capitalization of the repository
directory names, for example ``~/PsyNet`` and ``~/Dallinger``.

You can open these libraries in PyCharm by click File > Open and then selecting the folders.
When prompted, select the option to open each project in a new window.
It's a good idea to have the PsyNet project open in a separate window whenever you are developing an experiment.
You can easily jump to particular function definitions by using the full text search (Cmd-Shift-F by default).

Sometimes you will want to trial particular changes to PsyNet or Dallinger library code. This can be useful for
debugging errors that occur within this code, or for proposing new features that you eventually contribute to
PsyNet or Dallinger. In order to test such changes, you need to link your local source libraries to your experiment
implementation. The way you do this depends on whether you are using Docker or not.

If you are using Docker, make sure you have downloaded both PsyNet and Dallinger to the locations specified above.
Then, whenever you are running PsyNet terminal command, insert ``-dev``, producing commands like this:

.. code:: bash

    bash docker/psynet-dev debug local
    bash docker/run-dev pytest test.py

This invokes Docker in the same way as before, but linking your local PsyNet and Dallinger installations.

If you are not using Docker, then the process is instead to navigate to those folders within your local environment,
then run ``pip3 install -e .`` The ``-e`` stands for 'editable'.

.. code:: bash

    cd ~/PsyNet
    pip3 install -e .

    cd ~/Dallinger
    pip3 install -e .
