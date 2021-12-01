==========
Recruiters
==========

.. _CAP-Recruiter:

CAP-Recruiter
-------------

Specify extra parameter
+++++++++++++++++++++++

Add the following code inside the experiment's class:

.. code-block:: python

    from dallinger.config import get_config

    @classmethod
    def extra_parameters(cls):
        get_config().register("cap_recruiter_auth_token", str, [], False)

Set authentication tokens
+++++++++++++++++++++++++

Add a new section to your local user's `.dallingerconfig` file to provide an authentication token
for the CAP-Recruiter API:

.. note::

    See CAP-safe for the valid authentication tokens.

.. code-block:: bash

    [API Tokens]
    # staging
    cap_recruiter_auth_token = <AUTH_TOKEN>

    # production
    cap_recruiter_auth_token = <AUTH_TOKEN>


Specify the recruiter class
+++++++++++++++++++++++++++

Finally, specify the recruiter class in `config.txt`:

**Staging**

.. code-block:: bash

    recruiter = StagingCapRecruiter

**Production**

.. code-block:: bash

    recruiter = CapRecruiter

.. note::

    The `DevCapRecruiter` class is only used during development. Don't use it when deploying!
