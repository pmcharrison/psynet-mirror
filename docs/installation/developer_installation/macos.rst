macOS installation
==================

Prerequisites
-------------

We recommend that you update MacOS to the latest version before installing PsyNet.

Add your SSH key to GitLab
~~~~~~~~~~~~~~~~~~~~~~~~~~

To authenticate to PsyNet's GitLab repository you need to create a (free)
GitLab account, generate an SSH key (if you don't have one already),
and upload it to GitLab.

To generate an SSH key:

.. code-block:: bash

   ssh-keygen -b 4096 -t rsa

Press Enter to save the key in the default location,
and Enter again twice to create the key with no passphrase.

Copy the SSH key to the clipboard by running this command:

.. code-block:: bash

   pbcopy < ~/.ssh/id_rsa.pub

Then navigate to `GitLab SSH keys <https://gitlab.com/-/profile/keys>`_,
click 'Add new key', paste the key in the 'Key' box,
remove the Expiration date if you think it's helpful, then click 'Add key'.


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

You only need to do this if you don't have Google Chrome installed already.

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

Setup virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~

You need to use virtual environments to work with PsyNet.
This can be confusing if you haven't used Python virtual environments before.
We strongly recommend you take half an hour at this point to read some online tutorials
about virtual environments and managing them with ``virtualenvwrapper` before continuing.

The following code installs ``virtualenvwrapper``:

.. code-block:: bash

   pip3 install virtualenv
   pip3 install virtualenvwrapper
   export WORKON_HOME=$HOME/.virtualenvs
   mkdir -p $WORKON_HOME
   export VIRTUALENVWRAPPER_PYTHON=$(which python3)
   source $(which virtualenvwrapper.sh)
   echo "export VIRTUALENVWRAPPER_PYTHON=$(which python3)" >> ~/.zshrc
   echo "source $(which virtualenvwrapper.sh)" >> ~/.zshrc

The following code creates a virtual environment called 'psynet' into which we are going to install Psynet.

.. code-block:: bash

   mkvirtualenv psynet --python $(which python3)

This virtual environment will contain your PsyNet installation alongside all the Python dependencies that go
with it. Virtual environments are useful because they allow you to keep control of the precise Python package
versions that are required by particular projects.

Whenever you develop or deploy an experiment using PsyNet (assuming you are not using Docker) you will need to
make sure you are in the appropriate virtual environment. You do this by writing code like the following
in your terminal:

.. code-block:: bash

   workon psynet

where in this case ``psynet`` is the name of the virtual environment.
One workflow is to have just one virtual environment for all of your PsyNet work, called ``psynet`` as above;
another is to create a separate virtual environment for each experiment you are working on.

To delete a pre-existing virtual environment, use the ``rmvirtualenv`` command like this:

.. code-block:: bash

   rmvirtualenv psynet

To make another virtual environment, use the ``mkvirtualenv`` command like this:

.. code-block:: bash

   mkvirtualenv my-experiment --python $(which python3)


Activate virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   workon psynet

Disable AirPlay
~~~~~~~~~~~~~~~

macOS's 'AirPlay Receiver' functionality clashes with the default ports used by Dallinger and PsyNet.
You should disable this functionality before proceeding. To achieve this, go to System Preferences, then Sharing,
and then untick the box labeled 'Airplay Receiver'.

Dallinger
---------

Install Dallinger
~~~~~~~~~~~~~~~~~

.. note::
   Make sure you have activated your virtual environment by running `workon psynet`.

.. code-block:: bash

   cd
   git clone https://github.com/Dallinger/Dallinger
   cd Dallinger
   pip3 install -r dev-requirements.txt
   pip3 install --editable '.[data]'

Verify successful installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   dallinger --version


PsyNet
------

Install PsyNet
~~~~~~~~~~~~~~

.. note::
   * Make sure you have activated your virtual environment by running `workon psynet`.


.. code-block:: bash

   cd
   git clone git@gitlab.com:PsyNetDev/PsyNet
   cd PsyNet

By default Git will check out the latest version of the master branch.
This is good if you are actively contributing code to PsyNet, but if you are instead just
designing and deploying experiments you probably want to check out the latest release of PsyNet instead.
To check out the latest PsyNet release, first go to PsyNet's
`pyproject.toml <https://gitlab.com/PsyNetDev/PsyNet/-/blob/master/pyproject.toml?ref_type=heads>`_ file
and look for the version number specified in the line beginning `version = `.
Suppose this number is `10.4.0`; you can check out this version by writing ``git checkout v10.4.0``.

Finally, we can install PsyNet with the following:

.. code-block:: bash

    pip3 install --editable .

Verify successful installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   psynet --version

If you are planning to use PsyNet just to design and run experiments,
you are now done with the installation.

Opening a project in your IDE
-----------------------------

We recommend using PsyNet with an IDE. In particular we recommend that you use PyCharm Professional,
which has special tools for working with Python and HTML/JS. This is paid software but you can
get free student/educational licenses.

As a first step we recommend opening up PsyNet as a PyCharm project so that you can try out some of the demos.
To do this, go to PyCharm, click File > Open and then open the folder containing your PsyNet installation,
typically ``~/PsyNet``.
You should now configure PyCharm to use the ``psynet`` virtual environment you created earlier.
Ignore any requests that PyCharm makes to create a virtual environment for you, and instead click in the bottom right
corner of the screen where you should see something like 'Python 3.X' or 'No virtual environment'.
Click "Add new interpreter" > "Add local interpreter".
Select "Virtualenv environment", select "Existing", and then select your ``psynet`` virtual environment;
it should look something like ``/Users/your-name/.virtualenvs/psynet/bin/python``.
PyCharm will spend some time processing this selection, but then when you open a new terminal tab it should load 
your virtual environment automatically.


Additional developer installation steps
---------------------------------------

If you are planning to contribute to PsyNet's source code,
please continue with the remaining installation steps below.

Install ChromeDriver
~~~~~~~~~~~~~~~~~~~~

Needed for running the Selenium tests with headless Chrome.

.. code-block:: bash

   brew install chromedriver

By default chromedriver will be blocked by the MacOS security policy.
To unblock it, first try to run it:

.. code-block:: bash

   chromedriver --version

If you see an error message stating that Apple cannot check chromedriver for malicious software,
you can disable it by going to System Settings, Privacy & Security,
then looking for a line that says '"Chromedriver was blocked from use because it is not from an
identified developer"'. Click 'Allow anyway', then try rerunning Chromedriver.

Install additional Python packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    pip3 install -e '.[dev]'

Install the Git pre-commit hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the virtual environment still activated:

.. code-block:: bash

   pip3 install pre-commit

This will install the pre-commit package into the virtual environment. With that in place, each git clone of `psynet` you create will need to have the pre-commit hook installed with:

.. code-block:: bash

   pre-commit install

This will install the pre-commit hooks defined in ``.pre-commit-config.yaml`` to check for `flake8` violations, sort and group ``import`` statements using `isort`, and enforce a standard Python source code format via `black`. You can run the black code formatter and flake8 checks manually at any time by running:

.. code-block:: bash

   pre-commit run --all-files

You may also want to install a black plugin for your own code editor, though this is not strictly necessary, since the pre-commit hook will run black for you on commit.
