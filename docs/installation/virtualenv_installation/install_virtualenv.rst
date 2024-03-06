Installing virtualenv
~~~~~~~~~~~~~~~~~~~~~

You need to use virtual environments to work with PsyNet.
This can be confusing if you haven't used Python virtual environments before.
We strongly recommend you take half an hour at this point to read some online tutorials
about virtual environments and managing them with ``virtualenvwrapper`` before continuing.

The following code installs ``virtualenvwrapper``:

.. code-block:: bash

   pip3 install virtualenv
   pip3 install virtualenvwrapper
   export WORKON_HOME=$HOME/.virtualenvs
   mkdir -p $WORKON_HOME
   export VIRTUALENVWRAPPER_PYTHON=$(which python3)
   source $(which virtualenvwrapper.sh)
   echo "export VIRTUALENVWRAPPER_PYTHON=$(which python3)" >> ~/.zshrc  # If you are on Linux, you may need to replace ~/.zshrc with ~/.bashrc
   echo "source $(which virtualenvwrapper.sh)" >> ~/.zshrc  # If you are on Linux, you may need to replace ~/.zshrc with ~/.bashrc
