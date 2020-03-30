.. highlight:: shell

============
Installation
============


User installation
-----------------

If you just want to use `dlgr_utils` in an experiment and you don't 
need to run the demo or edit the source, you can simply install it with `pip`:

.. code-block:: console

    pip3 install git+ssh://git@gitlab.com/computational-audition-lab/dlgr-utils

Note that you must have set up your GitLab SSH keys already.

Developer installation
------------------------------------

If you want to run the `dlgr_utils` demo or if you think you 
might want to edit the source some day, 
it's better to install it as an editable repository using `pip`, as follows:

Choose a location to put your installation, e.g. `~/cap`.

.. code-block:: console

    cd ~/cap
    git clone 

This will create folder called `dlgr_utils`.
Navigate to this folder:

.. code-block:: console

    cd dlgr_utils


Install with pip3 (make sure you are in the appropriate virtual environment
already, e.g. by running `workon dlgr_env`):

.. code-block:: console

    pip3 install -e .

The `-e` flag makes it editable.

Run the demo with `dallinger debug --verbose`.
