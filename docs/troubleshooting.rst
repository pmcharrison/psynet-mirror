.. _develop_troubleshooting:
.. highlight:: shell

===============
Troubleshooting
===============


Annoying deprecation warnings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In some situations you can find that your PsyNet logs are filled with annoying deprecation warnings.
We think that the environment variable ``PYTHONWARNINGS`` should work for suppressing such warnings:

.. code :: bash

    PYTHONWARNINGS="ignore::DeprecationWarning" psynet debug local


Database connection refused
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Suppose you see an error message like this:

.. code:: bash

    connection to server at "localhost" (::1), port 5432 failed: Connection refused
        Is the server running on that host and accepting TCP/IP connections?

This means that your local Postgres database cannot be accessed.
This would normally only happen if you are not using PsyNet through Docker.

If you are on a Mac, you can check the status of your database by running this command:

.. code:: bash

    brew services

If you don't see a line with ``postgresql``, you have not installed PostgreSQL.
Follow the developer installation instructions to do so.

If you do see a line with ``postgresql``, it probably has ``error`` written next to it.
You need to get access to the logs to debug this error.
To do so, look at the ``File`` column of the ``brew services`` output,
find the value corresponding to ``postgresql``. Print that file in your terminal using ``cat``,
for example:

.. code:: bash

    cat ~/Library/LaunchAgents/homebrew.mxcl.postgresql@14.plist

Look for a line like this:

.. code:: bash

    <key>StandardErrorPath</key>

The error log path is contained underneath it, between the ``<string>`` identifiers.
View the last few lines of that file in your terminal using ``tail``, for example:

.. code:: bash
    tail /usr/local/var/log/postgresql@14.log

Have a look at the error message.
One possible message is something like this:

.. code:: bash

    2023-04-25 16:53:51.224 BST [28527] FATAL:  lock file "postmaster.pid" already exists
    2023-04-25 16:53:51.224 BST [28527] HINT:  Is another postmaster (PID 716) running in data directory "/usr/local/var/postgresql@14"?

If you see this error message, try restarting your computer and trying again.
If that doesn't work, try searching Google for help. If you find another solution,
please share your experience here.
