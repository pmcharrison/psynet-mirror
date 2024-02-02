Installing PsyNet via virtualenv (macOS)
========================================

One-time setup
--------------

The following steps need to performed each time you setup a new computer
to run PsyNet experiments.

Check MacOS version
~~~~~~~~~~~~~~~~~~~

We recommend that you update MacOS to the latest version before proceeding.

Install Python
~~~~~~~~~~~~~~

PsyNet requires a recent version of Python 3. To check the minimum and recommended versions of Python,
look at PsyNet's
`pyproject.toml <https://gitlab.com/PsyNetDev/PsyNet/-/blob/master/pyproject.toml?ref_type=heads>`_ file,
specifically at the line beginning with ``requires-python``.
To see the current version of Python 3 on your system, enter ``python3 --version`` in your terminal.
If your current version is lower than the minimum version, you should update your Python
to the recommended version.
We recommend doing this by going to the `Python website <https://www.python.org/downloads/>`_,
and downloading the installer corresponding to the latest patch of the recommended version.
If the recommended version is 3.11, this means searching for Python version 3.11.x where
'x' is as high as possible.
At the time of writing this installer can be found by looking under the section
'Looking for a specific release?', clicking the desired Python version, then clicking
'macOS 64-bit universal2 installer'.

One installation is complete, try ``python3 --version`` again to ensure
that the correct version is found. To install old versions you might need to run ``brew uninstall python3``,
or go to the Applications folder and delete the appropriate version of Python.

Install Homebrew
~~~~~~~~~~~~~~~~

.. code-block:: bash

   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

Install Google Chrome
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   brew install --cask google-chrome

Install and setup PostgreSQL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   brew install postgresql@14
   brew services start postgresql@14
   createuser -P dallinger --createdb

When prompted, enter the follwing password: *dallinger*

.. code-block:: bash

   createdb -O dallinger dallinger
   createdb -O dallinger dallinger-import

   brew services restart postgresql@14

Install Heroku
~~~~~~~~~~~~~~

.. code-block:: bash

   brew install heroku/brew/heroku

Install Redis
~~~~~~~~~~~~~

.. code-block:: bash

   brew install redis
   brew services start redis

Setup Git
~~~~~~~~~

If you don't have Git already, install it with the following commands,
inserting your name and email address as appropriate.

.. code-block:: bash

   brew install git
   git config --global user.email "you@example.com"
   git config --global user.name "Your Name"

.. include:: install_virtualenv.rst

.. include:: ../download_psynet.rst

Disable AirPlay
~~~~~~~~~~~~~~~

macOS's 'AirPlay Receiver' functionality clashes with the default ports used by Dallinger and PsyNet.
You should disable this functionality before proceeding. To achieve this, go to System Preferences, then Sharing,
and then untick the box labeled 'Airplay Receiver'.

If you are interested in contributing to PsyNet, you should also complete
the :ref:`additional_developer_installation`.


Setting up a new project
------------------------

The following steps need to be performed each time you start a new project.

.. include:: ../identifying_a_project.rst

.. include:: opening_a_project_with_virtualenv.rst
