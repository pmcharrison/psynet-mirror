Massive Deployments 
====================

(Deploying Multiple Experiments in Parallel)

- This specific implementation, designed by Pol, is currently available
  only in the development version of the framework: **psynet==13.0.0rc1**.

- Pin this version in your project's requirements.txt file and generate
  constraints for dependency management.

**Monitoring Real-Time Experiment Data: The basic_data Endpoint**
-----------------------------------------------------------------

Overview and Utility: Why Use **get_basic_data**?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The basic_data endpoint is a powerful feature designed to provide
**real-time access** to your experiment's data during deployment,
eliminating the need for constant manual data exports.

The core utility lies in the **get_basic_data** method you implement
within your experiment class. When deployed, this method exposes the
data through a dedicated, easily accessible **URL** (e.g.,
http://127.0.0.1:5000/basic_data?...).

**Key Benefits:**

-  **Real-Time Data Access:** You can access the most up-to-date
      experiment data without interrupting the deployment or running a
      separate export process.

-  **Easy Data Loading:** The URL allows you to load the experiment data
      directly into your analysis environment (like **Pandas** in Python
      or a **dataframe** in R) using standard library functions
      (pd.read_json, jsonlite::fromJSON).

-  **Monitoring:** This is especially useful when dealing with
      **multiple batches**. By leveraging **GET parameters** in the URL,
      you can easily switch between different views or batches of data
      (e.g., checking data for Batch A vs. Batch B) using the same
      framework.

-  **Custom Sanity Checks:** The accessible URL enables you to write
      your own automated scripts to continuously load the data and
      perform **sanity checks** (e.g., monitoring data quality, checking
      response distributions, looking for suspicious activity, or
      confirming the experiment is progressing as expected).

Implementation of the Experiment Method (**get_basic_data**)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To use the /basic_data endpoint in your experiment, you need to
implement the get_basic_data method in your experiment class. The method
should return a list of dictionaries with the data you want to expose.
You can make this method as complex as you need. For example, you can
add GET parameters to the endpoint, e.g. /basic_data?sheet=participant
which allows to switch between different data sheets.

.. code:: python

   class Exp(psynet.experiment.Experiment):
       ...

       @classmethod
       def get_basic_data(cls, context=None, **kwargs):
           data = {
               "trial": [
                   # List all trials with their answers
                   {"id": trial.id, "answer": str(trial.answer)}
                   for trial in Trial.query.filter_by(failed=False, finalized=True).all()
               ],
               "participant": [
                   # List all participants with their last answer
                   {"id": participant.id, "answer": str(participant.answer)}
                   for participant in Participant.query.filter_by().all()
               ],
           }

           sheet = kwargs.get("sheet", "participant")
           if sheet not in data:
               raise DataError("Invalid sheet parameter")

           return data[sheet]

-  The data defined in your get_basic_data method is accessible
      in two ways: **via the Deployment Dashboard** and **directly via
      the Data URL**. When your experiment is running, you can easily
      view the structure and content of the exposed data by navigating
      to the **"Basic data"** tab on the dashboard. This page provides a
      Data URL and a Data preview pane, letting you instantly inspect
      the returned data and test different parameters. For automated
      monitoring, you can use the Data URL directly in analysis scripts
      (like pd.read_json(url)) to load the live data into a dataframe
      and run your custom sanity checks.

-  R Example:

..

   library(jsonlite)

   url <-
   "http://127.0.0.1:5000/basic_data?dashboard_user=cap&dashboard_password=capcapcap2021!"

   df <- fromJSON(url)

-  Python Example:

   .. code:: python

      import pandas as pd

      url = "http://127.0.0.1:5000/basic_data?dashboard_user=cap&dashboard_password=capcapcap2021!"
      df = pd.read_json(url)

.. image:: /_static/images/lab_deployments/image25.png
   :width: 8.5in

.. _section-3:

.. _section-4:

**Monitoring All Experiments at Once: Deployment Monitor**
----------------------------------------------------------

The deployment monitor provides a single, unified dashboard to
view and manage all your running and past experiment deployments. This
feature is crucial when running simultaneous experiments, as it
transforms complicated individual monitoring into a simple, automated
process.

**How to Use the Interface**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This monitor allows you to quickly assess the progress and
performance of every deployment at a glance:

1. **At-a-Glance Statistics:** For every deployment, you
      immediately see essential statistics, including:

   -  **Recruitment Status:** Whether the experiment is actively
         recruiting.

   -  **Runtime & Duration:** How long the experiment has been
         running and its estimated completion time.

   -  **Cost & Compensation:** The financial metrics associated
         with participant recruitment.

   -  **Participants & Errors:** The number of participants
         recruited and any recorded server errors.

2. **Filtering Deployments:** You can easily manage the
      complexity of multiple deployments using the filter menus at the
      top of the page. This allows you to quickly isolate groups of
      experiments based on recruiter, recruitment status, label and
      network status.

3. **Quick Shortcuts:** The shortcuts column on the right
      provides quick access to critical deployment tools. Here are some
      actions you can take:

   -  **URLs to data endpoint, dashboard, server (e.g., Dozzle),
      etc.:** Direct links to monitor server logs and performance,
      and more.

   -  **Export:** A shortcut to download the latest data for that
         specific deployment.

   -  **Notes:** An easy way to add, edit, or view important
         contextual notes about that deployment.

In short, the deployment monitor centralizes all deployment
information, making it simple to check the entire pipeline's status,
troubleshoot issues, and access data without navigating away from one
page. You can access it through the dashboard in the ‘Deployments’ tab.

.. image:: /_static/images/lab_deployments/image44.png
   :width: 8.5in

**Slack Integration: Real-Time Deployment Alerts** 
---------------------------------------------------

Integrate with Slack to get **instant, real-time alerts** for
your deployments. This is highly useful when you have multiple
simultaneous deployments. The PsyNet Bot automatically sends crucial
updates to the deployments channel.

**Configuration Steps**
^^^^^^^^^^^^^^^^^^^^^^^

1. **Join the Channel:** The PsyNet Bot reports to the central
      channel. Ask Elif to add you to the #deployments channel to
      receive notifications.

2. **Update the config in experiment.py**: Add the “notifier”:
      “slack” setting to your ‘config’,

..

   config = {

   "notifier": "slack",}

3. **Update ~/.dallingerconfig:** Add the following to your
   ``.dallingerconfig`` file:

   .. code:: ini

      [Slack]
      slack_channel_name = deployments
      slack_bot_token = <see cap safe>
      experimenter_name = <your name>

   .. note::

      Make sure your ``experimenter_name`` matches your name on Slack.

**Usage**
^^^^^^^^^

+---------+------------------------------------------------------------+
| Event   | Benefit & Actions                                          |
| R       |                                                            |
| eported |                                                            |
| by      |                                                            |
| PsyNet  |                                                            |
+=========+============================================================+
| Exp     | Instant Visibility: You're notified immediately when an    |
| eriment | experiment launches (including ID and URL). The alert      |
| started | includes the experiment dashboard link and login           |
| (and    | credentials for quick access.                              |
| cred    |                                                            |
| entials |                                                            |
| for     |                                                            |
| das     |                                                            |
| hboard) |                                                            |
+---------+------------------------------------------------------------+
| Recr    | Critical Alerts: Messages are sent for changes in the      |
| uitment | experiment's recruitment status (e.g., transition from     |
| updates | Recruiting to Taken down or Complete).                     |
+---------+------------------------------------------------------------+
| Error   | Critical Alerts: Receive immediate messages for errors.    |
| o       |                                                            |
| ccurred |                                                            |
+---------+------------------------------------------------------------+
| Exp     | Quick Access & Actions: The final completion status is     |
| eriment | noted. Every thread allows for quick actions, such as      |
| f       | manually exporting data, directly from the Slack thread.   |
| inished |                                                            |
+---------+------------------------------------------------------------+

By default such notifications will only occur when an experiment
is deployed (i.e. \\``psynet deploy\\`), not when it is run
locally in debug mode (i.e. \``\`psynet debug\\`). However, to
trial the Slack notification service locally, you can run \``\`psynet
deploy local\`.`
