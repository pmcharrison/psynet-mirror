.. _ssh_server:
.. highlight:: shell

===========
SSH servers
===========

The recommended approach for hosting your own PsyNet experiments is to
set up your own remote server accessed via SSH. We will refer to such
servers as 'SSH servers'.

Setting up the remote server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are several ways to set up your own remote server.
One way is to rent one via Amazon Web Services (see
`tutorial <deploy/aws_server_setup>`_).
Other comparable recommended companies include Hetzner and Contabo.
As a very approximate rule of thumb, we recommend 5 GB of RAM for each
simultaneous experiment you think you will need to host.

Once you've set up your remote server, you need to make sure that your local computer
has passwordless SSH access to the remote server.
If you have a key pair for the server, you probably need to add it to your SSH agent
with code like the following:

.. code:: bash

    ssh-add path/to/your/key.pem

If you normally need a password to access the instance, you'll need to
upload your local machine's SSH key to the remote instance. If you don't have
an SSH key already, generate one on your local machine:

.. code:: bash

    ssh-keygen

Then upload it to the remote instance by running a command in the following form,
replacing the credentials and server address as appropriate:

.. code:: bash

    ssh-copy-id yourusername@your-server.ac.uk

Verify that you can login passwordless by running the following:

.. code:: bash

    ssh your-username@your-server.ac.uk

If this works, you're ready to register the remote server within PsyNet/Dallinger.
Run the following:

.. code:: bash

    dallinger docker-ssh servers add --user your-username --host your-server.ac.uk


Setting up your Docker registry
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Deploying via SSH requires you to setup a Docker registry which will host your
Docker images. GitHub and GitLab both allow you to create suitable Docker registries.

The first step is to login to the Docker registry service on your local machine.
To login to the GitLab docker registry:

.. code:: bash

    docker login registry.gitlab.com

.. note::

    If you are using a self-hosted registry then you will need to change the URL,
    for example:

    .. code:: bash

        docker login registry.gitlab.developers.cam.ac.uk

    In some situations (e.g. federated authentication) you will not be able to login
    to your account via the command-line in this way. Instead, you will have to create
    a `personal access token via GitLab <https://gitlab.developers.cam.ac.uk/-/profile/personal_access_tokens>`_
    and then login with a command like the following:

    .. code:: bash

        docker login registry.gitlab.developers.cam.ac.uk -u your-username

    You should then enter your access token when prompted.

.. note::

    If you see this error:

    .. code:: bash

        WARNING! Your password will be stored unencrypted in /home/pmch2/.docker/config.json.

        Configure a credential helper to remove this warning. See

        https://docs.docker.com/engine/reference/commandline/login/#credentials-store

    you can probably continue without worrying about it. We are still working out
    the best way to deal with Docker credential management in PsyNet/Dallinger.

You then need to do exactly the same `docker login` process but on your remote server.
To do this, you need to open an SSH terminal to your server, if you haven't already:

.. code:: bash

    ssh your-username@your-server.ac.uk

Then run the same `docker login` command that you ran previously.

You then need to create a container registry in GitLab/GitHub. You can do it
using their web interface. Note that, for now, you probably need to make it public
(we are still working on private authentication), so make sure that you don't have to
deploy experiments with sensitive data in their experiment code.

Finally, you then need to tell your local PsyNet/Dallinger installation to store
its experiment images in this registry. To do this, you need to edit your local
``~/.dallingerconfig`` file.

If you don't have such a file already, you can create it like this:

.. code:: bash

    touch ~/.dallingerconfig

You can then edit it on Mac like this:

.. code:: bash

    open ~/.dallingerconfig

or simply with a text editor via your GUI.

Place a line like the following in your ``~/.dallingerconfig``,
putting the link to your own image registry:

.. code:: bash

    docker_image_base_name = registry.gitlab.developers.cam.ac.uk/mus/cms/psynet-experiment-images

That's it! You should be all set up now.

Deploying experiments via SSH
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You deploy experiments using the ``psynet deploy command``:

.. code:: bash

    psynet deploy ssh --app your-app-name

Briefly, the command works as follows:

- Run any preliminary steps, e.g. uploading assets to the remote server
- Build the Docker image, packaging up all local code and dependencies
- Push the Docker image to the remote server
- Instruct the remote server to pull the Docker image
- Instruct the remote server to spin up the Docker app
- Instruct the remote server to launch the experiment

This command can go wrong at several points. The parts that happen on the local
machine are usually easiest to debug. When things go wrong on the remote server,
you may need to connect to it via a separate SSH terminal to work out what's going on.
To connect to the server, run this in a separate terminal:

.. code:: bash

    ssh your-username@your-server.ac.uk

Navigate to the experiment's folder:

.. code:: bash

    cd ~/dallinger/your-app-name

If this folder doesn't exist yet, your command probably failed before it got
to the remote server.

Now view the Docker logs:

.. code:: bash

    docker compose logs

Often you will see the real error message there. You may need to scroll up through
the logs to see the full picture; sometimes there are multiple error messages,
but only the first one is the 'real' problem.

Sometimes it is useful to execute code on this remote Docker instance to work out
what happened. You can do this as follows:

.. code:: bash

    docker compose exec web /bin/bash

Under the hood
^^^^^^^^^^^^^^

It's worth knowing a few things about what's happening under the hood here so that you
are better positioned to debug things when they go wrong.

The SSH server works using Docker. Docker is a containerization service that virtualizes
entire operating systems and installed dependencies. This isolation is very helpful for ensuring
application portability.

When we work with Docker, we begin by creating a Docker *image*. A docker image is a snapshot
of an operating system in a particular status. The operating system we use here is Linux.
If you are familiar with the terminal in MacOS, then you will find Linux fairly intuitive.

Docker images are defined by writing Dockerfiles. Your experiment directory contains such a file,
it will be named ``Dockerfile``. Have a read through one such file to get a picture of how
the Docker image ends up being defined.

When we run an app we create one or more containers based on Dockerfiles. Containers are virtual
computers that are initialized according the snapshot provided in the Docker image.
You can run many containers on the same computer, but of course they all consume their own
computational resources.

The SSH server uses a tool called *docker compose* to orchestrate multiple containers for the
same app. Each PsyNet experiment contains four distinct containers:

- ``web`` - serves HTTP requests
- ``worker`` - process asynchronous tasks
- ``clock`` - schedules tasks
- ``redis`` - stores variable values

The SSH server additionally provides two further containers which are shared across all experiments:

- ``postgresql`` - hosts the experiment databases
- ``caddy`` - redirects HTTP requests to the appropriate experiment app. See
  `Caddy server <https://caddyserver.com/>`_ for more details.

When you deploy an experiment to the SSH server, a folder is created in the location
``~/dallinger/your-app-name`` which contains a Docker compose configuration called
``docker-compose.yml``. You can inspect this configuration file to learn about how the app
is defined. When you SSH to this server, you can interact with this folder to
gain entry to your application. For example, you can run the following code to gain SSH access
to the web process of your app:

.. code:: bash

    cd ~/dallinger/your-app-name
    docker compose exec web /bin/bash

Within the same directory, you can run the following command to see live logs from your app:

.. code:: bash

    docker compose logs

You can run the following command to view the status of all Docker containers currently running on the server,
including containers from other apps:

.. code:: bash

    docker ps

Once you are done with your experiment, you can export the data to your local computer using the following command,
but run it on your local computer, not via your SSH terminal.

.. code:: bash

    psynet export ssh --app your-app-name

For more information, see `Exporting <deploy/export.html>`_.

You can then tear down your app via the following command, again run on your local computer:

.. code:: bash

    psynet destroy ssh --app your-app-name



Known issues
^^^^^^^^^^^^

When many apps are deployed on the same server it is possible that certain apps
eat up too many database connections. To check the current connections to the database,
run this on the remote server:

.. code:: bash

    cd ~/dallinger
    docker compose exec postgresql /bin/bash
    psql -U dallinger

    select pid as process_id,
       usename as username,
       datname as database_name,
       client_addr as client_address,
       application_name,
       backend_start,
       state,
       state_change
    from pg_stat_activity;

This will print a table of database connections. The number of rows is the number of database
connections. The limit is by default 100; if you are close to 100, then you are close to trouble.

Normally you can (temporarily) resolve problems with the number of connections by restarting certain
processes in an experiment. Restarting is fast and should not significantly impact on user experiences.
To restart processes for a given app, run the following:

.. code:: bash
    cd ~/dallinger/your-app-name
    docker compose restart web
    docker compose restart worker
    docker compose restart clock

.. warning::

    Sometimes we see SQLAlchemy errors as a result of running related commands, we're not entirely
    sure when/why this happens. For now it's worth avoiding restarting processes unless absolutely
    necessary. It's good to test that your app still works after doing this.
