Step 1: Install Docker Desktop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can get Docker Desktop from the following link: https://www.docker.com/products/docker-desktop/
Normally Docker Desktop will work out of the box on Linux and macOS machines,
but there is lots of help available online if you get stuck.

Step 2: Install PyCharm
^^^^^^^^^^^^^^^^^^^^^^^

We recommend using PyCharm as your integrated development environment (IDE) for working with PsyNet.
You can learn about PyCharm here: https://www.jetbrains.com/pycharm/
We recommend using the Professional version in particular. If you are a student or academic,
you can get a free educational license via the PyCharm website.

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

Step 4: Try running an experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To check that everything is now running properly, you should try running an experiment.
You can start by downloading one from the :ref:`Example experiments <example_experiments_introduction>` page.
Follow the instructions in the repository to launch the experiment using Docker,
or just try running the following command:

::

    bash docker/psynet debug local


Step 5 (Optional): Install editable PsyNet and Dallinger repositories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes it is useful to edit PsyNet and Dallinger source code as part of debugging an experiment.
To do this, you should ``git clone`` the PsyNet and Dallinger repositories from their corresponding hosts:

- https://gitlab.com/PsyNetDev/PsyNet
- https://github.com/Dallinger/Dallinger/

You should place these repositories in your working directory, and leave their names exactly
as their defaults ('PsyNet' and 'Dallinger').
Now, if you run an experiment using the following command:

::

    bash docker/psynet-dev debug local

it will use these local repositories for PsyNet and for Dallinger.
