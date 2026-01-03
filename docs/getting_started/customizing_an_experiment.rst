Customizing an experiment
=========================

The best way to get a feel for PsyNet experiment development is to start with an existing demo
and try and customize it in various ways.
Have a look through the available demos in the ``demos`` directory of the PsyNet repository,
then choose one as your starting point.
Copy the demo's directory to a new location on your computer, outside the original PsyNet repository.

Now, you want to open a new Dev Container for this new experiment,
following the same process described in :ref:`running_locally`.

1. Open the new experiment directory in your IDE
2. Follow the prompt to launch a Dev Container
3. Wait until the automatic configuration scripts have stopped running
4. You can then launch the experiment by running `psynet debug local` in the terminal

This works because each demo directory contains its own ``Dockerfile`` and ``.devcontainer`` directory,
which is used to define the Dev Container environment.

You can now start modifying the experiment to your liking.
Try some simple modifications to begin with, for example changing the text of the questions.
If you're feeling confident, you can try some more complex modifications.
For ideas, you can browse the other demos, or browse the PsyNet documentation,
or ask Cursor to help you (but encourage it to look at the PsyNet source code rather than just guessing)

Simple modifications, such as changing text, can be done without restarting the experiment.
Simply edit the code in your IDE, save the file, and refresh the browser.
More complex modifications, such as changing the stimuli, will require you to restart the experiment.
To do this, you will need to stop the experiment by pressing Ctrl+C in the terminal,
then restart it by running ``psynet debug local`` again.

.. note::

    Sometimes you might want to customize another experiment that exists outside the PsyNet repository.
    The general principle is the same, but you might have a bit more work to do if the experiment was written
    for an older version of PsyNet.
    In most cases you should try and update the experiment to use the latest version of PsyNet.

    Have a look at `PsyNet's CHANGELOG <https://gitlab.com/PsyNetDev/PsyNet/-/blob/master/CHANGELOG.md?ref_type=heads>`_
    to see what has changed in PsyNet since the experiment was written.
    If the experiment repository does not contain a ``.devcontainer`` directory,
    you will need to copy one from a PsyNet demo, as well as the related ``Dockerfile``.
    You'll then want to update the ``requirements.txt`` file to use the latest version of PsyNet
    (you can see the latest released version in the top-left corner of the online documentation website),
    and then run ``psynet generate-constraints`` to update ``constraints.txt`` accordingly,
    and then rebuild your Dev Container (CMD+Shift+P > Rebuild Container).

    Once this is all done, try running ``psynet debug local`` -- you might encounter some errors on account of your version upgrade,
    but hopefully the error message will guide you towards what needs fixing.
