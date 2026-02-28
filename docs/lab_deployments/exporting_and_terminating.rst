Exporting & Terminating
=======================

🛑 Export data
--------------------

You can export the data using following command:

.. code:: bash

   psynet export ssh --app <APP_NAME> --server <SERVER> --path <PATH_TO_STORE_YOUR_DATA>

For example:

.. code:: bash

   psynet export ssh --app color-exp --server elif.cap-experiments.com --path /Users/elif.celen/Experiments/color

🔹 Export script 
----------------

In the group we like to have a file called export.py which contains:

-  Sanity checks

-  Export of demographic information

-  Export of the raw results to some preprocessed format, and

-  Preliminary plots of the main results

🛑 Sanity checks 
^^^^^^^^^^^^^^^^

These checks are very important because it allows us to determine
problems from early on and in case of error allows to abort the
experiment without receiving many complaints and paying many
participants.

Checks you must implement are:

-  Are time estimates set properly? -> e.g. make a histogram over the
      time it took to do trials

-  Do people progress fully through the experiment?

-  Do people do the required number of people do your trials? If people
      should do 60 trials, you should get 60 trials per participants

Try to use assertions for those sanity checks.

Export demographic information
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Read the required demographic information from the data, e.g. age and
gender from Participant.

Export of the raw results
^^^^^^^^^^^^^^^^^^^^^^^^^

Export your data to an output format you can use for plotting. E.g. save
a CSV you can import in Matlab or R.

Preliminary plot
^^^^^^^^^^^^^^^^

Make some preliminary plots to make sure you see the trend in the data.
If the results are very unexpected try to identify what can cause the
effect.

.. _best-practices-1:

Best practices
^^^^^^^^^^^^^^

Export regularly and run your export.py script. This way you can detect
problems from early on.

🛑 Export once more
-------------------

After you made sure that the experiment is completed export the data one
last time.

In a new version of PsyNet, your logs will be downloaded automatically
upon exporting. You will also see an automatic analysis of the log file.

.. _section-5:

🔹 Additional manual export in case of large assets
----------------------------------------------------------------------

| In case you are experiencing trouble exporting large assets using
  psynet export, you can also try to zip and export the assets manually
  from the ssh server. Take note that the assets will not have the same
  nice cleaned names as when exported via psynet export ssh!
| To do this manual export of the assets:

-  ssh to the server as explained in `SSH into the
   instance <provisioning.html#ssh-into-the-instance>`__

-  then you create a tar.gz of the assets folder on the server, by
      running in the terminal:

.. code:: bash

   tar -czvf $HOME/namefile.tar.gz $HOME/psynet-data/assets

-  leave the server, and on your local pc download this tar.gz by
      running in the terminal:

.. code:: bash

   scp -p 22 ubuntu@<SERVER_URL>:/home/ubuntu/namefile.tar.gz ~/Downloads

   to download the tar.gz file to your local Downloads folder (replace
   <SERVER_URL> by your servers URL)
