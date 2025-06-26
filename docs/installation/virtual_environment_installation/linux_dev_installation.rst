The following installation instructions are tested with **Ubuntu 22.04 LTS** and **Ubuntu 24.04 LTS**.
They address both experiment authors as well as developers who want to work on PsyNet's source code.

One-time setup
--------------

The following steps need to be performed each time you setup a new computer
to run PsyNet experiments.

Check Linux version
~~~~~~~~~~~~~~~~~~~

You may wish to check that you have an up-to-date version of Linux before proceeding.

Update and install required system packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ubuntu 22.04 LTS
################

.. code-block:: bash

   sudo apt update
   sudo apt upgrade
   sudo apt install vim python3.11-dev python3.11-venv python3-pip redis-server git libenchant-2-2 postgresql postgresql-contrib libpq-dev unzip

Ubuntu 24.04 LTS
################

.. code-block:: bash

   sudo apt update
   sudo apt upgrade
   sudo apt install vim python3.12-dev python3.12-venv python3-pip redis-server git libenchant-2-2 postgresql postgresql-contrib libpq-dev unzip

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
``sudo apt install python3.11-dev`` for Python 3.11.

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


.. include:: ../download_psynet.rst

.. include:: note_about_virtual_environments.rst

If you are interested in contributing to PsyNet, you should also complete
the :ref:`additional_developer_installation`.


Setting up a new project
------------------------

The following steps need to be performed each time you start a new project.

.. include:: ../identifying_a_project.rst

.. include:: opening_a_project_in_a_virtual_environment.rst
