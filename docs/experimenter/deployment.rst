=================
Docker deployment
=================

Server setup
------------

This setup only has to be done by the server's administrator once. Also, instructions apply to Ubuntu 20.04 LTS (Focal Fossa) only.

Add new user *cap*
++++++++++++++++++

Login to the remote server. Then, execute

.. code-block:: bash

    sudo adduser cap

Provide a secure password and store it at a save place.


Grant sudo privileges to user *cap*
+++++++++++++++++++++++++++++++++++

.. code-block:: bash

    sudo visudo

and at the end of the file add

.. code-block:: bash

    cap ALL=NOPASSWD: ALL

Save the file and exit the editor.

Disable autostart of Apache webserver
+++++++++++++++++++++++++++++++++++++

.. code-block:: bash

    sudo systemctl disable apache2
    sudo systemctl stop apache2

Install system packages
+++++++++++++++++++++++

.. code-block:: bash

    sudo apt install docker.io python3.9

Setup docker locally
++++++++++++++++++++

.. code-block:: bash

    sudo usermod -aG docker $USER
    newgrp docker

.. code-block:: bash

    sudo systemctl restart docker

Verify docker works
+++++++++++++++++++

.. code-block:: bash

    docker run hello-world

If the command doesn't run successfully log out and in again or reboot the machine.
After, try running the last command again.

Deployment from docker.io
-------------------------

This section makes use of Dallinger's ``dallinger docker-ssh`` command. In order to get a full understanding of its
capabilities refer to the official documentation at https://dallinger.readthedocs.io/en/latest/docker_support.html,
although this shouldn't be necessary for a basic deployment in the way described below.

.. note::

    Unless you already have one, create an account on ``docker.io`` or ``ghcr.io``. In this document,
    ``docker.io`` is utilized as the place for storing our Docker images.

The following steps are all executed from your local computer.

Add remote server to docker servers list
++++++++++++++++++++++++++++++++++++++++

Here, we use ``cap-experiments.ae.mpg.de`` as the server where experiments will be deployed.
Add it to the list of remote servers known to `docker-ssh`

.. code-block:: bash

    dallinger docker-ssh servers add --user cap --host cap-experiments.ae.mpg.de

To verify it has been added, execute

.. code-block:: bash

    dallinger docker-ssh servers list

Login to docker.io (locally)
++++++++++++++++++++++++++++

.. code-block:: bash

    docker login -u <DOCKER_IO_USERNAME> -p "<DOCKER_IO_PASSWORD>" docker.io

or for  better security

.. code-block:: bash

    docker login -u <DOCKER_IO_USERNAME> --password-stdin docker.io

Now type ``CTRL-D``, paste the password and hit `RETURN`.

.. note::
    For how to use a `credentials store`, see this link: https://docs.docker.com/engine/reference/commandline/login/#credentials-store

Make sure your experiment's constraints.txt file is up-to-date
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

In your experiment directory execute

.. code-block:: bash

    dallinger generate-constraints

Adjust the experiment's `config.txt` file
+++++++++++++++++++++++++++++++++++++++++

Add a new section ``Docker`` containing the key ``docker_image_base_name`` to your experiment's `config.txt` file.

.. code-block:: bash

    [Docker]
    docker_image_base_name = docker.io/<DOCKER_IO_USERNAME>/<DOCKER_IO_REPOSITORY>

Build Docker image
++++++++++++++++++

*This step is optional as `dallinger docker-ssh deploy` will also build the image if it has changed or does not exist yet.*

The Docker image will contain all necessary software to independently run in a Docker container on the remote server.
Build it with

.. code-block:: bash

    dallinger docker build

Deploy image to remote server
+++++++++++++++++++++++++++++

You are now ready to deploy the image to the remote server:

.. code-block:: bash

    dallinger docker-ssh deploy

This will append a new line after the line which specifies `docker_image_base_name` in `config.txt`.
The console's output should give you hints for how to further proceed from here.

Special notes when using CAP-Recruiter as recruitment system
------------------------------------------------------------

Specify extra parameter
+++++++++++++++++++++++

Add the following code inside the experiment's class:

.. code-block:: python

    from dallinger.config import get_config

    @classmethod
    def extra_parameters(cls):
        get_config().register("cap_recruiter_auth_token", str, [], False)

Set authentication tokens
+++++++++++++++++++++++++

Add a new section to your local user's `.dallingerconfig` file to provide an authentication token
for the CAP-Recruiter API:

.. note::

    See CAP-safe for the valid authentication tokens.

.. code-block:: bash

    [API Tokens]
    # staging
    cap_recruiter_auth_token = <AUTH_TOKEN>

    # production
    cap_recruiter_auth_token = <AUTH_TOKEN>


Specify the recruiter class
+++++++++++++++++++++++++++

Finally, specify the recruiter class in `config.txt`:

**Staging**

.. code-block:: bash

    recruiter = StagingCapRecruiter

**Production**

.. code-block:: bash

    recruiter = CapRecruiter

.. note::

    The `DevCapRecruiter` class is only used during development. Don't use it when deploying!
