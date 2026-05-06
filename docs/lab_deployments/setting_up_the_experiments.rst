Pre-Deployment Setup Overview
=============================

This page is a summary of the checks to complete before deploying your
experiment. Each section links to the detailed documentation where you
can find full instructions. Recruiter-specific instructions are covered
in :doc:`Recruiter-Specific Deployment Steps <recruiter_specific_deployment_steps>`.

Define the experiment configuration
-----------------------------------

Make sure the required experiment parameters are set and match the
version you intend to deploy:

- Consent.
- Experiment title and description.
- Payment settings.
- Expected completion time.
- Target participant count.
- Locale, if the experiment is translated.

Run the estimate command from the experiment directory:

.. code:: bash

   psynet estimate

Use the output to confirm that the expected completion time and
compensation are reasonable before you configure the recruiter.

.. _storage:

Choose a storage backend
------------------------

Use a deployment-ready storage backend. For experiments with assets,
choose either S3 storage or local storage according to the needs of the
experiment. Do not deploy with ``DebugStorage`` — it is only intended
for local development. For guidance on storage options, see the
`Assets tutorial <https://psynetdev.gitlab.io/PsyNet/tutorials/assets.html>`__.

Choose a recruiter
------------------

Choose the recruiter before you launch, because each recruiter has
different setup requirements:

- `Prolific <recruiter_specific_deployment_steps.html#prolific>`__.
- `CINT <recruiter_specific_deployment_steps.html#cint-lucid>`__.
- `Lab Recruiter <recruiter_specific_deployment_steps.html#lab-recruiter>`__.

After choosing the recruiter, read the matching section in
:doc:`Recruiter-Specific Deployment Steps <recruiter_specific_deployment_steps>`
and configure all recruiter-specific settings.

Test the experiment
-------------------

Before public deployment, test the experiment in each of these modes:

- **Local test:** Run the experiment on your own machine with
  ``psynet debug local``.
- **Docker test:** Run the experiment through the Docker installation to
  confirm that dependencies are captured in ``requirements.txt``.
- **Remote debug:** Run the experiment on the deployment server with
  ``psynet debug ssh``.
- **Hotair:** Share a private testing link (set ``recruiter = hotair``)
  before publishing the experiment to real participants.

For full details on each testing mode, see the
`testing section <general_deployment_process.html#test>`__ of the
General Deployment Process.

Final pre-deployment check
--------------------------

Before running the deployment command:

- Restore the full production version of the experiment if you shortened
  it for testing.
- Confirm that the recruiter configuration has been changed from
  ``hotair`` to the intended live recruiter.
- Check that all recruiter-specific requirements are complete.
- Discuss the payment strategy and confirm the budget. For Prolific,
  make sure the account has enough balance before launching.
