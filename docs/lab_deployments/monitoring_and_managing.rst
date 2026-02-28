Monitoring & Managing 
======================

Once your experiment is deployed, continuous monitoring is essential to
ensure smooth data collection, handle participant issues, and optimize
recruitment. If you cannot do it yourself (e.g., due to time-zone
issues), you can contact Nori or Elif for help.

This section provides general guidelines, while recruiter-specific
details (Prolific, CINT, Lab Recruiter) can be found in their respective
sections.

🛑 Using the Dashboard 
----------------------

The experiment dashboard is your main tool for tracking and managing the
study. It is the same for each recruiter. It is printed on the terminal
after the deployment command (how to find the `dashboard
link <#actual-deployment>`__).

Key Features:

-  **Monitoring Tab:** View networks, nodes, parameters, and participant
      answers. Click shapes for details.

-  **Timeline Tab:** Track participant counts, completions, and
      failures. Also, see all the modules in your experiment and
      completion percentages.

-  **Database Tab:** View or export data via the Export Tab.

🛑 Monitoring Participants & Data Collection 
--------------------------------------------

-  Track participant progress (dropouts or errors).

-  Use **Dozzle logs** for real-time debugging. Regularly check for
      error messages in logs and fix critical issues immediately. (how
      to find the `dozzle link <#provisioning>`__)

-  Monitor Prolific/CINT marketplaces for recruiter-specific insights.

🛑 Participant Issues 
---------------------

Participants might directly contact you in some cases of errors and
issues.

Where Participants May Contact You:

-  **Prolific:** Via the Prolific messaging system.

-  **CINT:** currently not possible.

-  **Lab Recruiter:** Emails sent to coco-experiments@cornell.edu.

Messages in gmail account 
^^^^^^^^^^^^^^^^^^^^^^^^^^

It might also be the case that participants will text you on the group’s
gmail account computational.audition@gmail.com (you can find the
credential in cap-safe). It could be that your login has to be verified
through some further authentication. In that case, contact Nori for
help. This was an important mode of communication in the past but rarely
happens now.

When you are done with a message, move the message to the “Done”
subfolder. Sometimes, you will see emails, which contain bills and are
not related to your experiment. These mails should be moved to the
“accounts” subfolder.

🛑 Recruitment and Payment Strategies 
-------------------------------------

-  Start with a small recruitment batch (5-10 participants) and review
      data quality before increasing participation. After all these
      initial participants have finished the experiment, you should
      check that you do not get any errors and that your initial time
      estimate for the experiment is accurate.

-  Regularly increase recruitment size manually instead of relying on
      auto-recruit for the entire study.

-  Adjust wage per hour and completion time estimates based on actual
      participant behavior.

-  If you are using auto-recruit, stop it before reaching the final
      stages to prevent excess costs.
