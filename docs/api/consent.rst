=======
Consent
=======

Most experiments should implement a custom consent flow.
The built-in classes in :mod:`psynet.consent` are mainly convenience wrappers
for specific institutional/recruiter templates and are often not a good fit for
external projects.

How PsyNet checks consent
-------------------------

PsyNet expects at least one timeline element that inherits from
:class:`~psynet.consent.Consent`.
The consent element can be any page type, including
:class:`~psynet.page.InfoPage` or :class:`~psynet.modular_page.ModularPage`.

If your experiment intentionally has no consent step, include
:class:`~psynet.consent.NoConsent` as an explicit placeholder.

Custom consent patterns (in increasing complexity)
--------------------------------------------------

1) Minimal implicit consent with a single ``InfoPage``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from psynet.consent import Consent
    from psynet.page import InfoPage


    class SimpleConsentPage(InfoPage, Consent):
        def __init__(self):
            super().__init__(
                "By clicking 'Next' you confirm that you have read the consent information and agree to participate.",
                time_estimate=20,
            )

This is the shortest approach and avoids custom Jinja templates entirely.
It is appropriate when continuing in the timeline is sufficient to indicate consent.

2) Explicit accept/reject consent using built-in page primitives
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from psynet.consent import Consent
    from psynet.modular_page import ModularPage, PushButtonControl
    from psynet.page import RejectedConsentPage
    from psynet.timeline import CodeBlock, Module, conditional, join


    class ExplicitConsentPage(ModularPage, Consent):
        def __init__(self):
            super().__init__(
                label="explicit_consent",
                prompt="Do you consent to participate in this study?",
                control=PushButtonControl(["I agree", "I do not agree"]),
                time_estimate=20,
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"custom_consent": raw_answer == "I agree"}

        def get_bot_response(self, experiment, bot):
            return {"custom_consent": True}


    class ExplicitConsent(Module):
        def __init__(self):
            super().__init__(
                "explicit_consent_module",
                join(
                    ExplicitConsentPage(),
                    conditional(
                        "custom_consent_check",
                        lambda participant: not participant.answer["custom_consent"],
                        RejectedConsentPage(),
                    ),
                    CodeBlock(
                        lambda participant: participant.var.set(
                            "custom_consent",
                            participant.answer["custom_consent"],
                        )
                    ),
                ),
            )

This keeps everything in Python and provides an explicit rejection path.

3) Multi-page consent flow with richer formatting
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from markupsafe import Markup
    from psynet.page import InfoPage
    from psynet.timeline import join

    consent_flow = join(
        InfoPage(
            "Welcome. Please read the following consent details carefully.",
            time_estimate=8,
        ),
        InfoPage(
            Markup(
                "<h4>Data use</h4>"
                "<p>Your responses will be used for research purposes only.</p>"
                "<p>You may withdraw at any time before submission.</p>"
            ),
            time_estimate=20,
        ),
        ExplicitConsent(),
    )

Only one element in the sequence must inherit from
:class:`~psynet.consent.Consent` (in this example ``ExplicitConsentPage``).

Built-in classes (reference)
----------------------------

Built-ins are still available and documented for completeness, but most users
should prefer a custom implementation following one of the patterns above.

.. automodule:: psynet.consent
    :members: Consent, NoConsent
    :show-inheritance:
