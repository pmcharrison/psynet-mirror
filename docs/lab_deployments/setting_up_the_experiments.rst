Setting Up the Experiments
==========================

Before deploying your experiment, you need to complete basic setup steps
that apply to all deployments. Most details, including specific
recruiter instructions, are covered in the
:doc:`Recruiter-Specific Deployment Steps <recruiter_specific_deployment_steps>`
section, so this page provides only the essential steps.

1) Define Experiment Configuration

   a. Ensure **all required parameters** are set (consent, title,
         description, payment, completetion time, participant size).

   b. run psynet estimate in the terminal to get estimated completion
         time and compensation.

   c. Use **appropriate storage (S3 or LocalStorage)** instead of
         DebugStorage.

2) Choose a Recruiter

   a. `Prolific <recruiter_specific_deployment_steps.html#prolific>`__,
      `CINT <recruiter_specific_deployment_steps.html#cint-lucid>`__, or
      `Lab Recruiter <recruiter_specific_deployment_steps.html#lab-recruiter>`__
      — each has different setup steps.

   b. Configure the recruiter-specific settings after reading
      :doc:`Recruiter-Specific Deployment Steps <recruiter_specific_deployment_steps>`.

3) Test Your Experiment

   a. **Local test:** Run it on your machine first.

   b. **Hotair:** Use a private testing link before public deployment.

4) Final Check Before Deployment

   a. Verify that all steps recommended in your chosen recruiter’s
         section are followed.

   b. Discuss the payment strategy. Ensure you have enough balance on
      `Prolific <recruiter_specific_deployment_steps.html#prolific>`__
      before launching.
