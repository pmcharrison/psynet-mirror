Docker
======

Introduction to Docker
----------------------

It is now possible to develop PsyNet experiments entirely within Docker.
Docker is a virtualization platform that runs software in 'containers' that behave like
self-contained operating systems. This enables us to run the same PsyNet code on different
operating systems (Windows, MacOS, Linux) without worrying about differences between these environments.
For more information see https://www.docker.com/.

Should I use Docker myself?
---------------------------

We are starting to encourage people to use Docker as the primary approach for developing and deploying
PsyNet experiments. It has several key advantages:

- **Simplifying installation.** Previously it would take many steps to install PsyNet on a local computer,
  as one had to install many supporting services such as Redis and Postgres. Now all of this is wrapped in Docker,
  so the installation process is massively simplified.
- **Simplifying environment management.** Previously one had to to be very careful about the maintenance of
  'virtual environments' that kept appropriate versions of packages installed for given experiment implementations.
  It was easy to get these virtual environments mixed up, or broken. With Docker, the user doesn't have to worry
  about any of this, as Docker manages everything.
- **Simplifying deployment.** Using Docker, experiments are deployed via identical Docker images to those used
  for local debugging. This significantly reduces the possibility of unforeseen divergences between local and
  deployment environments that might cause bugs.
- **Enhancing reproducibility.**  When we deploy an experiment using Docker, the experiment deployment is then
  stored as a standalone Docker image that captures all of its dependencies, and should be perfectly reproducible
  years into the future. This contrasts with previous approaches, where incremental changes to Python versions
  and operating system conditions would often eventually break experiments.

There are a few disadvantages too -- we think they're small, but worth noting nonetheless.

- Using Docker introduces a performance overhead to local debugging, meaning slower start-up times
  and increased memory usage. It's helpful to use a computer with at least 16 GB of RAM.
- Docker adds an extra layer between you and code execution, which can make it a little harder to debug
  processes. However there are various techniques that can reduce the impact of this which we'll talk about later.

Prerequisites for PsyNet in Docker
----------------------------------

The most important first step is to install Docker Desktop.
You can get Docker Desktop from the following link: https://www.docker.com/products/docker-desktop/

Normally Docker Desktop will work out of the box on Linux and MacOS machines.
On Windows it often requires a bit more work.
In particular, there is something called "Windows Subsystem for Linux" (WSL) that you may need to install/activate.

Installing WSL on Windows
^^^^^^^^^^^^^^^^^^^^^^^^^

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

Installing PyCharm
^^^^^^^^^^^^^^^^^^

We recommend using PyCharm as your integrated development environment (IDE) for working with PsyNet.
You can learn about PyCharm here: https://www.jetbrains.com/pycharm/
We recommend using the Professional version in particular. If you are a student or academic,
you can get a free educational license via the PyCharm website.

Installing Git
^^^^^^^^^^^^^^

Most people working with PsyNet will need to work with Git.
Git is a popular system for code version control, enabling people to track changes to code as a project develops,
and collaborate with multiple people without accidentally overwriting each other's changes.
To install Git, visit the `Git website <https://git-scm.com/downloads>`.

You will also typically work with an online Git hosting service such as
`GitHub <https://github.com>` or
`GitLab <https://about.gitlab.com/>`.
Speak to your lab manager for advice about which one your lab uses;
at the `Centre for Music and Science <https://cms.mus.cam.ac.uk/>` we use GitHub,
whereas the `Computational Auditory Perception group <https://www.aesthetics.mpg.de/en/research/research-group-computational-auditory-perception.html>`
uses GitLab.
You will need to create an account on that website, and for PsyNet purposes it's recommended that you link your
account to your local computer by creating and uploading an SSH key.

An SSH key is a special kind of password that is stored on your local computer.
To use an SSH key, you typically do the following:

- Generate an SSH key pair on your local computer;
- Upload the 'public' component of this key pair to GitHub or GitLab.

You should do this before moving forward with your experiment implementation. For instructions, see below:

- `GitHub SSH key instructions <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account>`
- `GitLab SSH key instructions <https://docs.gitlab.com/ee/user/ssh.html>`

Once you're set up with GitHub/GitLab, you're ready to start working with a Git repository.
This might be a repository you create yourself, or you might work with a repository someone else created.
Ask your lab manager for advice.
