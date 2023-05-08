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
When starting Docker for Windows you might run into following error: "A timeout occured while waiting for a WSL integration agent to become ready". In that case, try to install an older version of Docker Desktop (e.g. 4.17.1).

When trying to run an experiment you might encounter an error message simmilar to the following: "docker: Error response from daemon: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: error during container init: error mou
nting "/run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/Ubuntu-22.04/647ede0919eb9497eef4fc4d3073b8954528e4e97e5aa5995e0caf21f0b1cddc" to rootfs at "/root/.dallingerconfig": mount
/run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/Ubuntu-22.04/647ede0919eb9497eef4fc4d3073b8954528e4e97e5aa5995e0caf21f0b1cddc:/root/.dallingerconfig (via /proc/self/fd/14), flags: 0x5000: not a directory: unknown: Are you trying to mount a directory onto a file (or vice-versa)? Check if the specified host path exists and is the expected type."

You can fix this by creating an empty file called .dallingerconfig in the home directory of the Linux Subsystem. To do this you can run following command in your home directory
::
    touch .dallingerconfig
