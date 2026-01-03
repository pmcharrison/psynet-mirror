Quickstart
==========

PsyNet relies on many interconnected services, including PostgreSQL, Redis, and Flask.
To simplify the installation process, we use Dev Containers to automatically provision
these services on your local machine.

.. note::

    See the :ref:`legacy_installation` section for details on alternative installation methods.


Install Google Chrome
---------------------

PsyNet currently only supports Google Chrome.
You can download Google Chrome for free from the following link: https://www.google.com/chrome/.

Install Docker Desktop
----------------------

Docker is a virtualization platform used for running software in a platform-independent way.
It's required for running Dev Containers.

.. include:: legacy_installation/docker_installation/docker_desktop_installation.rst

Install an IDE
--------------

We recommend using Visual Studio Code (VSCode) as your IDE for working with PsyNet.
This means that you can use our provided configuration files to automatically configure your IDE,
to work with PsyNet.
You can download VSCode for free from the following link: https://code.visualstudio.com/.

You might also consider using Cursor, which is an AI-enhanced fork of VSCode.
Cursor is very helpful at explaining how to use PsyNet features.
You can download Cursor for free from the following link: https://www.cursor.com/.

Download PsyNet
---------------

Download the PsyNet repository using one of the following methods:

If you have Git installed, you can clone the PsyNet repository to your current directory
with the following command:

.. code-block:: bash

    git clone https://gitlab.com/PsyNetDev/PsyNet

Alternatively, if you don't have Git installed, you can navigate to PsyNet's GitLab page,
click the 'Code' button, and select 'Download ZIP'.
Once the ZIP file has downloaded, unzip it to your desired location.

Open the PsyNet repository
--------------------------

Now open the repository in your IDE ('File' > 'Open Folder' in VSCode/Cursor).

Launch a Dev Container
----------------------

You should now see a prompt to launch a Dev Container.

.. image:: ../installation/images/open-devcontainer.png
    :alt: Screenshot showing how to open a Dev Container in VSCode or Cursor.
    :class: bordered
    :align: center
    :width: 400px

Before proceeding to the next step, wait until the automatic configuration scripts have stopped running
(it should take 30-60 seconds).

Launch a PsyNet demo
--------------------

Once the Dev Container is running, open a terminal window.
In VSCode/Cursor, you can do this by clicking the 'Terminal' button:

.. image:: ../installation/images/terminal-button.png
    :alt: Screenshot showing how to open a terminal window in VSCode or Cursor.
    :class: bordered
    :align: center
    :width: 100px

You should see a terminal prompt like this:

.. image:: ../installation/images/terminal-prompt.png
    :alt: Screenshot showing a terminal prompt in VSCode or Cursor.
    :class: bordered
    :align: center
    :width: 400px

Now navigate to a PsyNet demo.
You can see the available demos in the file explorer by navigating to the 'demos' directory.
The following code navigates to the 'timeline' demo:

.. code-block:: bash

    cd demos/timeline

Now you can launch the demo using the following command:

.. code-block:: bash

    psynet debug local

You will need to wait 10 seconds or so for the demo to start.
You may see one or more pop-ups asking whether you want to open an external website;
you should say Yes to these.

If everything works properly, you should see two web pages.
One is a participant interface, looking something like this:

.. image:: ../installation/images/participant-interface.png
    :alt: Screenshot showing a participant interface in a PsyNet demo.
    :class: bordered
    :align: center
    :width: 600px

The other is an admin interface, looking something like this:

.. image:: ../installation/images/admin-interface.png
    :alt: Screenshot showing an admin interface in a PsyNet demo.
    :class: bordered
    :align: center
    :width: 600px

You can now interact with the demo as if you were a participant.
If you want to start a second participant session, you can do this via the admin interface,
clicking the 'New participant' button on the 'Development' tab.

You can also use the admin interface to view the data collected from the participants.
Try taking a few pages of the experiment, then refresh the admin interface,
then click 'Database', and explore the available data types.

Create your own experiment
--------------------------

The recommended way to start developing your own experiments is to start by copying
an existing PsyNet demo. Have a look through the demos directory to see what might be a good starting point.

Once you've chosen your demo, copy it somewhere else on your computer.
For example, you might want to create a directory in your home directory called 'psynet-experiments',
and copy the demo into this directory.

Now, you want to open a new Dev Container for this new experiment,
following the same process as before:

1. Open the new experiment directory in your IDE
2. Follow the prompt to launch a Dev Container
3. Wait until the automatic configuration scripts have stopped running
4. You can then launch the experiment by running `psynet debug local` in the terminal

This works because each demo directory contains its own ``Dockerfile`` and ``.devcontainer`` directory,
which is used to define the Dev Container environment.

You can now start modifying the experiment to your liking.
Try some simple modifications to begin with, for example changing the text of the questions.
If you're feeling confident, you can try some more complex modifications.
For ideas, you can browse the other demos, or browse the PsyNet documentation,
or ask Cursor to help you (but encourage it to look at the PsyNet source code rather than just guessing)

Simple modifications, such as changing text, can be done without restarting the experiment.
Simply edit the code in your IDE, save the file, and refresh the browser.
More complex modifications, such as changing the stimuli, will require you to restart the experiment.
To do this, you will need to stop the experiment by pressing Ctrl+C in the terminal,
then restart it by running ``psynet debug local`` again.

Prepare a remote server for deployment
--------------------------------------

PsyNet experiments are typically deployed to a remote server.
You can use your own pre-existing server,
or you can use Dallinger (one of PsyNet's dependencies) to provision a server for you from Amazon Web Services (AWS).
We will describe both approaches below.

Before you start, you will likely need to create a ``.dallingerconfig`` file in your local machine's home directory.

.. code-block:: bash

    touch ~/.dallingerconfig

This ``.dallingerconfig`` file provides global configuration options for PsyNet and Dallinger.
It is auomatically shared with your Dev Containers.

.. tab:: Using your own server

    Suppose you already have a server, and it has a domain name which resolves to its IP address
    (e.g. ``my-server.com``). This server must not be configured to rely on a password to authenticate,
    it should instead use a key pair (i.e. a public key, which sits on the server, and a private key,
    which sits on your local machine).
    The private key might be your personal private key (typically ``~/.ssh/id_rsa`` or ``~/.ssh/id_ed25519``)
    or alternatively it might be a PEM file that you received when setting up the server.
    If it's a PEM file, you should copy it to the ``~/.ssh`` directory (e.g. ``~/.ssh/my-server.pem``).

    Before continuing, you should test that you can connect to your server using SSH.
    If you are using a personal private key, you should be able to connect as follows
    (we will suppose that the server's domain name is ``my-server.com`` and the username is ``ubuntu``):

    .. code-block:: bash

        ssh ubuntu@my-server.com

    If you are using a PEM file, you will need to pass it to the SSH client:

    .. code-block:: bash

        ssh -i ~/.ssh/my-server.pem ubuntu@my-server.com

    Once you've verified that you can connect to your server using SSH,
    close the connection using ``Ctrl+C``.
    You then need to tell Dallinger about your private key by adding the following to ``~/.dallingerconfig``,
    setting the ``server_pem`` option to the path of your private key:

    .. code-block:: bash

        [PEM files]
        server_pem = ~/.ssh/id_rsa  # or ~/.ssh/id_ed25519, or ~/.ssh/my-server.pem, as appropriate

    You can then register your server from your Dev Container terminal:

    .. code-block:: bash

        dallinger docker-ssh servers add --host my-server.com --user ubuntu

    This might take a few minutes as Dallinger will install any required dependencies.
    Don't worry if you see an error message about Docker not being found;
    Dallinger will install Docker for you.

.. tab:: Provisioning an AWS server

    Renting an AWS server costs money if you do it for a long time. However, the average
    PsyNet experiment only takes a few hours to run (because participants are quick to recruit with Prolific),
    so AWS costs only need to be a few dollars. However, if you forget to stop the server when you're done,
    you might incur much larger costs. **You must therefore be very careful when using AWS servers,
    and double-check your AWS console to ensure that you are not incurring unexpected costs.**

    .. note::

        At the time of writing (January 2026), the recommended AWS server type for deployment
        is ``m7i.xlarge`` (16 GB RAM, 4 vCPUs), which costs around $0.20 an hour.
        A five-hour experiment should therefore only cost around $1.

    If you like, you can provision an AWS server yourself using the AWS console.
    If you do it this way, you can register it like any other server via the 'Using your own server' method.
    Alternatively, you can get Dallinger to provision the AWS server for you following the steps below.

    .. warning::

        The instructions below involve sharing your AWS credentials with Dallinger.
        AWS credentials are sensitive information; if someone else gets hold of them,
        they could use them to access your AWS account and incur unexpected costs.
        There is a minor possibility that this could happen one day if one of PsyNet's dependencies
        ended up being compromised by a bad actor. To protect yourself from this, we recommend
        using Identity and Access Management (IAM) to minimise the scope of your credentials.
        We also recommend deleting your credentials after use (you can do this in the AWS console).

    If you use IAM to manage your credentials (recommended), you will need to create your IAM user
    with the following permissions:

    .. code-block:: bash

        AmazonEC2FullAccess
        AmazonRoute53FullAccess
        AmazonS3FullAccess  # only if you want to use S3 for storing experiment data/backups
        AmazonMechanicalTurkFullAccess  # only if you want to use MTurk for recruiting participants
        AmazonSNSFullAccess  # only if you want to use MTurk

    Once you have your AWS credentials, you will need to place them in the ``~/.dallingerconfig`` file
    mentioned above.

    .. code-block:: bash

        [AWS]
        aws_access_key_id = your-secret-aws-access-key-id
        aws_secret_access_key = your-secret-aws-secret-access-key

    You'll also need to register a domain name in AWS Route 53.
    If you're working within a research group, we recommend setting up a single domain name for the group
    (e.g. ``cool-psychology.org``)
    Dallinger then makes it easy to use subdomains for each individual server
    (e.g. ``memory-experiments.cool-psychology.org``).

    Once you have your domain name, you can provision a server from AWS within your Dev Container terminal:

    .. code-block:: bash

        dallinger ec2 provision \
            --name memory-experiments \
            --region us-east-1 \
            --dns-host memory-experiments.cool-psychology.org \
            --type m7i.xlarge

    Your server will then automatically be registered with Dallinger
    (no need to run ``dallinger docker-ssh servers add``).
