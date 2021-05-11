from typing import Optional

from .page import RejectedConsentPage
from .timeline import Module, Page, conditional, get_template, join


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
        self.events = join(
            CAPRecruiterStandardConsentPage(),
            conditional(
                "cap-recruiter_standard_consent_conditional",
                lambda experiment, participant: (
                    "standard_consent" not in participant.answer
                    or participant.answer["standard_consent"] is not True
                ),
                RejectedConsentPage(),
            ),
        )
        super().__init__(self.label, self.events)


class CAPRecruiterStandardConsentPage(Page):
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
        self.events = join(
            CAPRecruiterAudiovisualConsentPage(),
            conditional(
                "cap-recruiter_audiovisual_consent_conditional",
                lambda experiment, participant: (
                    "audiovisual_consent" not in participant.answer
                    or participant.answer["audiovisual_consent"] is not True
                ),
                RejectedConsentPage(),
            ),
        )
        super().__init__(self.label, self.events)


class CAPRecruiterAudiovisualConsentPage(Page):
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
        self.events = join(
            MTurkStandardConsentPage(),
            conditional(
                "mturk_standard_consent_conditional",
                lambda experiment, participant: (
                    "standard_consent" not in participant.answer
                    or participant.answer["standard_consent"] is not True
                ),
                RejectedConsentPage(),
            ),
        )
        super().__init__(self.label, self.events)


class MTurkStandardConsentPage(Page):
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
        self.events = join(
            MTurkAudiovisualConsentPage(),
            conditional(
                "mturk_audiovisual_consent_conditional",
                lambda experiment, participant: (
                    "audiovisual_consent" not in participant.answer
                    or participant.answer["audiovisual_consent"] is not True
                ),
                RejectedConsentPage(),
            ),
        )
        super().__init__(self.label, self.events)


class MTurkAudiovisualConsentPage(Page):
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
        self.events = join(
            PrincetonConsentPage(),
            conditional(
                "princeton_consent_conditional",
                lambda experiment, participant: (
                    "consent" not in participant.answer
                    or participant.answer["consent"] is not True
                ),
                RejectedConsentPage(),
            ),
        )
        super().__init__(self.label, self.events)


class PrincetonConsentPage(Page):
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
