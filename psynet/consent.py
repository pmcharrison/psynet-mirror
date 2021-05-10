from typing import Optional

from .timeline import Page, get_template


class CAPRecruiterStandardConsentPage(Page):
    """
    This page displays a standard consent page for participants entering from the CAP-Recruiter website.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 10,
        **kwargs,
    ):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("cap-recruiter_standard_consent.html"),
            **kwargs,
        )

    def format_answer(self, raw_answer, **kwargs):
        return {"standard_consent": True}


class CAPRecruiterAudiovisualConsentPage(Page):
    """
    This page displays a audiovisual recordings consent page for participants entering from the CAP-Recruiter website.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 10,
        **kwargs,
    ):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("cap-recruiter_audiovisual_consent.html"),
            **kwargs,
        )

    def format_answer(self, raw_answer, **kwargs):
        return {
            "audiovisual_consent": True,
            "demonstration_purposes_consent": kwargs["metadata"][
                "demonstration_purposes_consent"
            ],
        }


class PrincetonConsentPage(Page):
    """
    This page displays the consent page for the Griffiths lab at Princeton University.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
        **kwargs,
    ):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("princeton_consent.html"),
            **kwargs,
        )

    def format_answer(self, raw_answer, **kwargs):
        return {"consent": True}


class MTurkStandardConsentPage(Page):
    """
    This page displays the standard consent page.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
        **kwargs,
    ):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("mturk_standard_consent.html"),
            **kwargs,
        )

    def format_answer(self, raw_answer, **kwargs):
        return {"standard_consent": True}


class MTurkAudiovisualConsentPage(Page):
    """
    This page displays the audiovisual recordings consent page.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 10,
        **kwargs,
    ):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("mturk_audiovisual_consent.html"),
            **kwargs,
        )

    def format_answer(self, raw_answer, **kwargs):
        return {"audiovisual_consent": True}
