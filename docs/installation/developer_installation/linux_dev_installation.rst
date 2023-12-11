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
   sudo apt install vim python3.10-dev python3.10-venv python3-pip redis-server git libenchant1c2a postgresql postgresql-contrib libpq-dev unzip

Add your SSH key to GitLab
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to be able to contribute to PsyNet in the future 
you will need to generate an SSH key (if you don't have one already) and upload it to GitLab.

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
The easiest way to do this is via the ``apt install`` command above, for example
``sudo apt install python3.10-dev`` for Python 3.10.

Install Docker and Docker plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   sudo apt install ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg

   echo \
      "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

   sudo apt update
   sudo apt install docker.io docker-compose-plugin docker-buildx-plugin

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

   curl https://cli-assets.heroku.com/install-ubuntu.sh | sh

Install Python virtualenv
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip3 install virtualenv
   pip3 install virtualenvwrapper

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

In case you experience problems setting up the virtual environment:

- Check in which directory virtualenvwrapper.sh is installed. This might be a different directory than '~/.local/bin/'. In that case, adapt the code above to source this file accordingly.
- Check whether the directory where virtualenvwrapper.sh was installed is added to PATH. If not, add the directory to PATH.


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

.. note::
   * Make sure you have added an SSH Public Key under your GitLab profile.
   * Also, make sure you have activated your virtual environment by running `workon psynet`.

.. code-block:: bash

   cd
   git clone https://gitlab.com/PsyNetDev/PsyNet
   cd psynet
   pip install --editable .

Verify successful installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   psynet --version

If you are planning to use PsyNet just to design and run experiments,
you are now done with the installation.

Additional developer installation steps
---------------------------------------

If you are planning to contribute to PsyNet's source code,
please continue with the remaining installation steps below.

Install ChromeDriver
~~~~~~~~~~~~~~~~~~~~

Needed for running the Selenium tests with headless Chrome.

.. code-block:: bash

   wget https://chromedriver.storage.googleapis.com/109.0.5414.74/chromedriver_linux64.zip --directory /tmp
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
