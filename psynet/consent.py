from typing import Optional

from psynet.timeline import CodeBlock

from .page import RejectedConsentPage
from .timeline import Elt, Module, NullElt, Page, conditional, get_template, join


class Consent(Elt):
    pass


class NullConsent(Consent, NullElt):
    pass


#################
# CAP-Recruiter #
#################
class CAPRecruiterStandardConsent(Module):
    """
    The CAP-Recruiter standard consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "cap-recruiter_standard_consent"
        self.elts = join(
            self.CAPRecruiterStandardConsentPage(),
            conditional(
                "cap-recruiter_standard_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["standard_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "cap-recruiter_standard_consent",
                    participant.answer["standard_consent"],
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class CAPRecruiterStandardConsentPage(Page, Consent):
        """
        This page displays the CAP-Recruiter standard consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("cap-recruiter_standard_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"standard_consent": raw_answer}


class CAPRecruiterAudiovisualConsent(Module):
    """
    The CAP-Recruiter audiovisual recordings consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "cap-recruiter_audiovisual_consent"
        self.elts = join(
            self.CAPRecruiterAudiovisualConsentPage(),
            conditional(
                "cap-recruiter_audiovisual_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["audiovisual_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "cap-recruiter_audiovisual_consent",
                    participant.answer["audiovisual_consent"],
                )
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "cap-recruiter_demonstration_purposes_consent",
                    participant.answer["demonstration_purposes_consent"],
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class CAPRecruiterAudiovisualConsentPage(Page, Consent):
        """
        This page displays the CAP-Recruiter audiovisual consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("cap-recruiter_audiovisual_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {
                "audiovisual_consent": raw_answer,
                "demonstration_purposes_consent": kwargs["metadata"][
                    "demonstration_purposes_consent"
                ],
            }


#########
# MTurk #
#########
class MTurkStandardConsent(Module):
    """
    The MTurk standard consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "mturk_standard_consent"
        self.elts = join(
            self.MTurkStandardConsentPage(),
            conditional(
                "mturk_standard_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["standard_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "mturk_standard_consent", participant.answer["standard_consent"]
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class MTurkStandardConsentPage(Page, Consent):
        """
        This page displays the MTurk standard consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("mturk_standard_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"standard_consent": raw_answer}


class MTurkAudiovisualConsent(Module):
    """
    The MTurk audiovisual recordings consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "mturk_audiovisual_consent"
        self.elts = join(
            self.MTurkAudiovisualConsentPage(),
            conditional(
                "mturk_audiovisual_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["audiovisual_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "mturk_audiovisual_consent",
                    participant.answer["audiovisual_consent"],
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class MTurkAudiovisualConsentPage(Page, Consent):
        """
        This page displays the MTurk audiovisual consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("mturk_audiovisual_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"audiovisual_consent": raw_answer}


#############
# Princeton #
#############
class PrincetonConsent(Module):
    """
    The Princeton University consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "princeton_consent"
        self.elts = join(
            self.PrincetonConsentPage(),
            conditional(
                "princeton_consent_conditional",
                lambda experiment, participant: (not participant.answer["consent"]),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "princeton_consent", participant.answer["consent"]
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class PrincetonConsentPage(Page, Consent):
        """
        This page displays the Princeton University consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("princeton_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"consent": raw_answer}


##############
# No consent #
##############
class NoConsent(Module):
    """
    An invisible consent for experiments without the need for the participant to give explicit consent.
    """

    def __init__(
        self,
        time_estimate=0,
    ):
        self.label = "no_consent"
        self.elts = join(NullConsent())
        super().__init__(self.label, self.elts)
