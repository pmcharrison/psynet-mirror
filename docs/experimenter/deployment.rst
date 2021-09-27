=================
Docker deployment
=================

Server setup
------------

This setup only has to be done by the server's administrator once. Also, instructions apply to Ubuntu 20.04 LTS (Focal Fossa) only.

Update sudo permissions
+++++++++++++++++++++++

Login on the remote server. Then, execute

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

    sudo groupadd docker
    sudo usermod -aG docker $USER
    newgrp docker

.. code-block:: bash

    sudo systemctl restart docker

Verify docker works
+++++++++++++++++++

.. code-block:: bash

    docker run hello-world

If it doesn't run the command successfully log out and log in a gain or reboot. Then try running the command again.


Deployment from docker.io
-------------------------

This section makes use of Dallinger's ``dallinger docker-ssh`` command. In order to get a full understanding of its
capabilities refer to the official documentation at https://dallinger.readthedocs.io/en/latest/docker_support.html,
although this shouldn't be necessary for a basic deployment in the way described below.

.. note::

    Unless you already have one, first create an account on ``docker.io``.

Add remote server to docker servers list
++++++++++++++++++++++++++++++++++++++++

We use ``cap-experiments.ae.mpg.de`` as the server where experiments will be deployed.

.. code-block:: bash

    dallinger docker-ssh servers add --user cap --host cap-experiments.ae.mpg.de

Login to docker.io (locally and on the remote server)
+++++++++++++++++++++++++++++++++++++++++++++++++++++

*TODO*: Check if both logins are necessary.

.. code-block:: bash

    docker login -u <DOCKER_IO_USERNAME> -p "<DOCKER_IO_PASSWORD>" docker.io

Adjust experiment config.txt
++++++++++++++++++++++++++++

Add a new section ``Docker`` containing key ``image_base_name`` to your experiments `config.txt` file.

.. code-block:: bash

    [Docker]
    image_base_name = docker.io/<DOCKER_IO_USERNAME>/<DOCKER_IO_REPOSITORY>

Build Docker image
++++++++++++++++++

The Docker image will contain all necessary software to independently run in a Docker container on the remote server.

.. code-block:: bash

    dallinger docker build

Push image to docker.io
+++++++++++++++++++++++

.. code-block:: bash

    dallinger docker push --use-existing


Deploy image to remote server
+++++++++++++++++++++++++++++

.. code-block:: bash

    dallinger docker-ssh deploy --image docker.io/<DOCKER_IO_USERNAME>/<DOCKER_IO_REPOSITORY>:<DOCKER_IMAGE_HASH> -c recruiter hotair -c dashboard_password cap

E.g.:

.. code-block:: bash

    dallinger docker-ssh deploy --image docker.io/dockeriousername/mcmcp:7f4ce7eb -c recruiter hotair -c dashboard_password cap

Tag Docker image
++++++++++++++++

.. code-block:: bash

    docker tag <DOCKER_IO_REPOSITORY>:<DOCKER_IMAGE_HASH> <DOCKER_IO_USERNAME>/<DOCKER_IO_REPOSITORY>:<DOCKER_IMAGE_HASH>

E.g.:

.. code-block:: bash

    docker tag mcmcp:7f4ce7eb dockeriousername/mcmcp:7f4ce7eb



