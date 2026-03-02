Step 1: Install Docker Desktop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. include:: docker_desktop_installation.rst

Step 2: Install an IDE
^^^^^^^^^^^^^^^^^^^^^^

We recommend using **VSCode** or **Cursor** as your integrated development environment (IDE) for working with PsyNet.
Both are free and work well with PsyNet.

- **VSCode**: Download from https://code.visualstudio.com/
- **Cursor**: Download from https://cursor.sh/

.. note::

    **VSCode vs Cursor**: Cursor is built on VSCode and includes AI-assisted coding features (like AI chat and code completion).
    For PsyNet development purposes, both work equally well. VSCode is completely free and open source, while Cursor offers
    a free tier with some limitations and paid plans for advanced AI features. Choose VSCode if you prefer the original,
    more established editor, or Cursor if you want AI-powered development assistance. The setup instructions and functionality
    are largely the same for both.

**PyCharm** is also supported as an alternative IDE, but note that PyCharm remote debugging is currently not working (as of February 2025).
If you choose to use PyCharm, you will need to configure it yourself; we do not provide detailed setup instructions as they may become outdated.



Step 3: Install Git
^^^^^^^^^^^^^^^^^^^

Most people working with PsyNet will need to work with Git.
Git is a popular system for code version control, enabling people to track changes to code as a project develops,
and collaborate with multiple people without accidentally overwriting each other's changes.
To install Git, visit the `Git website <https://git-scm.com/downloads>`_.

You will also typically work with an online Git hosting service such as
`GitHub <https://github.com>`_ or
`GitLab <https://about.gitlab.com/>`_.
Speak to your lab manager for advice about which one your lab uses;
at the `Centre for Music and Science <https://cms.mus.cam.ac.uk/>`_ we use GitHub,
whereas the `Computational Auditory Perception group <https://www.aesthetics.mpg.de/en/research/research-group-computational-auditory-perception.html>`_
uses GitLab. You will probably want to create an account on that website before continuing.

.. warning::

    *Windows users only*: once you've installed Git, you need to run a few commands in your terminal:

    ::

        git config --global core.autocrlf false
        git config --global core.eol lf

    This code tells Git to use Unix-style line endings in your code repositories rather than Windows-style line endings.
    This is important because your Docker run scripts won't run with the latter.


.. warning::

    *Windows users only*: if you plan to use an SSH key to connect to your online Git hosting service,
    and you want to use an SSH key with a password, then by default you will have to reenter your password
    each time you restart WSL. If this sounds annoying, we recommend either creating your SSH key without a
    password, or following the instructions
    `here <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/working-with-ssh-key-passphrases?platform=windows>`_
    to have you password managed by ``ssh-agent``.


Step 4: Download an experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To check that everything is now running properly, you should try running an experiment.
You can start by downloading one from the :ref:`Example experiments <example_experiments>` page.

The easiest way to download the code is as a zip file. If you are viewing the repository
online you should see a link to do this on the web page.

If you want to work on the experiment yourself you should probably download it using Git.
If you are viewing the repository online you should see button saying 'Clone' or similar;
this will give you some download links to copy. You can use these in your terminal.
We recommend you use the 'HTTPS' link.

::

    # Navigate to the parent directory where you want to download your project.
    # The project will be downloaded as a subdirectory within this directory,
    # defaulting to the name of the repository.
    # Note: you should create the parent directory first if it doesn't exist yet.
    cd ~/Documents/psynet-projects

    # Clone the Git repository, replacing the URL below with the one you get from
    # the website under the Clone with HTTPS option.
    git clone https://gitlab.com/pmcharrison/example-experiment.git

If you want to run an experiment from a private repository then someone should have added you already
as a collaborator. You will need to use your credentials when cloning the repository;
if you use the HTTPS link then you should be prompted for these automatically.


Step 5: Set up your IDE
^^^^^^^^^^^^^^^^^^^^^^^

### Setting up your IDE

Open your IDE and use your IDE to open the downloaded folder.
You should then 'build' the experiment. The first time you build a PsyNet
experiment it will download PsyNet and lots of other dependencies. Make sure you have a
good internet connection for this, it will take a few minutes.
You build the experiment by running the following in your IDE's terminal:

::

    bash docker/build


Note: if you see an error message like this:


::

    ./docker/run: Permission denied

run the following command, then try again:

::

    chmod +x docker/*

If you see other error messages at this point, see Troubleshooting.

The project includes a pre-configured `.vscode/launch.json` file that is set up for debugging in VSCode/Cursor.
You can use this to debug your experiment by setting breakpoints and using the debugger.

Step 6: Running the experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. warning::
    **MacOS users only:**

    macOS's 'AirPlay Receiver' functionality clashes with the default ports used by Dallinger and PsyNet.
    You should disable this functionality before proceeding. To achieve this, go to System Preferences, then Sharing,
    and then untick the box labeled 'Airplay Receiver'.

You should now be able to run the experiment.
Try this by running the following command in your IDE's terminal:

::

    bash docker/psynet debug local

It'll print a lot of stuff, but eventually you should see 'Dashboard link' printed.
Open the provided URL in Google Chrome, and it'll take you to the experiment dashboard.
From here you can start a new participant session.


Step 7 (Optional): Install editable PsyNet and Dallinger repositories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes it is useful to edit PsyNet and Dallinger source code as part of debugging an experiment.
To do this, you should ``git clone`` the PsyNet and Dallinger repositories from their corresponding hosts:

- https://gitlab.com/PsyNetDev/PsyNet
- https://github.com/Dallinger/Dallinger/

You should place these repositories in your working directory, and leave their names exactly
as their defaults ('PsyNet' and 'Dallinger').
If you are using a Windows machine, then you will need to place these repositories in your WSL (Linux)
working directory. You may be able to find this by going to File Explorer, looking for Linux,
then Ubuntu. If you are not sure, try running the command below, and it should print an error message
telling you where exactly to look.

Now, if you run an experiment using the following command:

::

    bash docker/psynet-dev debug local

it will use these local repositories for PsyNet and for Dallinger.
