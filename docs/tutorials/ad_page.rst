.. _AdPage:

===========
The Ad Page
===========

The way that the experiment is advertised to participants depends on the recruitment method.

Generic recruiter
-----------------

The 'generic' recruiter is used for experiments that are not integrated with a crowdsourcing provider.
In such cases, participants simply navigate to the experiment via a pre-specified link.
In this case PsyNet does not display an ad to the participant.

Prolific
--------

Prolific participants see an ad in their Prolific interface. This ad looks something like this:

.. image:: ../_static/images/prolific/ad_example.png
  :alt: Prolific ad example

The content of this ad is initially populated by PsyNet with reference to your experiment config,
in particular fields like ``title``, ``config``, ``wage_per_hour``, and so on.
You can customize the content via the Prolific interface.

MTurk and CAP-Recruiter
-----------------------

With MTurk and CAP-Recruiter the ad page is hosted by PsyNet itself.
This ad page is again initially populated by PsyNet with reference to your experiment config,
but can be customized by editing methods of the ``Experiment`` class, as detailed below.

**1. General description of the experiment**

    Add a description using the `description` keyword in the experiment's `config.txt` file, e.g.:

        *description = The <span style="font-style: italic;">Max Planck Insitute for Empirical Aesthetics</span> is looking for online
        participants for a brief psychology experiment.<br>In this experiment, you will listen
        to sounds and answer questions.*

    You can make use of HTML's style attribute to adapt the text's appearance as shown in the above example.

**2. Requirements**

    Five default requirements are added automatically. These are:

    .. raw:: html

        <ul style="font-style: italic;">
            <li>The experiment can only be performed using a <span style="font-weight: bold;">laptop</span> (desktop computers are not allowed).</li>
            <li>You should use an <span style="font-weight: bold;">updated Google Chrome</span> browser.</li>
            <li>You should be sitting in a <span style="font-weight: bold;">quiet environment</span>.</li>
            <li>You should be at least <span style="font-weight: bold;">18 years old</span>.</li>
            <li>You should be a <span style="font-weight: bold;">fluent English speaker</span>.</li>
        </ul>

    More requirements can be added, e.g. by augmenting your experiment class with the following code:

    ::

        @property
        def ad_requirements(self):
            return super().ad_requirements + [
                'You must be wearing <span style="font-weight: bold;">headphones</span> and sitting in a quiet place.'
            ]

    Organize requirements according to your needs by using custom Python code.

**3. Payment information**

    The following payment information text will be rendered by default unless amended (or completely overriden)
    in the experiment class:

    .. raw:: html

        <span style="font-style: italic;">
            We estimate that the task should take approximately <span style="font-weight: bold;">n minutes</span>. Upon completion of the full task,
            <br>
            you should receive a reward of approximately
            <span style="font-weight: bold;">$x.yz</span> depending on the
            amount of work done.
            <br>
            In some cases, the experiment may finish early: this is not an error, and there is no need to write to us.
            <br>
            In this case you will be paid in proportion to the amount of the experiment that you completed.
        </span>
        <br><br>

    You could add another line of text using this code, e.g.:

    ::

        @property
        def ad_payment_information(self):
            return super().ad_payment_information
            + '<br>Send us your <span style="font-weight: bold;">bank account information</span> to receive refunds.'

    Again, you can make use of HTML's style attribute to adapt the text's appearance to your needs.

.. note::
    To completely override the appearance of the ad page you can add an `ad.html` file to the `templates` directory of your experiment.
