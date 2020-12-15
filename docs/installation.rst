.. _installation:
.. highlight:: shell

============
Installation
============


User installation
-----------------

If you just want to use `psynet` in an experiment and you don't
need to run the demo or edit the source, you can simply install it with `pip`:

.. code-block:: console

    pip3 install git+ssh://git@gitlab.com/computational-audition-lab/psynet

Note that you must have set up your GitLab SSH keys already.
It is also possible to install specific commits, see
`this documentation <https://dallinger.readthedocs.io/en/latest/private_repo.html>`_
for details.

Developer installation
----------------------

If you want to run the `psynet` demo or if you think you
might want to edit the source some day,
it's better to install it as an editable repository using `pip`, as follows:

Choose a location to put your installation, e.g. `~/cap`.

.. code-block:: console

    cd ~/cap
    git clone https://gitlab.com/computational-audition-lab/psynet

By default this command installs the ``master`` branch. You can switch between
different branches, and even different commits, using Git.
To update your repository to the latest version,
run ``git pull``.

The Git command will have created a folder called `psynet`.
Navigate to this folder:

.. code-block:: console

    cd psynet

Install with pip3 (make sure you are in the appropriate virtual environment
already, e.g. by running `workon dlgr_env`):

.. code-block:: console

    pip3 install -e .

The `-e` flag makes it editable.
