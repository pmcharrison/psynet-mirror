Ubuntu/GNU Linux
================

The following installation instructions apply to **Ubuntu 20.04 LTS (Focal Fossa)** only. They address both experiment authors as well as developers who want to work on PsyNet's source code.

.. note::
   You must have set up your GitLab SSH keys already.


Prerequisites
-------------

Update and install required system packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   sudo apt update
   sudo apt upgrade
   sudo apt install vim python3.9-dev python3.9-venv python3-pip redis-server git libenchant1c2a postgresql postgresql-contrib libpq-dev unzip

Install Google Chrome
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
   sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
   sudo apt update
   sudo apt install google-chrome-stable

Setup PostgreSQL
~~~~~~~~~~~~~~~~

.. code-block:: bash

   sudo service postgresql start
   sudo -u postgres -i

.. code-block:: bash

   createuser -P dallinger --createdb

Password: *dallinger*

.. code-block:: bash

   createdb -O dallinger dallinger
   createdb -O dallinger dallinger-import
   exit

.. code-block:: bash

   sudo service postgresql reload

Install heroku client
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   sudo snap install heroku --classic

Install Python virtualenv
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip3 install virtualenv
   pip3 install virtualenvwrapper

Setup virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   export WORKON_HOME=$HOME/.virtualenvs
   mkdir -p $WORKON_HOME
   echo "export VIRTUALENVWRAPPER_PYTHON=$(which python3)" >> ~/.bashrc
   echo "source ~/.local/bin/virtualenvwrapper.sh" >> ~/.bashrc
   export VIRTUALENVWRAPPER_PYTHON=$(which python3)
   source ~/.local/bin/virtualenvwrapper.sh
   mkvirtualenv psynet --python $(which python3.9)

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
   pip install -r dev-requirements.txt
   pip install --editable '.[data]'

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
   pip install --editable .

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

   wget https://chromedriver.storage.googleapis.com/90.0.4430.24/chromedriver_linux64.zip --directory /tmp
   sudo unzip /tmp/chromedriver_linux64.zip chromedriver -d /usr/local/bin/

Install additional Python packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    pip install -e '.[dev]'

Install the Git pre-commit hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the virtual environment still activated:

.. code-block:: bash

   pip install pre-commit

This will install the pre-commit package into the virtual environment. With that in place, each git clone of `psynet` you create will need to have the pre-commit hook installed with:

.. code-block:: bash

   pre-commit install

This will install the pre-commit hooks defined in ``.pre-commit-config.yaml`` to check for `flake8` violations, sort and group ``import`` statements using `isort`, and enforce a standard Python source code format via `black`. You can run the black code formatter and flake8 checks manually at any time by running:

.. code-block:: bash

   pre-commit run --all-files

You may also want to install a black plugin for your own code editor, though this is not strictly necessary, since the pre-commit hook will run black for you on commit.
