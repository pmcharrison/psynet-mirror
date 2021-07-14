macOS
=====

The following installation instructions apply to **macOS Big Sur (11.1) and Catalina (10.15)**. They address both experiment authors as well as developers who want to work on PsyNet's source code.

.. note::
   You must have set up your GitLab SSH keys already.


Prerequisites
-------------

Before starting installation make sure you have the latest macOS updates installed. Thereafter follow the step-by-step instructions below.

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

   brew install postgresql
   brew services start postgresql
   createuser -P dallinger --createdb

Password: *dallinger*

.. code-block:: bash

   createdb -O dallinger dallinger
   createdb -O dallinger dallinger-import
   exit

   brew services restart postgresql

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

.. code-block:: bash

   git config --global user.email "you@example.com"
   git config --global user.name "Your Name"

Setup virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip3 install virtualenv
   pip3 install virtualenvwrapper
   export WORKON_HOME=$HOME/.virtualenvs
   mkdir -p $WORKON_HOME
   export VIRTUALENVWRAPPER_PYTHON=$(which python3)
   source $(which virtualenvwrapper.sh)
   mkvirtualenv psynet --python $(which python3)
   echo "export VIRTUALENVWRAPPER_PYTHON=$(which python3)" >> ~/.zshrc
   echo "source $(which virtualenvwrapper.sh)" >> ~/.zshrc

Activate virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   workon psynet


Dallinger
---------

Install Dallinger
~~~~~~~~~~~~~~~~~

In the example below Dallinger is cloned into the user's home directory, but you can choose a different location to put your installation, like e.g. `~/cap`.

.. note::

   Make sure you have activated your virtual environment by running `workon psynet`.

.. code-block:: bash

   cd ~
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

In the example below PsyNet is cloned into the user's home directory, but you can choose a different location to put your installation, like e.g. `~/cap`.

.. note::
   * Make sure you have added an SSH Public Key under your GitLab profile.
   * Also, make sure you have activated your virtual environment by running `workon psynet`.

.. code-block:: bash

   cd ~
   git clone git@gitlab.com:computational-audition-lab/psynet
   cd psynet
   pip3 install -e .

The `-e` flag makes in the last command above makes the `psynet` code editable.

Verify successful installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   psynet --version

As an *experiment author* you are now done with the installation and you can begin building experiments. In this case, move on to :doc:`/experimenter/basic_usage`.


As a *developer* who wants to work on `psynet`'s source code, however, please continue with the remaining installation steps below.

.. note::
   Below instructions apply to *developers only*.

Install ChromeDriver
~~~~~~~~~~~~~~~~~~~~

Needed for running the Selenium tests with headless Chrome.

.. code-block:: bash

   brew install wget
   wget https://chromedriver.storage.googleapis.com/90.0.4430.24/chromedriver_mac64.zip --directory /tmp
   sudo unzip /tmp/chromedriver_mac64.zip chromedriver -d /usr/local/bin/

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
