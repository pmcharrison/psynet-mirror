Getting Started
===============

Important Notice:
-----------------

This document provides a step-by-step guide for deploying experiments.
To ensure a smooth deployment process, **certain sections are mandatory
for all users**, while others are specific to the recruiter you choose
(`Prolific <recruiter_specific_deployment_steps.html#prolific>`__,
`CINT <recruiter_specific_deployment_steps.html#cint-lucid>`__, or
`Lab Recruiter <recruiter_specific_deployment_steps.html#lab-recruiter>`__).

How to Use This Document
^^^^^^^^^^^^^^^^^^^^^^^^

- 🛑 **Must do**: Sections that are essential for everyone. These include
  prerequisites, setting up servers, and general deployment steps.
  Skipping these may lead to errors.
- 🔹 **Optional**: Sections that depend on your chosen recruiter. You can
  skip parts that do not apply to your deployment method.

What You Should Read First
^^^^^^^^^^^^^^^^^^^^^^^^^^

-  All users must complete the :doc:`prerequisites <prerequisites>`
   before proceeding.

-  We strongly recommend reading up to the
   :doc:`recruiter-specific deployment steps <recruiter_specific_deployment_steps>`
   section to fully understand the deployment process.

-  After that, verify CINT settings such as incidence rate, or continue
   with the recruiter-specific section that applies to your experiment.

This guide follows the current recommended deployment mode, which
utilizes Docker with AWS provisioning, primarily using
`Prolific <recruiter_specific_deployment_steps.html#prolific>`__ as a
recruiter. However, if you are deploying via
`CINT <recruiter_specific_deployment_steps.html#cint-lucid>`__ or
`Lab Recruiter <recruiter_specific_deployment_steps.html#lab-recruiter>`__,
you will find detailed instructions in their respective sections.

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

One powerful way to reduce error is to streamline and unify the whole
process of running online experiments. We therefore make the following
recommendations. You can deviate from it, **but you must be aware that
you might encounter more issues and cannot always be supported.**

-  We expect you to use a Mac.

-  You need to have `Docker <prerequisites.html#docker-desktop>`__ and `PyCharm <prerequisites.html#pycharm>`__ installed,
      if you have a student ID or a proof of teaching, we recommend setting up `Github
      Copilot <prerequisites.html#setup-co-pilot>`__

-  You should use Docker for local development and remote deployment.

-  For now we mainly support deployment to Prolific, CINT and
      Lab Recruiter. Make sure your experiment complies with the
      requirements.

Deployment Checklist
--------------------

1. **Prerequisites**

   - Set up PsyNet and complete all required installations.
   - Ensure Docker Desktop is `installed and running <prerequisites.html#docker-desktop>`__.
   - Log in to the `group Docker registry <prerequisites.html#log-into-the-docker-registry>`__ via GitLab (one-time).

2. **Experiment Setup**

   - Verify all experiment parameters.
   - Confirm locale, recruiter, and PsyNet estimates (time and payment).
   - Verify recruiter-specific settings:

     - **Prolific**

       - Set base payment (``wage_per_hour``) to ``0`` during
         deployment.
       - Verify qualifications (e.g., audio, nationality, microphone).

     - **CINT**

       - Verify PsyNet settings (e.g., aggressive timeout).

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
   - Deposit your export to FS Jacoby.

**Important:** Check the recruiter-specific sections for
additional setup and monitoring details.
