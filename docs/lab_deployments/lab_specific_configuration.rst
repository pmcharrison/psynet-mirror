CAP Lab Configuration
=====================

This page documents the Computational Audition Lab (CAP) specific
infrastructure and credentials needed to deploy experiments. New lab
members should complete the :doc:`Prerequisites <prerequisites>` page
first, then return here for the CAP-specific values to fill in.

.. contents:: On this page
   :local:
   :depth: 1

----

Credential Store (cap-safe)
----------------------------

The lab maintains a private credential store called **cap-safe**,
which contains the shared configuration files every lab member needs.

To obtain your credentials:

1. Clone the cap-safe repository (you need to be added to the
   ``computational-audition-lab`` GitLab group first — ask Frank):

   .. code:: bash

      git clone https://gitlab.com/computational-audition-lab/cap-safe.git

2. Inside the repository there is a file called ``cap_keys.zip``:

   .. image:: /_static/images/lab_deployments/image2.png
      :width: 8.5in

3. Enter the safe password (ask a lab member for it).

4. Inside the archive you will find ``.dallingerconfig`` and ``cap.pem``.

5. Place ``.dallingerconfig`` in your home directory (``~/.dallingerconfig``)
   and ``cap.pem`` in your ``~/.ssh/`` directory.

6. Set the correct permissions on the PEM file:

   .. code:: bash

      chmod 600 ~/.ssh/cap.pem

   On Windows:

   .. code:: bash

      icacls C:\path\to\cap.pem /inheritance:r /grant:r "%USERNAME%:R"

7. The ``.dallingerconfig`` from cap-safe already contains the correct
   EC2 settings for the lab. Verify it includes:

   .. code:: ini

      [EC2]
      ec2_default_security_group = cap
      ec2_default_pem = /Users/<your-username>/cap

   Replace ``<your-username>`` with your actual macOS username (run
   ``whoami`` to check). Verify with:

   .. code:: bash

      ls ~/.ssh/cap.pem

The cap-safe also contains translation credentials (see
`Translation Credentials`_ below) and any other lab API keys.

----

Lab GitLab Account
------------------

All CAP experiment repositories live in the
``computational-audition-lab`` GitLab group, accessed through the
shared group account ``computational.audition``.

**To get access:**

- Ask a lab member to add you to the group via the ``computational.audition``
  account.
- Ask Frank to add your SSH key to the group access list.

**To create a new experiment repository:**

1. In the ``computational-audition-lab`` group, create a subgroup for
   the experiment series, then create a new project within it.
2. Uncheck "Initialize with README" when creating the project.
3. In your local experiment folder:

   .. code:: bash

      git init
      git remote add origin <your-new-repository-url>
      git push -u origin master

Log in to the GitLab Docker registry before deploying:

.. code:: bash

   docker login registry.gitlab.com

----

Internal Lab Servers
--------------------

The lab has internal servers that are free to use (unlike EC2). Use
these when deploying within Europe.

Currently available internal servers:

.. MPI Frankfurt servers commented out pending confirmation they are still available.
   cap-experiments.ae.mpg.de (MPI Frankfurt — primary)
   cap-experiments3.ae.mpg.de (MPI Frankfurt)
   cap-experiments4.ae.mpg.de (MPI Frankfurt)

- ``experiments1.cococo-lab.cornell.edu`` (Cornell)

Register each server with Dallinger once (you only need to do this
once per machine):

.. code:: bash

   # MPI Frankfurt servers — confirm availability with Frank before using:
   # dallinger docker-ssh servers add --host cap-experiments.ae.mpg.de --user cap
   # dallinger docker-ssh servers add --host cap-experiments3.ae.mpg.de --user cap
   # dallinger docker-ssh servers add --host cap-experiments4.ae.mpg.de --user cap
   dallinger docker-ssh servers add --host experiments1.cococo-lab.cornell.edu --user cap

To deploy to an internal server:

.. code:: bash

   # MPI Frankfurt example (confirm availability with Frank before using):
   # psynet deploy ssh --app <app-name> --server cap-experiments3.ae.mpg.de --dns-host cap-experiments3.ae.mpg.de
   psynet deploy ssh --app <app-name> --server experiments1.cococo-lab.cornell.edu --dns-host experiments1.cococo-lab.cornell.edu

----

EC2 Domain Convention
----------------------

The lab uses the domain ``cap-experiments.com`` for EC2 deployments.
Each lab member uses a personal subdomain based on their first name
(or a short version of it).

**Standard provisioning command:**

.. code:: bash

   dallinger ec2 provision --name <name>-<experiment>-<batch> --region <region> --dns-host <your-name>.cap-experiments.com --type <type>

**Example:**

.. code:: bash

   dallinger ec2 provision --name elif-melody-batch2 --region eu-west-3 --dns-host elif.cap-experiments.com --type m7i.xlarge

The experiment URL will be:
``<app-name>.<your-name>.cap-experiments.com``

The Dozzle log URL will be:
``logs.<your-name>.cap-experiments.com``

**Instance naming convention:** Always start the server name with your
name so others can identify it — e.g., ``elif-melody-batch2``, not
``melody123``. Unidentifiable servers may be deleted.

**Recommended instance types:**

- ``m7i.large`` — for remote debugging
- ``m7i.xlarge`` — for live deployment

To list running instances:

.. code:: bash

   dallinger ec2 list instances --pem cap --running

To filter by region:

.. code:: bash

   dallinger ec2 list instances --pem cap --region <region> --running

----

Translation Credentials
------------------------

The cap-safe contains both translation credentials the lab uses.

**Google Translate:**

The file ``psynet-gtrans.json`` is in the cap-safe. Place it in your
home directory:

.. code:: bash

   cp psynet-gtrans.json ~/

Then verify your ``.dallingerconfig`` contains:

.. code:: ini

   [Google Translate]
   google_translate_json_path = ~/psynet-gtrans.json

**OpenAI:**

The OpenAI API key is in the cap-safe. Add it to your
``.dallingerconfig``:

.. code:: ini

   [OpenAI]
   openai_api_key = <see cap-safe>

See the
`Internationalization tutorial <https://psynetdev.gitlab.io/PsyNet/tutorials/internationalization.html>`__
for full usage instructions.

----

Lab Config Values for Experiment Scripts
-----------------------------------------

When writing experiment scripts, use these standard CAP lab values:

.. code:: python

   config = {
       "contact_email_on_error": "computational.audition@gmail.com",
       "organization_name": "Cornell Computational Cognition Lab",
       ...
   }

For CINT experiments, use the running-specific email:

.. code:: python

   "contact_email_on_error": "computational.audition+online_running@gmail.com"

----



CINT Custom Qualifications (Lab-Specific Only)
-----------------------------------------

The following qualifications are specific to the lab's CINT configuration and may not be available outside our account setup.
Currently, we have the following custom qualifications:

-  [\`\ `TIMEOUT <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=187e22aa-8a67-45c9-8a7c-481eeeaddfb0>`__\ \`]:
   warning participants they can't leave the page as they might be
   kicked out otherwise (set automatically)

-  [\`\ `MONOLINGUALISM <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=08a162fe-4c14-48c7-b850-1d09f95527a1>`__\ \`]:
   asking participants if they are monolingual

-  [\`\ `HAS_AUDIO <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=25434891-030a-405a-9616-e43961d674fa>`__\ \`]:
   asking participants if they can play audio

-  [\`\ `ALLOW_VOICE_RECORDING <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=9242d802-f6d6-4786-8049-50490dcd5179>`__\ \`]:
   asking participants if they can record their voice

-  [\`\ `BORN_IN_COUNTRY <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=2a6d41c7-c38c-4a69-ad12-2cca5074d98f>`__\ \`]:
   asking participants if they were born in the country

-  [\`\ `HAS_NATIONALITY <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=f91c6b4f-7167-4e30-95ab-9efb408f0537>`__\ \`]:
   asking participants

-  [\`\ `IS_NATIVE <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=c0833d98-be26-46df-8e01-1abbb740cda6>`__\ \`]:
   asking participants if they are native speakers

If another lab requires similar logic, these should be recreated independently within their own CINT account.


**Extending Qualifications to New Languages**

To extend an existing qualification to a new language:

- Add the question in the CINT interface
- Ensure answer options remain in the same order as the original
- Use English as a reference to maintain consistency across locales

-----------------------------------

**Adding a New Qualification (CINT UI)**

1. Go to the CINT qualification page
2. Click "Add Qualification"
3. Configure:
   - Name: use uppercase with underscores (e.g. HAS_AUDIO)
   - Type: "Conditional List – Single Punch"
   - Minimum Displayed Conditions: 2
   - Maximum Displayed Conditions: 2
4. Add question text for each language
5. Upload answer options using "Mass Upload"
6. Save changes

.. note::

   New qualifications may take some time to propagate within CINT.
   To retrieve the QuestionID, inspect the page source after creation.


Pilot Testing Convention
-------------------------

Before deploying with real participants, share a hotair link with the
lab for feedback. Post the link in **#online_experiments** on Slack
with a description of what to test and any specific aspects you want
feedback on.

Once you have pilot data, write your ``export.py`` analysis script
and check that data are processed correctly before running the full
deployment.

----

Co3lab Recruiter
--------------

The lab runs its own recruitment platform at
`recruiter.cococo-lab.cornell.edu <https://recruiter.cococo-lab.cornell.edu/accounts/login/>`__.

- To create an admin account, contact: cap-information@ae.mpg.de
- Payment rate: typically **15 EUR/hour** (set ``wage_per_hour: 15``)
- Set ``recruiter: "lab-recruiter"`` in your experiment config
- After deploying, go to the Experiments tab in the LAB Recruiter,
  click **New Experiment**, and set the URL to the link printed in
  the terminal after deployment
  (e.g., ``https://<app-name>.experiments1.cococo-lab.cornell.edu``)
- Consent form: Contact the team if you
  need a custom consent form

For full recruiter-specific deployment steps, see
:doc:`Recruiter-Specific Deployment Steps <recruiter_specific_deployment_steps>`.

----

Data Deposit
------------

After each experiment, export and deposit your data to **FS Jacoby**
(the lab's shared network storage). Run your ``export.py`` script to
verify the data are complete before depositing.

----

Lab Support Contacts
---------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Topic
     - Contact
   * - PsyNet / Dallinger bugs
     - ``#psynet-support`` on Slack or
       `GitLab issues <https://gitlab.com/PsyNetDev/PsyNet/-/issues>`__
   * - Online experiment questions
     - ``#online-experiments`` on Slack
   * - General programming questions
     - ``#programming`` on Slack
   * - cap-safe access / credentials
     - Ask Frank or a senior lab member
   * - LAB Recruiter admin account
     - cap-information@ae.mpg.de
   * - Lab server access
     - Ask Frank to add your SSH key
