Troubleshooting
===============

**Q**: Help, I can’t access my server anymore!

| **A**: Try re-adding your pem file to your ssh keygen by running:
| ``ssh-add -K ~/.ssh/cap.pem``

**Q**: I get this error after running ``psynet debug ssh`` or
``psynet deploy ssh``. What
should I do?

.. code:: text

   docker.errors.DockerException: Error while fetching server API version:
   ('Connection aborted.', ConnectionRefusedError(61, 'Connection refused'))

**A**: You should make sure Docker Desktop is running.

**Q:** When debugging, I obtain the following (similar) error:

.. code:: text

   docker.errors.DockerException: Error while fetching server API
   version: ('Connection aborted.', PermissionError(13, 'Permission denied'))

**A**: Changing permissions to the docker socket appears to have
resolved this issue for me.

**Q:** Port 5000 is already used

**A:** Disable Airdrop receiver

Alternatively stop another experiment that is running in another window
or pycharm project window. To kill all running python you can write
*killall Python* or *killall python* in the terminal window.

**Q:** My server restarted and my experiment is not running anymore.

**A:** All experiments are stored under ~/dallinger. You can cd into
this directory and cd into the experiment folder. You can now run docker
compose which will restart your experiment docker container.

**Q:** How to compensate a participant who was timed out by Prolific and
is complaining?

**A:** cap prolific approve <study_id> <participant_id>

**Q:** I'm unable to connect to my AWS EC2 instance via SSH; the
connection times out. How can I resolve this issue and regain access to
my server?

A: The timeout error you're receiving often indicates a networking or
internal system issue on the instance that can be resolved with a
reboot. Please follow these steps to reboot:

1. Install AWS CLI

2. Configure it with credentials etc: aws configure

3. Find the instance ID, e.g. from the .. code:: bash

   dallinger ec2 list instances
      command

4. Reboot instance: aws ec2 reboot-instances --instance-ids
      <INSTANCE_ID>

**Q:** A

**A:** A

Things to discuss
-----------------

-  Which server should be used?

-  How many participants should take the experiment at the same time?

-  [STRIKEOUT:Why are we not using prolific version of auto recruit?]

-  [STRIKEOUT:What are the important config params?]

-  [STRIKEOUT:Where to get the prolific_qualifications_en.json ?]

-  How to safely transfer cap.pem and dallingerconfig to new lab
      members?

-  What is our payment strategy?

-  How to use dozzle? How to interpret total CPU usage? Is it ok if it
      spikes above 100%? What are the containers?

-  naming conventions of server, app

-  [STRIKEOUT:reporting of experiment. Will this be automated?]

-  [STRIKEOUT:exporting data while participants are still taking the
      experiment may cause errors [?]]

.. _section-15:

.. |image1| image:: /_static/images/lab_deployments/image19.png
   :width: 2.5in
.. |image2| image:: /_static/images/lab_deployments/image50.png
   :width: 8.5in
.. |image3| image:: /_static/images/lab_deployments/image22.png
   :width: 8.5in
.. |image4| image:: /_static/images/lab_deployments/image33.png
   :width: 8.5in
.. |image5| image:: /_static/images/lab_deployments/image5.png
   :width: 8.5in
.. |image6| image:: /_static/images/lab_deployments/image45.png
   :width: 8.5in
