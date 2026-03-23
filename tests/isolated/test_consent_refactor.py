from psynet.consent import (
    LabRecruiterAudiovisualConsent,
    MainConsent,
    PrincetonCAPRecruiterConsent,
    PrincetonLabRecruiterConsent,
)
from psynet.page import RejectedConsentPage
from psynet.timeline import CodeBlock, get_template


def _extract_rejected_consent_kwargs(module):
    rejected_page = next(elt for elt in module.elts if isinstance(elt, RejectedConsentPage))

    class StubExperiment:
        @staticmethod
        def RejectedConsentLogic(**kwargs):
            return kwargs

    return rejected_page.function(StubExperiment())


def _extract_codeblocks(module):
    return [elt for elt in module.elts if isinstance(elt, CodeBlock)]


def test_main_consent_module_configuration():
    consent = MainConsent()

    assert consent.id == "main_consent"
    assert consent.elts[0].template_str == get_template("consents/main_consent.html")
    assert consent.elts[0].format_answer(True) == {"main_consent": True}
    assert consent.elts[0].get_bot_response(None, None) == {"main_consent": True}
    assert _extract_rejected_consent_kwargs(consent) == {
        "failure_tags": ["main_consent_rejected"]
    }
    assert len(_extract_codeblocks(consent)) == 1


def test_lab_recruiter_audiovisual_consent_configuration():
    consent = LabRecruiterAudiovisualConsent()
    page = consent.elts[0]

    assert consent.id == "lab-recruiter_audiovisual_consent"
    assert page.template_str == get_template("consents/cap-recruiter_audiovisual_consent.html")
    assert page.format_answer(
        False, metadata={"demonstration_purposes_consent": True}
    ) == {
        "lab-recruiter_audiovisual_consent": False,
        "demonstration_purposes_consent": True,
    }
    assert page.get_bot_response(None, None) == {
        "lab-recruiter_audiovisual_consent": True,
        "demonstration_purposes_consent": True,
    }
    assert _extract_rejected_consent_kwargs(consent) == {"failure_tags": None}
    assert len(_extract_codeblocks(consent)) == 2


def test_princeton_alias_is_preserved():
    assert PrincetonCAPRecruiterConsent is PrincetonLabRecruiterConsent
