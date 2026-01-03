Running PsyNet locally
======================

PsyNet relies on many interconnected services, including PostgreSQL, Redis, and Flask.
To simplify the installation process, we use Dev Containers to automatically provision
these services on your local machine.

.. note::

    See the :ref:`legacy_installation` section for details on alternative installation methods.


Install Google Chrome
---------------------

PsyNet currently only supports Google Chrome.
You can download Google Chrome for free from the following link: https://www.google.com/chrome/.

Install Docker Desktop
----------------------

Docker is a virtualization platform used for running software in a platform-independent way.
It's required for running Dev Containers.

.. include:: ../installation/legacy_installation/docker_installation/docker_desktop_installation.rst

Install an IDE
--------------

We recommend using Visual Studio Code (VSCode) as your IDE for working with PsyNet.
This means that you can use our provided configuration files to automatically configure your IDE,
to work with PsyNet.
You can download VSCode for free from the following link: https://code.visualstudio.com/.

You might also consider using Cursor, which is an AI-enhanced fork of VSCode.
Cursor is very helpful at explaining how to use PsyNet features.
You can download Cursor for free from the following link: https://www.cursor.com/.

Download PsyNet
---------------

Download the PsyNet repository using one of the following methods:

If you have Git installed, you can clone the PsyNet repository to your current directory
with the following command:

.. code-block:: bash

    git clone https://gitlab.com/PsyNetDev/PsyNet

Alternatively, if you don't have Git installed, you can navigate to PsyNet's GitLab page,
click the 'Code' button, and select 'Download ZIP'.
Once the ZIP file has downloaded, unzip it to your desired location.

Open the PsyNet repository
--------------------------

Now open the repository in your IDE ('File' > 'Open Folder' in VSCode/Cursor).

Launch a Dev Container
----------------------

You should now see a prompt to launch a Dev Container.

.. image:: ../getting_started/images/open-devcontainer.png
    :alt: Screenshot showing how to open a Dev Container in VSCode or Cursor.
    :class: bordered
    :align: center
    :width: 400px

Before proceeding to the next step, wait until the automatic configuration scripts have stopped running
(it should take 30-60 seconds).

Launch a PsyNet demo
--------------------

Once the Dev Container is running, open a terminal window.
In VSCode/Cursor, you can do this by clicking the 'Terminal' button:

.. image:: ../getting_started/images/terminal-button.png
    :alt: Screenshot showing how to open a terminal window in VSCode or Cursor.
    :class: bordered
    :align: center
    :width: 100px

You should see a terminal prompt like this:

.. image:: ../getting_started/images/terminal-prompt.png
    :alt: Screenshot showing a terminal prompt in VSCode or Cursor.
    :class: bordered
    :align: center
    :width: 400px

Now navigate to a PsyNet demo.
You can see the available demos in the file explorer by navigating to the 'demos' directory.
The following code navigates to the 'timeline' demo:

.. code-block:: bash

    cd demos/timeline

Now you can launch the demo using the following command:

.. code-block:: bash

    psynet debug local

You will need to wait 10 seconds or so for the demo to start.
You may see one or more pop-ups asking whether you want to open an external website;
you should say Yes to these.

If everything works properly, you should see two web pages.
One is a participant interface, looking something like this:

.. image:: ../getting_started/images/participant-interface.png
    :alt: Screenshot showing a participant interface in a PsyNet demo.
    :class: bordered
    :align: center
    :width: 600px

The other is an admin interface, looking something like this:

.. image:: ../getting_started/images/admin-interface.png
    :alt: Screenshot showing an admin interface in a PsyNet demo.
    :class: bordered
    :align: center
    :width: 600px

You can now interact with the demo as if you were a participant.
If you want to start a second participant session, you can do this via the admin interface,
clicking the 'New participant' button on the 'Development' tab.

You can also use the admin interface to view the data collected from the participants.
Try taking a few pages of the experiment, then refresh the admin interface,
then click 'Database', and explore the available data types.

Create your own experiment
--------------------------

The recommended way to start developing your own experiments is to start by copying
an existing PsyNet demo. Have a look through the demos directory to see what might be a good starting point.

Once you've chosen your demo, copy it somewhere else on your computer.
For example, you might want to create a directory in your home directory called 'psynet-experiments',
and copy the demo into this directory.

Now, you want to open a new Dev Container for this new experiment,
following the same process as before:

1. Open the new experiment directory in your IDE
2. Follow the prompt to launch a Dev Container
3. Wait until the automatic configuration scripts have stopped running
4. You can then launch the experiment by running `psynet debug local` in the terminal

This works because each demo directory contains its own ``Dockerfile`` and ``.devcontainer`` directory,
which is used to define the Dev Container environment.

You can now start modifying the experiment to your liking.
Try some simple modifications to begin with, for example changing the text of the questions.
If you're feeling confident, you can try some more complex modifications.
For ideas, you can browse the other demos, or browse the PsyNet documentation,
or ask Cursor to help you (but encourage it to look at the PsyNet source code rather than just guessing)

Simple modifications, such as changing text, can be done without restarting the experiment.
Simply edit the code in your IDE, save the file, and refresh the browser.
More complex modifications, such as changing the stimuli, will require you to restart the experiment.
To do this, you will need to stop the experiment by pressing Ctrl+C in the terminal,
then restart it by running ``psynet debug local`` again.

