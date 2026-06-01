Prerequisites (One-time Setup)
==============================

This page describes the one-time setup required to run experiments using
the lab deployment workflow. You only need to complete this setup once.

PsyNet installation
-------------------

For detailed installation instructions on macOS, please refer to the
`official installation guide <https://psynetdev.gitlab.io/PsyNet/installation/index.html>`__.

Required software and accounts
------------------------------

Docker Desktop
^^^^^^^^^^^^^^

Install Docker Desktop:
https://www.docker.com/products/docker-desktop

Log into the Docker registry
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Make sure you are logged into the group Docker registry through GitLab:

.. code:: bash

   docker login registry.gitlab.com

Set up a Docker account:

1. Download Docker.

2. Create an account on Docker Hub: https://www.docker.com/

Note that it is possible to use another Docker registry in general (for
example of another group, or a global repository with your personal
account), but this is not recommended within the group (see more
information https://psynetdev.gitlab.io/PsyNet/deploy/ssh_server.html)

IDE setup
~~~~~~~~~

We most strongly recommend **Cursor** as the default IDE for PsyNet
development. **VSCode** is the closest alternative because Cursor is
built on VSCode, so the same project settings and debugging files
generally work in both editors. **PyCharm** is also supported as an
alternative IDE, but it is no longer the default recommendation for PsyNet.

1. Download and install your IDE:

   - Cursor: https://cursor.sh/
   - VSCode: https://code.visualstudio.com/
   - PyCharm: https://www.jetbrains.com/pycharm/

2. Open your experiment repository as the project folder.

3. Select the Python interpreter or virtual environment you use for
   PsyNet. If you are working with Docker-based experiment scripts, use
   the terminal and helper scripts that come with the experiment
   repository.

4. To test that your setup works, open the IDE's integrated terminal, go
   to an experiment folder (for example, ``demos/timeline``), and run the
   local debug command used by your experiment setup, for example:

   .. code:: bash

      psynet debug local

   For Docker-based experiment templates, the command is typically:

   .. code:: bash

      bash docker/psynet debug local

   The command should eventually print a dashboard link. Open that link
   in Google Chrome and start a participant session to confirm that the
   experiment runs locally.

In particular, PyCharm remote debugging is currently known to be
unreliable, so we do not maintain detailed PyCharm setup instructions
here.

Git: version control and best practices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Set up an SSH key for GitLab

   To use GitLab, you need to activate an SSH key. Follow these steps:

   I. Run the following in terminal to generate an ED25519 key. When it asks for
      a location, press enter (sets default location in ``~/.ssh``). It then asks
      for a passphrase.

      .. code:: bash

         ssh-keygen -t ed25519

   II. Run the following to copy the SSH key to the clipboard:

       .. code:: bash

          pbcopy < ~/.ssh/id_ed25519.pub

   III. In the SSH Keys section of your gitlab account settings (look at
        "Preferences" in the upper right), paste your key in the "Key" box and
        replace "Title" with whatever you want to call your machine.

        .. image:: /_static/images/lab_deployments/image23.png
           :width: 8.5in

   IV. Press "Add key." You should now be able to push and pull from gitlab by entering your passphrase.

2. Connect to lab resources

   Ask your lab administrator to add you to the lab's GitLab group and
   to add your SSH key to the group access list.

3. How to use git

   **main** branch (used to be master branch): most stable form of the code

   **dev** branch: constitutes the next version of the software that we are
   preparing to release

   useful commands:

   .. code:: bash

      git init                      # create git repository
      git clone <url>               # clones the repository at url
      git status                    # show working tree status
      git add <files>               # add files
      git commit -m "my message"    # record changes
      git push                      # update remote
      git checkout <branch>         # switch branches

   We recommend using the Git interface in VSCode, Cursor, or another
   IDE for reviewing and committing changes.

   It is important to make sure you are logged in to git registry before
   deploying:

   .. code:: bash

      docker login registry.gitlab.com

4. How to create a repository in your lab's GitLab account

   1. create a subgroup for the experiment series and then, go on “create project”

   2. then go on “create project from blank

   3. then you should see something like this:

   4. Name your project, uncheck “Initialize with README”, and create the project.

5. Push your local repository to your lab's GitLab account

   1. Go to your experiment and make it a git repository:

      .. code:: bash

         git init

   2. Add the remote repository:

      .. code:: bash

         git remote add origin <your_empty_repository>

   3. Verify the remote is set up correctly:

      .. code:: bash

         git remote -v

   4. Check which files are tracked or changed:

      .. code:: bash

         git status

   5. Add files:

      .. code:: bash

         git add <files>

   6. Record the changes with a message:

      .. code:: bash

         git commit -m "your_message"

   7. Push to the remote:

      .. code:: bash

         git push origin main

How to commit in your IDE
^^^^^^^^^^^^^^^^^^^^^^^^^

-  Instead of using ``git commit -m "<your message>"``, you can also
   commit through your IDE's Git interface.

-  Go to “Commit” on the left side and check the files you want to
   commit. Type the message below and press “Commit”, or “Commit and
   Push” if you also want to push.

.. image:: /_static/images/lab_deployments/image51.png
   :width: 8.5in

Set credentials and server access keys
--------------------------------------

You will need a ``.dallingerconfig`` file in your home directory and a
PEM key file in your ``~/.ssh`` directory to access your lab's servers.

Your lab administrator should provide these files through a secure
channel (for example, an encrypted archive in a private credential
repository). The steps below assume your lab provides a credential
archive containing both files.

1. Obtain the credential archive from your lab administrator (e.g.,
   clone a private credential repository or download an encrypted
   archive).

2. Inside the archive there will be an encrypted file containing your
   credentials:

   .. image:: /_static/images/lab_deployments/image2.png
      :width: 8.5in

3. Enter the password provided by your lab administrator to decrypt the
   archive.

4. Inside you will find ``.dallingerconfig`` and a PEM key file (e.g.
   ``your-key.pem``).

5. Place ``.dallingerconfig`` in your home directory and ``your-key.pem``
   in your ``~/.ssh`` directory.

6. Set the correct permissions on the PEM file:

   .. code:: bash

      chmod 600 ~/.ssh/your-key.pem

   On Windows you may also need to run:

   .. code:: bash

      icacls C:\path\to\your-key.pem /inheritance:r /grant:r "%USERNAME%:R"

7. Add the following lines to your ``~/.dallingerconfig``, replacing the
   values with those provided by your lab administrator:

   .. code:: ini

      [EC2]
      ec2_default_security_group = <your-security-group>
      ec2_default_pem = ~/.ssh/your-key.pem

   You can verify the PEM file is in the right place by running:

   .. code:: bash

      ls ~/.ssh/your-key.pem
