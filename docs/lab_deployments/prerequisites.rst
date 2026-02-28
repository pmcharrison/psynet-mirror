Prerequisites (One-time Setup)
==============================

This describe all the setup process that needs to run experiments in the
main thread of the group.

You need to do this setup only once.

.. note::

   We will eventually separate this document from the deployment document.

PsyNet Installation 
--------------------

For detailed installation instructions on macOS, please refer to the
`official installation guide <https://psynetdev.gitlab.io/PsyNet/installation/index.html>`__.

Required Software & Accounts 
-----------------------------

🛑 Docker desktop 
^^^^^^^^^^^^^^^^^

Install Docker (https://www.docker.com/products/docker-desktop)

🛑 Log into the Docker Registry 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Make sure you are logged into the Group Docker registry via Gitlab with
your Gitlab credentials by running the command:

.. code:: bash

   docker login registry.gitlab.com

Set up docker account

1. Download docker

2. Create an account in docker.io: https://www.docker.com/

Note that it is possible to use another Docker registry in general (for
example of another group, or a global repository with your personal
account), but this is not recommended within the group (see more
information https://psynetdev.gitlab.io/PsyNet/deploy/ssh_server.html)

🛑 Pycharm
~~~~~~~~~~~~~~~~~~~~

Install PyCharm
^^^^^^^^^^^^^^^

-  Apply for educational discount
      (https://www.jetbrains.com/shop/eform/students )

-  Download and install `PyCharm Pro <https://www.jetbrains.com/pycharm/>`__.

**Important**, you need Pycharm Pro to be able to use the debugger.

Choose your environment
^^^^^^^^^^^^^^^^^^^^^^^

1. Open the project.

2. Go to settings -> Python interpreter:

3. Select show all:

.. image:: /_static/images/lab_deployments/image42.png
   :width: 8.5in

4. Go to plus sign

5. Go to existing environments and select from the list the one that
relates to you

.. image:: /_static/images/lab_deployments/image40.png
   :width: 2.5in

6. Press OK

7. Optional: Sometimes you already added the virtual environment, in
this case you can select it from the list on the left. However you may
need to turn of the filter (|image1|) in order to see it:

.. image:: /_static/images/lab_deployments/image17.png
   :width: 8.5in

Pressing the filter icon (the one on the right from the pencil icon):

.. image:: /_static/images/lab_deployments/image26.png
   :width: 3.5in

to test open the terminal in the lower part of the pycharm window, and
go to the folder of an experiment (e.g **demos/timeline**) and type
**psynet debug local**.

.. image:: /_static/images/lab_deployments/image47.png
   :width: 8.5in

Custom keymaps
^^^^^^^^^^^^^^

To further customize the ability to select a code and execute it go to
setting in python and search for “​​execute selection in python Console”
select this option:

.. image:: /_static/images/lab_deployments/image15.png
   :width: 8.5in

Add a simple shortcut for example replace this by Command+Enter. Now you
can select a code and Command+Enter will execute it in the console.

Debugging in Pycharm
^^^^^^^^^^^^^^^^^^^^

1. In the top right go to here:

.. image:: /_static/images/lab_deployments/image43.png
   :width: 8.5in

2. Select edit configurations:

3. Select + and debug server

4. Set the name to “Debug” and port to “1234”. If you use docker
locally. For Docker set the name to “Docker Debug”, set the port to
“12345” and change “localhost” to “host.internal”.

5. Copy the pip install command:

.. image:: /_static/images/lab_deployments/image8.png
   :width: 8.5in

6. Run it in the virtual environment.

7. Start the debugger.

8. Copy this line from the console to set a breakpoint.

.. image:: /_static/images/lab_deployments/image12.png
   :width: 8.5in

9. Put the breakpoint in your code

10. Your code should now stop at the breakpoint. You can now select
lines code in your console and press Command+Enter to execute the
selection in the debugger. You can see the variables when looking into
“Debugger”.

.. image:: /_static/images/lab_deployments/image31.png
   :width: 8.5in

9. Perform the following changes to the pycharm debug settings: go to
preferences and search for python debugger unselect “attach to
subprocesses” and select “gevent compatible”

.. image:: /_static/images/lab_deployments/image24.png
   :width: 8.5in

Setup Co-Pilot
^^^^^^^^^^^^^^

Copilot gives you autocomplete-suggestions for programming

Website to CoPilot
(https://plugins.jetbrains.com/plugin/17718-github-copilot )

In Pycharm go to Preferences -> Plugins-> Marketplace and look for
CoPilot

.. image:: /_static/images/lab_deployments/image55.png
   :width: 8.5in

click on Install and restart PyCharm

now you should see CoPilot in “Installed”

🛑 Git: Version control & Best Practices 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Setup shh keygen for gitlab

To use gitlab, you'll need to activate an SSH key. Follow these steps to
do so:

1. Run the following in terminal to generate an ED25519 key. When it asks 
   for a location, press enter (sets default location in ~/.ssh). It'll 
   then ask for a passphrase.

   .. code:: bash

      ssh-keygen -t ed25519

2. Run the following to copy the SSH key to the clipboard:

   .. code:: bash

      pbcopy < ~/.ssh/id_ed25519.pub

3. In the SSH Keys section of your gitlab account settings (look at
      "Preferences" in the upper right), paste your key in the "Key" box
      and replace "Title" with whatever you want to call your machine.

.. image:: /_static/images/lab_deployments/image23.png
   :width: 8.5in

4. Press "Add key." You should now be able to push and pull from gitlab
      by entering your passphrase.

2. Connect to Lab resources

Please ask a member to add you to the Computational Audition Lab Group
through the group account computational.audition.

Please ask Frank to add your SSH key to the group access list.

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

We strongly recommend using the pycharm IDE for committing.

It is important to make sure you are logged in to git registry before
deploying:

.. code:: bash

   docker login registry.gitlab.com

4. how to create a repository in computational.audtition

1. create a subgroup for the experiment series and then, go on “create project”

2. then go on “create project from blank

3. then you should see something like this:

4. name your project, uncheck “Initialize with README” and create the project\ |image2|

4. Push your local repository to computational.audition

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

   |image3|

5. Add files:

   .. code:: bash

      git add <files>

6. Record the changes with a message:

   .. code:: bash

      git commit -m "your_message"

7. Push to the remote:

   .. code:: bash

      git push origin main

How to git commit in Pycharm
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

-  Instead of using git commit -m “<your message>”, you can also commit
      via Pycharm.

-  Go to “Commit” on the left side and chak the files you want to
      commit. Type in the message below and press “Commit” or “Commit
      and Push” if you want to push too.

.. image:: /_static/images/lab_deployments/image51.png
   :width: 8.5in

.. _section-1:

🛑 Set credentials and cap-safe 
-------------------------------

You will need .dallingerconfig in your home directory and a cap.pem file
in your ~/.ssh directory.

To get the cap.pem follow the following instructions.

1. Clone the group safe:

   .. code:: bash

      git clone https://gitlab.com/computational-audition-lab/cap-safe.git


2. Inside the repository there is a file called “cap_keys.zip”

.. image:: /_static/images/lab_deployments/image2.png
   :width: 8.5in

3. Enter the password (same as safe password)

4. Inside you can find .dallingerconfig and cap.pem

5. Move it to your home directory

6. Set the proper permissions on the pem file. Go to the command line 
   terminal and type:

   .. code:: bash

      chmod 600 ~/.ssh/cap.pem

If using windows you may also need to do this:

.. code:: bash

   icacls C:\path\to\cap.pem /inheritance:r /grant:r "%USERNAME%:R"

7. Be sure that you are at the latest Dallinger version and add the
following lines to your .dallingerconfig file:

.. code:: ini

   [EC2]
   ec2_default_security_group = cap
   ec2_default_pem = /Users/<your username>/cap

Please be sure to type the correct username. If you do not know your
username then you can verify it by typing in the console: whoami. You
can verify that this line /Users/<your username>/cap to output of the
following command: ls ~/.ssh/cap.pem
