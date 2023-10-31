Step 1: Install Docker Desktop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can get Docker Desktop from the following link: https://www.docker.com/products/docker-desktop/
Normally Docker Desktop will work out of the box on Linux and macOS machines,
but there is lots of help available online if you get stuck.

You may need to set some settings in Docker Desktop once it's installed.
Navigate to Docker Desktop settings, then look for an 'Advanced' tab.
If you don't see such a tab, you can skip the following instructions.
If you do see such a tab, do the following:

1. Select 'System (requires password)' installation of Docker's CLI tools, rather than 'User'.
2. Tick the box that says 'Allow the default Docker socket to be used'.
3. Tick the box that says 'Allow privileged port mapping'.

Step 2: Install PyCharm
^^^^^^^^^^^^^^^^^^^^^^^

We recommend using PyCharm as your integrated development environment (IDE) for working with PsyNet.
You can learn about PyCharm here: https://www.jetbrains.com/pycharm/
For proper integration with PsyNet (especially if you are using the Docker installation route),
you will need to use the Professional version in particular. If you are a student or academic,
you can get a free educational license via the PyCharm website.

.. warning::

    *Windows users only*: You should configure PyCharm to use Unix-style line endings (LF) by default instead
    of Windows-style line endings (CLRF); otherwise your Docker scripts may not run.
    To do this, follow
    `these instructions from the JetBrains website <https://www.jetbrains.com/help/pycharm/configuring-line-endings-and-line-separators.html>`_:

    1. Open PyCharm's settings.
    2. Go to File | New Projects Setup | Settings (or Preferences) for New Projects | Editor | Code Style.
    3. Set Line separator to 'Unix and macOS (\n)'.
    4. If you are in a project already, you may wish to select the current project from the Scheme dropdown menu on this
       same page and repeat the process of setting the line seperator.
    5. Press OK.



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


Step 5: Set up PyCharm
^^^^^^^^^^^^^^^^^^^^^^

The first time you open PyCharm you may need to enter some license information,
decide to start a free trial, or something similar. Do this first.

Now, within PyCharm, click File > Open and open the folder that Git downloaded for you.
This opens the experiment directory as a PyCharm 'project'.
It may ask you to setup an 'interpreter' at this point; ignore this message and click Cancel.

The first thing you should do is 'build' the experiment. The first time you build a PsyNet
experiment it will download PsyNet and lots of other dependencies. Make sure you have a
good internet connection for this, it will take a few minutes.
You build the experiment by running the following in your PyCharm terminal:

::

    bash docker/build


Note: if you see an error message like this:


::

    ./docker/run: Permission denied

run the following command, then try again:

::

    chmod +x docker/*

If you see other error messages at this point, see Troubleshooting.

Now you should configure PyCharm to use your experiment's Docker image.

.. warning::

    If you are not using PyCharm Professional Edition, you will probably not have the option
    to integrate PyCharm with Docker in this way.

To do this, first open the Dockertag file in your experiment's directory
(this is simply a file with the filename 'Dockertag'),
and copy the contents to your clipboard.
Then look for the 'interpreter' box in the bottom-right corner of your screen;
this would normally say 'No interpreter', but it could say something like 'Python 3.11'.
Click on this text and click 'Add New interpreter',
then click 'On Docker'.
Select an option that looks like 'Pull, or perhaps 'Pull or use existing',
then under 'Image tag' paste the contents of the Dockertag file you copied earlier.
Click Next, and wait a while. The script will initially look for that tag on Dockerhub, which should fail;
It should then look for that tag on your local computer, and successfully acquire the image you just built locally.
Click Next, then select 'System Interpreter', then click 'Create'. You should have now successfully set up your
interpreter.

Step 6: Running the experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If all has gone well, you should now be able to run the experiment.
Try this by running the following command in your PyCharm terminal:

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
