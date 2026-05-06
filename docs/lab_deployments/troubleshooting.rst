Troubleshooting
===============

**Q**: I cannot access my server anymore.

**A**: Try re-adding your PEM key to your SSH agent by running:

.. code:: bash

   ssh-add -K ~/.ssh/<your-key-name>.pem

Replace ``<your-key-name>`` with the name of your PEM file (e.g., the
file configured in your ``~/.dallingerconfig``).

----

**Q**: I get this error after running ``psynet debug ssh`` or
``psynet deploy ssh``. What should I do?

.. code:: text

   docker.errors.DockerException: Error while fetching server API version:
   ('Connection aborted.', ConnectionRefusedError(61, 'Connection refused'))

**A**: Make sure Docker Desktop is running.

----

**Q**: When debugging, I get the following error:

.. code:: text

   docker.errors.DockerException: Error while fetching server API
   version: ('Connection aborted.', PermissionError(13, 'Permission denied'))

**A**: Changing permissions to the Docker socket has resolved this issue
in the past.

----

**Q**: Port 5000 is already in use.

**A**: Disable AirDrop receiver on macOS. Alternatively, stop any other
experiment running in another terminal or PyCharm window. To kill all
running Python processes you can run:

.. code:: bash

   killall python

or

.. code:: bash

   killall Python

----

**Q**: My server restarted and my experiment is no longer running.

**A**: All experiments are stored under ``~/dallinger``. SSH into the
server, navigate to the experiment directory, and run
``docker compose up`` to restart the experiment containers.

----

**Q**: I am unable to connect to my AWS EC2 instance via SSH; the
connection times out.

**A**: A timeout often indicates a networking or internal system issue
that can be resolved with a reboot. Steps:

1. Install the AWS CLI.

2. Configure it with your credentials:

   .. code:: bash

      aws configure

3. Find the instance ID:

   .. code:: bash

      dallinger ec2 list instances

4. Reboot the instance:

   .. code:: bash

      aws ec2 reboot-instances --instance-ids <INSTANCE_ID>

----

**Q**: The launch appears stuck at "Launching experiment" for more than
a few minutes.

**A**: Inspect the Dozzle logs for HTTP server errors. A common cause
is that ``nip.io`` has hit a quota limit and is refusing to provide an
HTTPS address. Other common causes include an invalid server name or
incorrect recruiter parameters. If the terminal does not show a clear
error, the Dozzle logs usually contain a more useful message.

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
