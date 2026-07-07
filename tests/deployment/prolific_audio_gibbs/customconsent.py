from typing import Optional

from psynet.consent import Consent
from psynet.page import RejectedConsentPage
from psynet.timeline import CodeBlock, Module, Page, conditional, join


class CustomMainConsent(Module):
    """
    The main consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        label = "main_consent"
        elts = join(
            self.MainConsentPage(),
            conditional(
                "main_consent_conditional",
                lambda experiment, participant: not participant.answer["main_consent"],
                RejectedConsentPage(failure_tags=["main_consent_rejected"]),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "main_consent", participant.answer["main_consent"]
                )
            ),
        )
        super().__init__(label, elts)

    class MainConsentPage(Page, Consent):
        """
        This page displays the main consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            with open("templates/custom_main_consent.html", "r") as f:
                template_str = f.read()
            super().__init__(time_estimate=time_estimate, template_str=template_str)

        def format_answer(self, raw_answer, **kwargs):
            return {"main_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"main_consent": True}
