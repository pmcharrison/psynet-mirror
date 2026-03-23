from typing import Optional

from psynet.timeline import CodeBlock

from .page import RejectedConsentPage
from .timeline import Elt, Module, NullElt, Page, conditional, get_template, join


class Consent(Elt):
    """
    Inherit from this class to mark a timeline element as being part of a consent form.
    PsyNet requires you have at least one such element in your timeline,
    to make sure you don't forget to include a consent form.
    See ``LabRecruiterAudiovisualConsentPage`` for an example.
    If you're sure you want to omit the consent form, include a ``NoConsent``
    element in your timeline.
    """

    pass


class NoConsent(Consent, NullElt):
    """
    If you want to have no consent form in your timeline, use this element as an empty placeholder.
    """

    pass


class _ConsentPageBase(Page, Consent):
    template_name: str = ""
    answer_key: str = ""

    def __init__(self, time_estimate: Optional[float] = 30):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template(self.template_name),
        )

    def format_answer(self, raw_answer, **kwargs):
        return {self.answer_key: raw_answer}

    def get_bot_response(self, experiment, bot):
        return {self.answer_key: True}


class _ConsentModuleBase(Module):
    module_label: str = ""
    conditional_label: str = ""
    consent_answer_key: str = ""
    page_class = _ConsentPageBase
    failure_tags = None
    participant_var_map = None

    def __init__(self, time_estimate: Optional[float] = 30):
        page = self.page_class(time_estimate=time_estimate)
        rejection_kwargs = (
            {}
            if self.failure_tags is None
            else {"failure_tags": list(self.failure_tags)}
        )

        def consent_rejected(experiment, participant):
            return not participant.answer[self.consent_answer_key]

        elts = [
            page,
            conditional(
                self.conditional_label,
                consent_rejected,
                RejectedConsentPage(**rejection_kwargs),
            ),
        ]

        mappings = self.participant_var_map or (
            (self.consent_answer_key, self.consent_answer_key),
        )
        for participant_var_key, answer_key in mappings:
            elts.append(
                CodeBlock(self._build_answer_saver(participant_var_key, answer_key))
            )

        super().__init__(self.module_label, join(*elts))

    @staticmethod
    def _build_answer_saver(participant_var_key, answer_key):
        def save_answer(participant):
            participant.var.set(participant_var_key, participant.answer[answer_key])

        return save_answer


#################
# Lab Recruiter #
#################
class LabRecruiterStandardConsent(_ConsentModuleBase):
    """
    The Lab Recruiter standard consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "lab-recruiter_standard_consent"
    conditional_label = "lab-recruiter_standard_consent_conditional"
    consent_answer_key = "lab-recruiter_standard_consent"

    class LabRecruiterStandardConsentPage(_ConsentPageBase):
        """
        This page displays the Lab Recruiter standard consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/cap-recruiter_standard_consent.html"
        answer_key = "lab-recruiter_standard_consent"

    page_class = LabRecruiterStandardConsentPage


class LabRecruiterAudiovisualConsent(_ConsentModuleBase):
    """
    The Lab Recruiter audiovisual recordings consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "lab-recruiter_audiovisual_consent"
    conditional_label = "lab-recruiter_audiovisual_consent_conditional"
    consent_answer_key = "lab-recruiter_audiovisual_consent"
    participant_var_map = (
        ("lab-recruiter_audiovisual_consent", "lab-recruiter_audiovisual_consent"),
        (
            "lab-recruiter_demonstration_purposes_consent",
            "demonstration_purposes_consent",
        ),
    )

    class LabRecruiterAudiovisualConsentPage(_ConsentPageBase):
        """
        This page displays the Lab Recruiter audiovisual consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/cap-recruiter_audiovisual_consent.html"
        answer_key = "lab-recruiter_audiovisual_consent"

        def format_answer(self, raw_answer, **kwargs):
            return {
                "lab-recruiter_audiovisual_consent": raw_answer,
                "demonstration_purposes_consent": kwargs["metadata"][
                    "demonstration_purposes_consent"
                ],
            }

        def get_bot_response(self, experiment, bot):
            return {
                "lab-recruiter_audiovisual_consent": True,
                "demonstration_purposes_consent": True,
            }

    page_class = LabRecruiterAudiovisualConsentPage


# Backward compatibility aliases
CAPRecruiterStandardConsent = LabRecruiterStandardConsent
CAPRecruiterAudiovisualConsent = LabRecruiterAudiovisualConsent


#########
# Lucid #
#########
class LucidConsent(_ConsentModuleBase):
    """
    The Lucid consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "lucid_consent"
    conditional_label = "lucid_consent_conditional"
    consent_answer_key = "lucid_consent"

    class LucidConsentPage(_ConsentPageBase):
        """
        This page displays the Lucid consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/lucid_consent.html"
        answer_key = "lucid_consent"

    page_class = LucidConsentPage


#############
# Princeton #
#############
class PrincetonConsent(_ConsentModuleBase):
    """
    The Princeton University consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "princeton_consent"
    conditional_label = "princeton_consent_conditional"
    consent_answer_key = "princeton_consent"

    class PrincetonConsentPage(_ConsentPageBase):
        """
        This page displays the Princeton University consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/princeton_consent.html"
        answer_key = "princeton_consent"

    page_class = PrincetonConsentPage


class PrincetonLabRecruiterConsent(_ConsentModuleBase):
    """
    The Princeton University consent form to be used in conjunction with Lab Recruiter.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "princeton_lab_recruiter_consent"
    conditional_label = "princeton_lab_recruiter_consent_conditional"
    consent_answer_key = "princeton_lab_recruiter_consent"

    class PrincetonLabRecruiterConsentPage(_ConsentPageBase):
        """
        This page displays the Princeton University consent page to be used in conjunction with Lab Recruiter.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/princeton_lab_recruiter_consent.html"
        answer_key = "princeton_lab_recruiter_consent"

    page_class = PrincetonLabRecruiterConsentPage


# Backward compatibility alias
PrincetonCAPRecruiterConsent = PrincetonLabRecruiterConsent


########
# Main #
########
class MainConsent(_ConsentModuleBase):
    """
    The main consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "main_consent"
    conditional_label = "main_consent_conditional"
    consent_answer_key = "main_consent"
    failure_tags = ("main_consent_rejected",)

    class MainConsentPage(_ConsentPageBase):
        """
        This page displays the main consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/main_consent.html"
        answer_key = "main_consent"

    page_class = MainConsentPage


############
# Database #
############
class DatabaseConsent(_ConsentModuleBase):
    """
    The database consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "database_consent"
    conditional_label = "database_consent_conditional"
    consent_answer_key = "database_consent"
    failure_tags = ("database_consent_rejected",)

    class DatabaseConsentPage(_ConsentPageBase):
        """
        This page displays the database consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/database_consent.html"
        answer_key = "database_consent"

    page_class = DatabaseConsentPage


###############
# Audiovisual #
###############
class AudiovisualConsent(_ConsentModuleBase):
    """
    The audiovisual consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "audiovisual_consent"
    conditional_label = "audiovisual_consent_conditional"
    consent_answer_key = "audiovisual_consent"
    failure_tags = ("audiovisual_consent_rejected",)

    class AudiovisualConsentPage(_ConsentPageBase):
        """
        This page displays the audiovisual consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/audiovisual_consent.html"
        answer_key = "audiovisual_consent"

    page_class = AudiovisualConsentPage


################
# Open science #
################
class OpenScienceConsent(_ConsentModuleBase):
    """
    The open science consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "open_science_consent"
    conditional_label = "open_science_consent_conditional"
    consent_answer_key = "open_science_consent"
    failure_tags = ("open_science_consent_rejected",)

    class OpenScienceConsentPage(_ConsentPageBase):
        """
        This page displays the open science consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/open_science_consent.html"
        answer_key = "open_science_consent"

    page_class = OpenScienceConsentPage


################################################
# Voluntary participation with no compensation #
################################################
class VoluntaryWithNoCompensationConsent(_ConsentModuleBase):
    """
    The voluntary participation with no compensation consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    module_label = "voluntary_with_no_compensation_consent"
    conditional_label = "voluntary_with_no_compensation_consent_conditional"
    consent_answer_key = "voluntary_with_no_compensation_consent"
    failure_tags = ("voluntary_with_no_compensation_consent_rejected",)

    class VoluntaryWithNoCompensationConsentPage(_ConsentPageBase):
        """
        This page displays the voluntary participation with no compensation consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        template_name = "consents/voluntary_with_no_compensation_consent.html"
        answer_key = "voluntary_with_no_compensation_consent"

    page_class = VoluntaryWithNoCompensationConsentPage
