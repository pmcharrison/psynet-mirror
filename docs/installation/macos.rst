macOS
=====

The following installation instructions apply to **macOS Monterey (12.1), Big Sur (11.1), and Catalina (10.15)**. They address both experiment authors as well as developers who want to work on PsyNet's source code.

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

.. note::

   If you are installing on Big Sur 11.3 with the M1 chip, please skip below

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

Disable AirPlay
~~~~~~~~~~~~~~~

MacOS Monterey introduces 'AirPlay Receiver' functionality that clashes with the default ports used by Dallinger and PsyNet.
You should disable this functionality before proceeding. To achieve this, go to System Preferences, then Sharing,
and then untick the box labeled 'Airplay Receiver'.

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
   pip3 install --editable .

Legacy instructions for Big Sur 11.3/M1
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Originally when MacOS Big Sur came out, we experienced issues compiling some of PsyNet's dependencies.
We found that we could resolve these issues by moving to the virtual environment manager `conda`.
This fix no longer seems to be necessary, but for posterity we give our original instructions below,
in case they are still useful to some people. By default, though, you should skip this section.

In order to have PsyNet work with Big Sur 11.3 macOS with the M1 chip, we advise you use `conda` to download, install, and manage packages within your virtual environment. You can obtain this software by downloading `Miniconda <https://docs.conda.io/en/latest/miniconda.html>`_ . You could also accomplish this with `Anaconda <https://www.anaconda.com/>`_, but this will download about 5 GB worth of software that is not needed to install PsyNet. Once you have installed Miniconda, you can then type the following commands into your Terminal:

.. code-block:: bash

   cd ~
   git clone git@gitlab.com:computational-audition-lab/psynet
   cd psynet
   conda create --name psynet python=3.10 # creates a virtual environment called psynet, respond yes to prompt
   conda activate psynet
   pip3 install --editable .
   conda install psycopg2 # needs to be installed , respond yes to prompt

Note that if you close your Terminal, you will need to ensure that you type `conda activate psynet` everytime you want to work on PsyNet. You can return to your base environment with `conda deactivate` while in the virtual environment.

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
   wget https://chromedriver.storage.googleapis.com/94.0.4606.41/chromedriver_mac64.zip --directory /tmp
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
