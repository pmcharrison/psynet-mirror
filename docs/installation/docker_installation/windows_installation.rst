Windows installation
====================

.. include:: shared_introduction.rst

Step 0: Install WSL
^^^^^^^^^^^^^^^^^^^

Docker on Windows depends on the "Windows Subsystem for Linux" (WSL). All code you run using PsyNet and Docker needs to be run within the Linux subsystem. 
If you haven't worked with Docker before you may well need to install this.

Here is a simple tutorial for installing WSL 2 and Ubuntu on Windows:
https://ubuntu.com/tutorials/install-ubuntu-on-wsl2-on-windows-10#1-overview
Note: it is WSL 2 we want, not just WSL. Bear this in mind when looking for online tutorials.

WSL is a platform for installing particular Linux operating systems. In addition to installing WSL,
the above tutorial also installs Ubuntu, which is a particular flavor of the Linux operating system.
This is important for getting Docker to work.

Once you've installed Ubuntu, it's important that you select it as the default distro within WSL.
You can list available distros within WSL by running the following command in your terminal:

::

    wsl -l --all

You want to set your default to the Ubuntu option.
That probably means writing something like this:

::

    wsl --setdefault Ubuntu


Note: If you see a message beginning "Hardware assisted virtualization and data execution protection
must be enabled in the BIOS", you need to restart your computer into BIOS and change some settings to enable those two things.
The precise set of steps will depend on your computer. The first step though is to restart your computer,
and press a certain key to launch into BIOS -- ordinarily that key will be printed on the screen at some point
during the startup sequence. Hint -- you might find that the option you need to select is called 'SVM mode'....

Once you've installed WSL, you probably will need to restart your computer before trying to relaunch Docker Desktop.

.. include:: shared_installation.rst

Troubleshooting
^^^^^^^^^^^^^^^

WSL 2 installation is incomplete
--------------------------------

If you see a message beginning with "WSL 2 installation is incomplete", you probably need to do the following:

- Click on the link it gives you
- Click on the link under 'download the latest package', open and run the installer once it has downloaded
- Continue with the next steps of the installation
- Note: if you run Powershell, it might fail if you run it on admin mode! If you get stuck (Access Denied),
  try running it again without admin mode and see if it works.

Hardware assisted virtualization
--------------------------------

If you see a message beginning "Hardware assisted virtualization and data execution protection must be enabled in the
BIOS", you need to restart your computer into BIOS and change some settings to enable those two things. The precise set
of steps will depend on your computer. The first step though is to restart your computer, and press a certain key to
launch into BIOS -- ordinarily that key will be printed on the screen at some point during the startup sequence.
Hint -- you might find that the option you need to select is called 'SVM mode'...

Failed to solve with frontend dockerfile
----------------------------------------

If you see a message starting "failed to solve with frontend dockerfile.v0",
you may want to try rebooting your computer and trying again.

Invalid option name: pipefail
-----------------------------

If you see an error message like this when running a Docker command:

::

    command not found 2:
    command not found 4:
    invalid option name: set: pipefail


The problem is probably that your project has the wrong line endings;
on Windows, if you are not configured correctly, then your files may end up
with Windows-style line endings (CRLF) instead of Unix-style line endings (LF).
To fix this, first follow the line-endings instructions described above for
setting up Git and PyCharm in Windows.
Then select your project folder in the project pane,
and from the task bar select File | File Properties | Line Separators | LF - Unix and MacOS.
Your command should now run without the error.

A timeout occurred
------------------

When starting Docker for Windows you might run into following error: "A timeout occured while waiting for a
WSL integration agent to become ready". In that case, you may want to try installing
an older version of Docker Desktop (e.g. 4.17.1).

Impersistence of ssh-agent in WSL
----------------------------

When deploying experiments, ssh-agent plays a crucial role in the communicaton between
the scientist's computer and the experiment server. However, in WSL, ssh-agent does not
persist across reboots of the virtual machine. To allow ssh-agent to automatically have
re-added provided SSH credentials upon initiation of WSL, you may consider the following
documentation from GitHub:
https://docs.github.com/en/authentication/connecting-to-github-with-ssh/working-with-ssh-key-passphrases#auto-launching-ssh-agent-on-git-for-windows
