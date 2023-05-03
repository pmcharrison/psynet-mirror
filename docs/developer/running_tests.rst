.. _developer:
.. highlight:: shell

=============
Running tests
=============

PsyNet contains a large number of automated tests to help protect the package
from bugs. This test suite includes running all the demos and checking that
they complete in the correct state.

Whenever you push a contribution to a branch of the PsyNet repository,
these automated tests will be automatically queued. They normally take 10-15 minutes
to complete. Keep an eye on the GitLab interface to see if any errors have occurred.
Errors should be resolved before merging branches into ``dev`` or ``master``.

Test parallelization
--------------------

The automated test suite is slow because it has to run more than 70 demo experiments.
GitLab therefore runs these tests in parallel to save time. This is not
really practical on most local machines, so be warned that running the full test
suite locally will ordinarily take a very long time. It's better instead to
run individual tests locally and only run the full test suite on GitLab.

Identifying which test failed
-----------------------------
If you see that the automatic tests have failed,
visit the GitLab error logs to see which particular test failed.
You're looking for a test script with a name like ``test_assets.py``,
and a test function within that, for example ``test_assets_upload_correctly()``.

The umbrella test scripts ``test_run_all_demos.py`` and ``test_run_isolated_tests.py``
iterate through many subsidiary test scripts.
If you see a failure there, inspect the logs to see exactly which
subsidiary test script failed.

Debugging tests locally
-----------------------

It is often faster to debug test failures on your local computer rather than
on GitLab. The first step is to identify which test failed, following
the instructions above. Let's suppose that the test is located in
``tests/test_assets.py``.
The next step is to reproduce this failure on your local computer.
You can do this by running the following in your terminal:

.. code-block:: python

    pytest tests/test_assets.py --chrome -s


The ``--chrome`` argument is only needed for tests that invoke an automated
web browser; if you omit this argument for such a test,
then the test will be skipped. This behavior is inherited from Dallinger,
we plan to remove it in the future.

The ``-s`` argument tells pytest to log live output from the test as it runs.
This is normally a good idea for keeping track of what's going on.

If you are using PyCharm it is usually preferable to run the tests through
the PyCharm interface. First you have to configure PyCharm's run configurations.
Do this as follows:

1. Click 'Run', then 'Edit configurations';
2. Click 'Edit configuration templates';
3. Select 'Python tests';
4. Select 'pytest';
5. Add ``--chrome -s`` to 'Additional arguments';
6. Click OK.

Now you can right click on a particular test file or test function within PyCharm
and run the test by clicking 'Run pytest in ...', or alternatively
'Debug pytest in ...'. The latter mode is slower but supports breakpoints.

Debugging tests via Docker
--------------------------

If you are making changes to the ``Dockerfile`` in your merge request, 
then these changes may not be reflected in the tests you run, because the 
tests by default pull the PsyNet master Docker base image. 
In order to make these tests work properly, you need to run the tests on 
a Docker image built from your branch. To do this, do the following.

First, go to your PsyNet source code directory and run the following
(make sure you are not within a demo directory):

:: 

    docker build -t registry.gitlab.com/psynetdev/psynet:master .

This will build the PsyNet docker image from your local branch and tag it as if it were
the master branch. Don't worry, this won't be uploaded to GitLab unless you say so.

If you now want to run a demo test, then you should be able to do so as follows:

::

    docker/run pytest test.py

Note that this does not quite match the Docker environment that the CI tests are using, 
but it should be close enough. We might document alternative approaches later.


Ignorable errors
----------------

There are certain errors that occasionally occur in the automated test suite
that have not been fixed yet because they only happen occasionally.
If you see such errors in your own branch, don't worry, you don't have to fix them.
They should normally go away if you click the rerun button for the particular
test that failed. An up-to-date list of such error messages will be kept below.

Deadlock error in gibbs demo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    E       psycopg2.errors.DeadlockDetected: deadlock detected
    E       DETAIL:  Process 60 waits for ShareLock on transaction 1205; blocked by process 71.
    E       Process 71 waits for ShareLock on transaction 1206; blocked by process 60.
    E       HINT:  See server log for query details.
    E       CONTEXT:  while updating tuple (0,17) in relation "node"
    /usr/local/lib/python3.10/site-packages/sqlalchemy/engine/default.py:736: DeadlockDetected
