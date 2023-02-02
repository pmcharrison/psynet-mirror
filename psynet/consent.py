from typing import Optional

from psynet.timeline import CodeBlock

from .page import RejectedConsentPage
from .timeline import Elt, Module, NullElt, Page, conditional, get_template, join


class Consent(Elt):
    """
    Inherit from this class to mark a timeline element as being part of a consent form.
    PsyNet requires you have at least one such element in your timeline,
    to make sure you don't forget to include a consent form.
    See ``CAPRecruiterAudiovisualConsentPage`` for an example.
    If you're sure you want to omit the consent form, include a ``NoConsent``
    element in your timeline.
    """

    pass


class NoConsent(Consent, NullElt):
    """
    If you want to have no consent form in your timeline, use this element as an empty placeholder.
    """

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
                    not participant.answer["cap-recruiter_standard_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "cap-recruiter_standard_consent",
                    participant.answer["cap-recruiter_standard_consent"],
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
                template_str=get_template(
                    "consents/cap-recruiter_standard_consent.html"
                ),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"cap-recruiter_standard_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {
                "cap-recruiter_standard_consent": True,
            }


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
                    not participant.answer["cap-recruiter_audiovisual_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "cap-recruiter_audiovisual_consent",
                    participant.answer["cap-recruiter_audiovisual_consent"],
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
                template_str=get_template(
                    "consents/cap-recruiter_audiovisual_consent.html"
                ),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {
                "cap-recruiter_audiovisual_consent": raw_answer,
                "demonstration_purposes_consent": kwargs["metadata"][
                    "demonstration_purposes_consent"
                ],
            }

        def get_bot_response(self, experiment, bot):
            return {
                "cap-recruiter_audiovisual_consent": True,
                "demonstration_purposes_consent": True,
            }


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
                lambda experiment, participant: (
                    not participant.answer["princeton_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "princeton_consent", participant.answer["princeton_consent"]
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
                template_str=get_template("consents/princeton_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"princeton_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"princeton_consent": True}


class PrincetonCAPRecruiterConsent(Module):
    """
    The Princeton University consent form to be used in conjunction with CAP-Recruiter.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "princeton_cap_recruiter_consent"
        self.elts = join(
            self.PrincetonCAPRecruiterConsentPage(),
            conditional(
                "princeton_cap_recruiter_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["princeton_cap_recruiter_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "princeton_cap_recruiter_consent",
                    participant.answer["princeton_cap_recruiter_consent"],
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class PrincetonCAPRecruiterConsentPage(Page, Consent):
        """
        This page displays the Princeton University consent page to be used in conjunction with CAP-Recruiter.

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
                template_str=get_template(
                    "consents/princeton_cap_recruiter_consent.html"
                ),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"princeton_cap_recruiter_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"princeton_cap_recruiter_consent": True}


########
# Main #
########
class MainConsent(Module):
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
        self.label = "main_consent"
        self.elts = join(
            self.MainConsentPage(),
            conditional(
                "main_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["main_consent"]
                ),
                RejectedConsentPage(failure_tags=["main_consent_rejected"]),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "main_consent", participant.answer["main_consent"]
                )
            ),
        )
        super().__init__(self.label, self.elts)

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
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("consents/main_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"main_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"main_consent": True}


############
# Database #
############
class DatabaseConsent(Module):
    """
    The database consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "database_consent"
        self.elts = join(
            self.DatabaseConsentPage(),
            conditional(
                "database_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["database_consent"]
                ),
                RejectedConsentPage(failure_tags=["database_consent_rejected"]),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "database_consent", participant.answer["database_consent"]
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class DatabaseConsentPage(Page, Consent):
        """
        This page displays the database consent page.

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
                template_str=get_template("consents/database_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"database_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"database_consent": True}


###############
# Audiovisual #
###############
class AudiovisualConsent(Module):
    """
    The audiovisual consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "audiovisual_consent"
        self.elts = join(
            self.AudiovisualConsentPage(),
            conditional(
                "audiovisual_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["audiovisual_consent"]
                ),
                RejectedConsentPage(failure_tags=["audiovisual_consent_rejected"]),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "audiovisual_consent", participant.answer["audiovisual_consent"]
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class AudiovisualConsentPage(Page, Consent):
        """
        This page displays the audiovisual consent page.

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
                template_str=get_template("consents/audiovisual_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"audiovisual_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"audiovisual_consent": True}


################
# Open science #
################
class OpenScienceConsent(Module):
    """
    The open science consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "open_science_consent"
        self.elts = join(
            self.OpenScienceConsentPage(),
            conditional(
                "open_science_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["open_science_consent"]
                ),
                RejectedConsentPage(failure_tags=["open_science_consent_rejected"]),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "open_science_consent", participant.answer["open_science_consent"]
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class OpenScienceConsentPage(Page, Consent):
        """
        This page displays the open science consent page.

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
                template_str=get_template("consents/open_science_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"open_science_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"open_science_consent": True}


################################################
# Voluntary participation with no compensation #
################################################
class VoluntaryWithNoCompensationConsent(Module):
    """
    The voluntary participation with no compensation consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        self.label = "voluntary_with_no_compensation_consent"
        self.elts = join(
            self.VoluntaryWithNoCompensationConsentPage(),
            conditional(
                "voluntary_with_no_compensation_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["voluntary_with_no_compensation_consent"]
                ),
                RejectedConsentPage(
                    failure_tags=["voluntary_with_no_compensation_consent_rejected"]
                ),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "voluntary_with_no_compensation_consent",
                    participant.answer["voluntary_with_no_compensation_consent"],
                )
            ),
        )
        super().__init__(self.label, self.elts)

    class VoluntaryWithNoCompensationConsentPage(Page, Consent):
        """
        This page displays the voluntary participation with no compensation consent page.

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
                template_str=get_template(
                    "consents/voluntary_with_no_compensation_consent.html"
                ),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"voluntary_with_no_compensation_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"voluntary_with_no_compensation_consent": True}
