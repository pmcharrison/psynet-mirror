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


Dallinger
---------

Install Dallinger
~~~~~~~~~~~~~~~~~

.. note::
   Make sure you have activated your virtual environment by running `workon psynet`.

Go to https://github.com/Dallinger/Dallinger/releases and make a note of the latest
released version of Dallinger. In the example below we imagine that this version is
9.10.0; you should replace 9.10.0 with the version number of the latest release.

.. code-block:: bash

   cd
   git clone https://github.com/Dallinger/Dallinger
   cd Dallinger
   git checkout v9.10.0
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
   * Make sure you have added an SSH Public Key under your GitLab profile.
   * Also, make sure you have activated your virtual environment by running `workon psynet`.

.. code-block:: bash

   cd
   git clone https://gitlab.com/PsyNetDev/PsyNet
   cd PsyNet

By default Git will check out the latest version of the master branch.
This is good if you are actively contributing code to PsyNet, but if you are instead just
designing and deploying experiments you probably want to check out the latest release of PsyNet instead.
To check out the latest PsyNet release, go to PsyNet's
`release page <https://gitlab.com/PsyNetDev/PsyNet/-/releases>`_
and make a note of the latest release number.
Suppose this number is ``10.4.1``; you can check out this version by writing ``git checkout v10.4.1``.

Finally, we can install PsyNet with the following:

.. code-block:: bash

    pip3 install --editable .

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

Add your SSH key to GitLab
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you don't yet have a GitLab user account, please create one via the GitLab website.
You need to generate an SSH key (if you don't have one already) and upload it to GitLab.

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

Install ChromeDriver
~~~~~~~~~~~~~~~~~~~~

Needed for running the Selenium tests with headless Chrome.

.. code-block:: bash

   wget https://chromedriver.storage.googleapis.com/109.0.5414.74/chromedriver_linux64.zip --directory /tmp
   sudo unzip /tmp/chromedriver_linux64.zip chromedriver -d /usr/local/bin/

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
