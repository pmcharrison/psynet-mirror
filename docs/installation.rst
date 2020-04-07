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

    pip3 install git+ssh://git@gitlab.com/computational-audition-lab/psynet@dev

Note that you must have set up your GitLab SSH keys already.
Note also that we have seleted the ``dev`` branch here. 
If you left out ``@dev``, it would instead install the ``master`` branch.
For now, we recommend the ``dev`` branch. 
It is also possible to install specific commits, see
`this documentation <http://docs.dallinger.io/en/latest/private_repo.html>`_
for details.

Developer installation
------------------------------------

If you want to run the `psynet` demo or if you think you 
might want to edit the source some day, 
it's better to install it as an editable repository using `pip`, as follows:

Choose a location to put your installation, e.g. `~/cap`.

.. code-block:: console

    cd ~/cap
    git clone -b dev https://gitlab.com/computational-audition-lab/psynet`

Note that we've installed the ``dev`` branch here. You can switch between
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
