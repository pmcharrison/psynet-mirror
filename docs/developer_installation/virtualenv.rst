Creating a fresh virtual environment
====================================

Sometimes you have PsyNet already installed but you want to create a fresh
virtual environment, perhaps to diagnose some package versioning issues.
You can do that as follows:

.. code-block:: bash

   mkvirtualenv new-env --python $(which python3)

replacing ``new-env`` with the desired name of your new environment.

Then, to reinstall your local PsyNet and Dallinger packages
(assuming they are located in their default locations):

:: code-block:: bash

    cd ~/Dallinger
    pip3 install -r dev-requirements.txt
    pip3 install --editable '.[data]'

    cd ~/PsyNet
    pip3 install -e '.[dev]'
