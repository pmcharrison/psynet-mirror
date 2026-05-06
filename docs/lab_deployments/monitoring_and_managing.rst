Monitoring & Managing
=====================

Once your experiment is deployed, continuous monitoring is essential to
ensure smooth data collection, handle participant issues, and optimize
recruitment.

This section provides general guidelines. Recruiter-specific details
(Prolific, CINT, Lab Recruiter) can be found in their
:doc:`respective sections <recruiter_specific_deployment_steps>`.

Using the Dashboard
-------------------

The experiment dashboard is your main tool for tracking and managing the
study. It is the same for each recruiter. The URL is printed in the
terminal after the deployment command (see
`Deploying <deploying.html#actual-deployment>`__).

Key features:

-  **Monitoring Tab:** View networks, nodes, parameters, and participant
   answers. Click shapes for details.

-  **Timeline Tab:** Track participant counts, completions, and
   failures. Also, see all the modules in your experiment and
   completion percentages.

-  **Database Tab:** View or export data via the Export Tab.

Monitoring Participants & Data Collection
-----------------------------------------

-  Track participant progress and look for dropouts or errors.

-  Use **Dozzle logs** for real-time debugging. Regularly check for
   error messages in logs and fix critical issues immediately. The
   Dozzle URL is available at ``logs.<your-subdomain>.<your-domain>``
   (see `Provisioning <provisioning.html#provisioning>`__).

-  Monitor Prolific/CINT marketplaces for recruiter-specific insights.

Participant Issues
------------------

Participants may contact you directly when they encounter errors.

Where participants may contact you:

-  **Prolific:** Via the Prolific messaging system. Participants can
   contact you through Prolific messages, so check messages regularly
   and respond in a timely manner.

-  **CINT:** Currently not possible through the platform.

-  **Lab Recruiter:** Via email sent to the address configured in your
   lab's Lab Recruiter setup.

Recruitment and Payment Strategies
------------------------------------

-  Start with a small recruitment batch (5–10 participants) and review
   data quality before increasing participation. After these initial
   participants have finished, check that there are no errors and that
   your time estimate for the experiment is accurate.

-  Regularly increase recruitment size manually rather than relying on
   auto-recruit for the entire study.

-  Adjust wage per hour and completion time estimates based on actual
   participant behavior.

-  If you are using auto-recruit, stop it before reaching the final
   stages to prevent excess costs.
