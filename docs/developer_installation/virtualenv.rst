Creating a fresh virtual environment
====================================

Sometimes you have PsyNet already installed but you want to create a fresh
virtual environment, perhaps to diagnose some package versioning issues.
You can do that as follows:

.. code-block:: bash

   mkvirtualenv new-env --python $(which python3)

replacing ``new-env`` with the desired name of your new environment.
