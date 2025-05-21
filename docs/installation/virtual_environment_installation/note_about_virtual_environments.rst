Note about virtual environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You need to use virtual environments to work with PsyNet.
This can be confusing if you haven't used Python virtual environments before.
We strongly recommend you take half an hour at this point to read some online tutorials
about virtual environments and how they can be created with the ``venv`` command.

.. note::

   We used to recommend ``virtualenvwrapper`` to manage virtual environments.
   With this approach, users would create a single shared virtual environment
   for all their PsyNet projects. We now recommend instead that users just use the built-in ``venv`` command,
   and create a new virtual environment for each project.

   For reference, this is the code we used to install ``virtualenvwrapper``:

   .. code-block:: bash

      pip3 install virtualenv
      pip3 install virtualenvwrapper
      export WORKON_HOME=$HOME/.virtualenvs
      mkdir -p $WORKON_HOME
      export VIRTUALENVWRAPPER_PYTHON=$(which python3)
      source $(which virtualenvwrapper.sh)
      echo "export VIRTUALENVWRAPPER_PYTHON=$(which python3)" >> ~/.zshrc  # If you are on Linux, you may need to replace ~/.zshrc with ~/.bashrc
      echo "source $(which virtualenvwrapper.sh)" >> ~/.zshrc  # If you are on Linux, you may need to replace ~/.zshrc with ~/.bashrc
