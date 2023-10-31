Windows installation
====================

.. include:: shared_introduction.rst

Step 0: Install WSL
^^^^^^^^^^^^^^^^^^^

Docker on Windows depends on the "Windows Subsystem for Linux" (WSL). All code you run using PsyNet and Docker needs to be run within the Linux subsystem. 
If you haven't worked with Docker before you may well need to install this.

.. include:: ../wsl_installation.rst

Once you've installed WSL, you probably will need to restart your computer before trying to relaunch Docker Desktop.

.. include:: shared_installation.rst

Troubleshooting
^^^^^^^^^^^^^^^

.. include:: ../wsl_troubleshooting.rst

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
