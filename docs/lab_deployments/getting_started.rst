Getting Started
===============

This section is a practical guide for deploying PsyNet experiments in the
lab workflow. It covers the common steps that everyone needs, then points
you to recruiter-specific instructions for
`Prolific <recruiter_specific_deployment_steps.html#prolific>`__,
`CINT <recruiter_specific_deployment_steps.html#cint-lucid>`__, and
`Lab Recruiter <recruiter_specific_deployment_steps.html#lab-recruiter>`__.

How to use this guide
---------------------

Read the pages in order the first time you deploy an experiment:

1. :doc:`Prerequisites <prerequisites>`: complete one-time software,
   account, credential, and Git setup.
2. :doc:`General Deployment Process <general_deployment_process>`:
   understand the full experiment lifecycle, from design through testing
   and deployment.
3. :doc:`Provisioning <provisioning>`: choose and prepare the server that
   will host your experiment.
4. :doc:`Setting Up the Experiments <setting_up_the_experiments>`:
   configure your experiment, recruiter, storage, and pre-deployment
   checks.
5. :doc:`Deploying <deploying>`: run the deployment command and save the
   dashboard and log URLs.
6. :doc:`Recruiter-Specific Deployment Steps <recruiter_specific_deployment_steps>`:
   confirm any extra Prolific, CINT, or Lab Recruiter requirements.

The current recommended workflow uses Docker and either an internal lab
server or an EC2 server. Prolific is used as the main example, but the
same general process also applies to CINT and Lab Recruiter deployments
unless a recruiter-specific page says otherwise.

Glossary
--------

.. image:: /_static/images/lab_deployments/image29.png
   :width: 8.5in
   :class: glossary-hero

**PsyNet**
   The package we use to create online experiments. It builds upon
   Dallinger.

**Experiment hosting**
   The *server* that hosts your experiment. PsyNet supports
   **internal servers** and **EC2 servers**. The best choice depends on
   participant location.

**Docker**
   Container software used to run an experiment in a fixed environment
   to avoid unexpected behavior. It is recommended for local debugging
   and deployment (see `Best practices <#best-practices>`__).

**Recruiter**
   A *service* that invites and pays participants with optional
   demographic requirements. Examples include Prolific, CINT
   (previously Lucid), and Lab Recruiter.

**Remote debug (SSH)**
   Running ``psynet debug ssh`` against a server. This is not the same
   as deployment or hotair.

**Deployment**
   Running ``psynet deploy ssh`` and activating a recruiter.

**Hotair**
   A participant-view test mode that is visible only to you and not to
   real participants. Use this before live deployment, and share the
   hotair link with team members for feedback.

**Archive (redeploy from archive)**
   Continuing data collection with an existing experiment. The archived
   experiment database file is called an archive.

**Provisioning**
   Setting up a server (here, typically via EC2).

**Teardown**
   Quitting a server (here, typically via EC2).

**initial_recruitment_size**
   The variable in your ``Experiment`` class that controls how many
   participants are invited initially. Avoid inviting more participants
   than your deployment can handle.

**Increase experiment size**
   Recruit more participants manually once current participants finish.
   Repeat until your target sample size is reached.

**Auto-recruit**
   Maintains a constant number of active participants. In this mode,
   ``initial_recruitment_size`` effectively becomes the desired steady
   concurrent count.

Best practices
--------------

We recommend a shared workflow because it makes problems easier to
diagnose and support:

- Use macOS where possible.
- Install `Docker <prerequisites.html#docker-desktop>`__ and an IDE such as
  `PyCharm Professional <prerequisites.html#pycharm>`__ or Cursor.
- Use Docker for both local development and remote deployment.
- Use one of the currently supported recruiters: Prolific, CINT, or Lab
  Recruiter.
- Check that your experiment satisfies the requirements of the recruiter
  you choose before you launch.

Deployment Checklist
--------------------

1. **Prerequisites**

   - Set up PsyNet and complete the required installations.
   - Ensure Docker Desktop is `installed and running <prerequisites.html#docker-desktop>`__.
   - Log in to the `group Docker registry <prerequisites.html#log-into-the-docker-registry>`__ via GitLab (one-time).

2. **Experiment Setup**

   - Verify all experiment parameters.
   - Confirm locale, recruiter, and PsyNet estimates (time and payment).
   - Verify recruiter-specific settings, such as payment parameters,
     participant qualifications, demographic requirements, and any
     recruiter-specific configuration. See
     :doc:`Recruiter-Specific Deployment Steps <recruiter_specific_deployment_steps>`.

   - Use an appropriate storage backend (S3 or LocalStorage, not
     DebugStorage).

3. **Provisioning (Server Setup)**

   - Choose the correct server type (internal or EC2).
   - If using EC2, provision in the region closest to participants.
   - Confirm the EC2 instance type and local storage are sufficient if
     you use LocalStorage.

4. **Deployment**

   - Test your experiment end-to-end (including edge cases) in Docker.
   - Open Docker Desktop before deployment and confirm it is running.
   - Ensure ``requirements.txt`` is correct and constraints are generated.
   - If using Prolific, ensure account balance is sufficient.
   - Deploy to your server and publish the experiment in Prolific/CINT.
     Double-check demographics and technical qualifications in the
     marketplace.

5. **Monitoring & Management**

   - Start with 5-10 participants, then gradually scale once data and
     completions look good.
   - Monitor the dashboard to track participant progress and identify errors early.
   - Check Dozzle logs and inspect the error database table.
   - Monitor participant messages/free-text feedback and debug as needed.
   - Check data quality regularly (e.g., with an export script).

6. **Export & Termination**

   - Export all collected data for analysis.
   - If using an internal server, delete the app.
   - If using EC2, teardown (terminate) the server to avoid unnecessary costs.
   - Deposit your export to your lab's designated data repository.

**Important:** Check the recruiter-specific sections for
additional setup and monitoring details.
