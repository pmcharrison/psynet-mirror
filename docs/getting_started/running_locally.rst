.. _running_locally:

Running PsyNet locally
======================

Installation
------------

PsyNet has detailed installation instructions in the :doc:`installation section <../installation/index>`.
Follow the appropriate instructions for your operating system,
then follow the instructions below to check your setup.

Launch a PsyNet demo
--------------------

PsyNet contains many demo experiments in the ``demos`` directory.
These are organized into two main subdirectories: ``demos/experiments`` and ``demos/features``.

To run a demo, you first need to navigate to it in the terminal.
The following code navigates to the 'timeline' demo:

.. code-block:: bash

    cd demos/timeline

Now you can launch the demo using the following command:

.. code-block:: bash

    psynet debug local

You will need to wait a few seconds for the demo to start.
You may see one or more pop-ups asking whether you want to open an external website;
you should say Yes to these.

If everything works properly, you should see two web pages.
One is a participant interface, looking something like this:

.. image:: ../getting_started/images/participant-interface.png
    :alt: Screenshot showing a participant interface in a PsyNet demo.
    :class: bordered
    :align: center
    :width: 600px

The other is an admin interface, looking something like this:

.. image:: ../getting_started/images/admin-interface.png
    :alt: Screenshot showing an admin interface in a PsyNet demo.
    :class: bordered
    :align: center
    :width: 600px

You can now interact with the demo as if you were a participant.
If you want to start a second participant session, you can do this via the admin interface,
clicking the 'New participant' button on the 'Development' tab.

You can also use the admin interface to view the data collected from the participants.
Try taking a few pages of the experiment, then refresh the admin interface,
then click 'Database', and explore the available data types.
