from typing import Optional

import flask

from .page import InfoPage
from .timeline import get_template


class StandardConsentPage(InfoPage):
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
        time_estimate: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            content=flask.Markup(get_template("standard_consent.html")),
            time_estimate=time_estimate,
            show_next_button=False,
            **kwargs,
        )


class AudiovisualRecordingsConsentPage(InfoPage):
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
        time_estimate: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            content=flask.Markup(get_template("audiovisual_recordings_consent.html")),
            time_estimate=time_estimate,
            show_next_button=False,
            **kwargs,
        )
