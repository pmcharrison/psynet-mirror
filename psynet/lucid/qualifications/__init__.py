import json
import os
from typing import List

from markupsafe import Markup

from psynet.log import bold, red
from psynet.lucid import get_lucid_service
from psynet.lucid.qualifications.questions import get_custom_qualifications
from psynet.modular_page import Control, ModularPage
from psynet.recruiters import get_lucid_country_language_id
from psynet.utils import get_logger, get_translator


def create_lucid_recruitment_config(
    language_tag,
    country_tag,
    question_answer_dict,
    use_headphones: bool,
    use_microphone: bool,
    config_path=None,
    allow_mobile_devices: bool = None,
    force_google_chrome: bool = None,
    unique_ip: bool = True,
    unique_pid: bool = True,
    industry_id: int = 30,
    study_type_id: int = 1,
    debug: bool = True,
    qualifications_dict=None,
):
    """
    Create a Lucid recruitment config.
    Parameters
    ----------
    language_tag: str, 3-letter lanugage name, NOT an ISO language tag, if you specify a wrong language tag, the Lucid
    API will tell you which ones are available.
    country_tag: str, 2-letter country code, NOT an ISO country code, if you specify a wrong country tag, the Lucid API
    will tell you which ones are available.
    question_answer_dict: dict, a dictionary with question names as keys and a list of allowed answers as values. The
    question names must occur in CUSTOM_QUALIFICATIONS_LUCID.
    use_headphones: bool, whether the participant must use headphones
    use_microphone: bool, whether the participant must use a microphone
    config_path: str, default None, if None, it will return the config as a dictionary, if a path is specified, it will
    allow_mobile_devices: bool, default None, if None, it will be taken from the config file
    force_google_chrome: bool, default None, if None, it will be taken from the config file
    unique_ip: bool, default True, whether the participant must have a unique IP
    unique_pid: bool, default True, whether the participant must have a unique PID
    industry_id: int, default 30, which is the default for "Other", pick from:
    {
     '1': 'Automotive',
     '2': 'Beauty/Cosmetics',
     '3': 'Beverages - Alcoholic',
     '4': 'Beverages - Non Alcoholic',
     '5': 'Education',
     '6': 'Electronics/Computer/Software',
     '7': 'Entertainment (Movies, Music, TV, etc)',
     '8': 'Fashion/Clothing',
     '9': 'Financial Services/Insurance',
     '10': 'Food/Snacks',
     '11': 'Gambling/Lottery',
     '12': 'Healthcare/Pharmaceuticals',
     '13': 'Home (Utilities, Appliances, ...)',
     '14': 'Home Entertainment (DVD, VHS)',
     '15': 'Home Improvement/Real Estate/Construction',
     '16': 'IT (Servers, Databases, etc)',
     '17': 'Personal Care/Toiletries',
     '18': 'Pets',
     '19': 'Politics',
     '20': 'Publishing (Newspaper, Magazines, Books)',
     '21': 'Restaurants',
     '22': 'Sports',
     '23': 'Telecommunications (phone, cell phone, cable)',
     '24': 'Tobacco (Smokers)',
     '25': 'Toys',
     '26': 'Transportation/Shipping',
     '27': 'Travel',
     '28': 'Video Games',
     '29': 'Websites/Internet/E-Commerce',
     '30': 'Other',
     '31': 'Sensitive Content',
     '32': 'Explicit Content'
    }
    study_type_id: int, default 1, which is the default for "Adhoc", pick from:
    {
     '1': 'Adhoc',
     '2': 'Diary',
     '5': 'IHUT',
     '8': 'Community Build',
     '9': 'Face to Face',
     '11': 'Recruit - Panel',
     '13': 'Tracking - Monthly',
     '14': 'Tracking - Quarterly',
     '15': 'Tracking - Weekly',
     '16': 'Wave Study',
     '17': 'Qualitative Screening',
     '18': 'Internal Use',
     '21': 'Incidence Check',
     '22': 'Recontact',
     '23': 'Ad Effectiveness Research',
     '24': 'Proof Exposed',
     '25': 'Proof Control'
     }
    debug: bool, default True, whether to print debug information, i.e. see the translations of the qualifications

    Returns
    -------

    """
    from psynet.experiment import get_and_load_config

    logger = get_logger()
    config = get_and_load_config()
    service = get_lucid_service(config=config)

    if qualifications_dict is None:
        qualifications_dict = service.get_qualifications_dict()

    country_language_id = get_lucid_country_language_id(
        country_tag, language_tag, service=service
    )

    qualifications = []

    if allow_mobile_devices is None:
        allow_mobile_devices = config.get("allow_mobile_devices")

    if allow_mobile_devices:
        qualifications.append(
            {
                "Name": "MS_is_mobile",
                "QuestionID": 8214,
                "LogicalOperator": "NOT",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 1,
                "PreCodes": ["true"],
            }
        )
        qualifications.append(
            {
                "Name": "MS_is_tablet",
                "QuestionID": 8213,
                "LogicalOperator": "NOT",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 1,
                "PreCodes": ["true"],
            }
        )

    if force_google_chrome is None:
        force_google_chrome = config.get("force_google_chrome")

    if force_google_chrome:
        qualifications.append(
            {
                "Name": "MS_browser_type_Non_Wurfl",
                "QuestionID": 1035,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 2,
                "PreCodes": ["Chrome"],
            }
        )

    question_answer_dict["TIMEOUT"] = ["Agree"]
    if use_headphones:
        question_answer_dict["HEADPHONE"] = ["Yes, I can play audio"]
    if use_microphone:
        question_answer_dict["MICROPHONE"] = ["Yes, I can record audio"]

    for question_name, options in question_answer_dict.items():
        if question_name not in qualifications_dict:
            raise ValueError(f"Unknown question {question_name}.")
        question_id = qualifications_dict[question_name]
        english_option_df = service.get_answer_options(question_id)
        option_df = english_option_df.query("text in @options")
        assert (
            len(option_df) > 0
        ), f"Question {question_name} does not have specified options: {options}. Make sure to pick from: {english_option_df.text.tolist()}."
        precodes = option_df.precode.tolist()
        qualifications.append(
            {
                "Name": question_name,
                "QuestionID": question_id,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": len(options),
                "IsActive": True,
                "PreCodes": precodes,
            }
        )

        foreign_locale = f"{language_tag}_{country_tag}"
        try:
            foreign_option_df = service.get_answer_options(question_id, foreign_locale)
        except AssertionError:
            raise AssertionError(
                bold(
                    red(f"Could not find question {question_name} in {foreign_locale}.")
                )
                + " "
                + "Make sure it exists: https://www.samplicio.us/fulcrum/Questions.aspx"
            )

        foreign_selected_option_df = foreign_option_df.query("precode in @precodes")
        english_selected_option_df = english_option_df.query("precode in @precodes")
        assert len(foreign_selected_option_df) == len(
            english_selected_option_df
        ), f"Foreign options for question {question_name} do not match English options. English: {english_selected_option_df.text.tolist()} -> Foreign: {foreign_selected_option_df.text.tolist()}"
        foreign_question = service.get_question_name(question_id, foreign_locale)

        english_question = service.get_question_name(question_id)
        if debug:
            logger.info(
                bold(
                    f"Question {question_name} ({question_id}): {service.default_locale.upper()} -> {foreign_locale.upper()}"
                )
            )
            print(
                bold("English")
                + f": '{english_question}' => {english_selected_option_df.text.tolist()}"
            )
            print(
                bold("Foreign")
                + f": '{foreign_question}' => {foreign_selected_option_df.text.tolist()}"
            )
    lucid_recruitment_config = {
        "survey": {
            "CountryLanguageID": country_language_id,
            # Following API documentation: To ensure Suppliers have access to the Survey when it is set live,
            # set the following parameters:
            # FulcrumExchangeAllocation: 0
            # FulcrumExchangeHedgeAccess: true
            "FulcrumExchangeAllocation": 0,
            "FulcrumExchangeHedgeAccess": True,
            "IndustryID": industry_id,
            "StudyTypeID": study_type_id,
            "UniqueIPAddress": unique_ip,
            "UniquePID": unique_pid,
        },
        "qualifications": qualifications,
        "country": country_tag,
        "language": language_tag,
    }
    if config_path is not None:
        with open(config_path, "w") as f:
            json.dump(lucid_recruitment_config, f, indent=4)
    else:
        return lucid_recruitment_config


def _lucid_dict_printer(d, indent, base_indent):
    out = []
    out.append("{")
    for key, question_dict in d.items():
        out.append(f'{indent}"{key}": ' + "{")
        out.append(f'{indent*2}"question": _p("{key}", "{question_dict["question"]}"),')
        out.append(f'{indent*2}"options": [')
        for option in question_dict["options"]:
            out.append(f'{indent*3}_p("{key}", "{option}"),')
        out.append(f"{indent*2}],")
        out.append(f"{indent}}},")
    out.append("}")
    return "\n".join([base_indent + line for line in out])


def prepare_qualifications():
    service = get_lucid_service()
    lookup = service.get_lucid_country_language_lookup()
    question_dict = {}
    for _, row in lookup.iterrows():
        language = row["language_name"]
        country = row["country_name"]
        language_tag = row["language_tag"]
        country_tag = row["country_tag"]
        suffix = f"{language_tag}_{country_tag}"
        question_dict[f"BIRTH_{suffix}"] = {
            "question": f"Were you born in {country}?",
            "options": [
                f"Yes, I was born in {country}",
                "No, I was born in another country",
            ],
        }
        question_dict[f"NATIVE_{suffix}"] = {
            "question": f"Is your first language {language}?",
            "options": [
                f"Yes, {language} is my first language",
                "No, have a different first language",
            ],
        }
        question_dict[f"NATIONALITY_{suffix}"] = {
            "question": "What is your nationality?",
            "options": [f"I am from {country}", "I have a different nationality"],
        }
    here = os.path.abspath(os.path.dirname(__file__))
    indent = "  "
    with open(f"{here}/questions.py", "w") as f:
        out = '"""\n'
        out += "This file is automatically generated by prepare_qualifications()\n"
        out += '"""\n'
        out += "from psynet.utils import get_translator\n"
        out += "\n"
        out += "def get_custom_qualifications(locale):\n"
        out += indent + '"""\n'
        out += indent + "Get custom qualifications for Lucid for a specific locale.\n"
        out += indent + '"""\n'
        out += indent + "_, _p = get_translator(locale)\n"
        out += indent + f"return {_lucid_dict_printer(question_dict, indent, indent)}\n"
        f.write(out)


class LucidTerminateControl(Control):
    """
    This control presents a list of buttons. If the participant clicks a not allowed button, the experiment is
    terminated. This can be used for screening within the experiment.

    """

    macro = "terminate_control"

    def __init__(
        self,
        choices: List[str],
        labels: List[str],
        allowed: List[str],
        page_label: str,
        css_class_per_option: List[str],
        arrange_vertically: bool = True,
    ):
        super().__init__()
        assert all([choice in choices for choice in allowed])
        assert all(
            [
                all([char.islower() or char == "-" for char in choice])
                for choice in choices
            ]
        ), "All choices must be lowercase letters. Special characters are not allowed except '-'."
        self.items = [
            {
                "label": labels[i],
                "allowed": choice in allowed,
                "id": choice,
                "class": css_class_per_option[i],
            }
            for i, choice in enumerate(choices)
        ]
        self.label = page_label
        self.arrange_vertically = arrange_vertically

    @property
    def metadata(self):
        return self.__dict__


class LucidScreeningQuestion(ModularPage):
    def __init__(
        self,
        label,
        question,
        choices,
        labels,
        allowed,
        time_estimate,
        arrange_vertically=False,
        base_css_class="btn btn-primary btn-lg mx-2",
        css_class_per_option=None,
        aggressive_termination_on_no_focus=True,
    ):
        assert len(choices) == len(labels)
        if css_class_per_option is None:
            css_class_per_option = [base_css_class] * len(choices)
        assert len(css_class_per_option) == len(choices)
        css_class_per_option = [
            base_css_class + " " + style for style in css_class_per_option
        ]
        super().__init__(
            label=label,
            prompt=Markup(question),
            control=LucidTerminateControl(
                choices=choices,
                labels=labels,
                allowed=allowed,
                page_label=label,
                arrange_vertically=arrange_vertically,
                css_class_per_option=css_class_per_option,
            ),
            time_estimate=time_estimate,
            show_next_button=False,
            show_termination_button=False,
            aggressive_termination_on_no_focus=aggressive_termination_on_no_focus,
        )


class LucidTwoForcedChoiceQualification(LucidScreeningQuestion):
    def __init__(
        self,
        label,
        question,
        labels,
        choices=None,
        allowed=None,
        time_estimate=2,
        css_class_per_option=None,
    ):
        if choices is None:
            choices = ["yes", "no"]
            css_class_per_option = ["btn-success", "btn-danger"]

        assert (
            css_class_per_option is not None
        ), "If you provide custom choices, you must also provide custom css classes"

        if allowed is None:
            allowed = ["yes"]
        assert all(
            [choice in choices for choice in allowed]
        ), f"Allowed choices must be in {choices}"
        super().__init__(
            label=label,
            question=question,
            choices=choices,
            labels=labels,
            allowed=allowed,
            time_estimate=time_estimate,
            css_class_per_option=css_class_per_option,
        )


class LucidTimeoutQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, locale, time_estimate=5):
        _, _p = get_translator(locale)
        super().__init__(
            label="TIMEOUT",
            question=_p(
                "lucid_qualifications_timeout",
                "This survey requires you to stay on the website. "
                "When you switch tabs or leave the window, your participation will be terminated earlier. "
                'If you wish to end the survey earlier, please press the "early termination" button provided on each '
                "survey page. "
                "Please note that early termination will not result in compensation.",
            ),
            labels=[
                _p("lucid_qualifications_timeout", "Yes, I agree"),
                _p("lucid_qualifications_timeout", "No, I do not agree"),
            ],
            time_estimate=time_estimate,
        )


class LucidAudioQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, locale, time_estimate=5, allowed=None):
        if allowed is None:
            allowed = ["yes"]
        _, _p = get_translator(locale)
        super().__init__(
            label="HAS_AUDIO",
            question=_p(
                "lucid_qualifications_audio",
                "To complete this survey, you will be asked to listen to audio. "
                "Can you listen to audio on the current device?",
            ),
            labels=[
                _p("lucid_qualifications_audio", "Yes"),
                _p("lucid_qualifications_audio", "No"),
            ],
            allowed=allowed,
            time_estimate=time_estimate,
        )


class LucidHeadphoneQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, locale, time_estimate=5, allowed=None):
        if allowed is None:
            allowed = ["yes"]
        _, _p = get_translator(locale)
        super().__init__(
            label="HAS_HEADPHONE",
            question=_p(
                "lucid_qualifications_headphone",
                "To complete this survey, you will be asked to listen to audio using headphones. "
                "Do you have headphones available?",
            ),
            labels=[
                _p("lucid_qualifications_headphone", "Yes"),
                _p("lucid_qualifications_headphone", "No"),
            ],
            allowed=allowed,
            time_estimate=time_estimate,
        )


class LucidMicrophoneQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, locale, time_estimate=5, allowed=None):
        if allowed is None:
            allowed = ["yes"]
        _, _p = get_translator(locale)
        super().__init__(
            label="HAS_MICROPHONE",
            question=_p(
                "lucid_qualifications_microphone",
                "To complete this survey, you need a microphone. You may not use a wireless microphone (such as "
                + "Bluetooth headphones). Do you have a microphone available?",
            ),
            labels=[
                _p("lucid_qualifications_microphone", "Yes"),
                _p("lucid_qualifications_microphone", "No"),
            ],
            allowed=allowed,
            time_estimate=time_estimate,
        )


class LucidInQuietPlaceQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, locale, time_estimate=5, allowed=None):
        if allowed is None:
            allowed = ["yes"]
        _, _p = get_translator(locale)
        super().__init__(
            label="IN_QUIET_PLACE",
            question=_p(
                "lucid_qualifications_in_quiet_place",
                "To complete this survey, you need to be in a quiet place. Ideally, you should be in a room with no "
                "background noise, and you should not be disturbed by other people or pets. Are you in a quiet place?",
            ),
            labels=[
                _p("lucid_qualifications_in_quiet_place", "Yes"),
                _p("lucid_qualifications_in_quiet_place", "No"),
            ],
            allowed=allowed,
            time_estimate=time_estimate,
        )


class LucidAllowVoiceRecordingQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, locale, time_estimate=5, allowed=None):
        if allowed is None:
            allowed = ["yes"]
        _, _p = get_translator(locale)
        super().__init__(
            label="ALLOW_VOICE_RECORDING",
            question=_p(
                "lucid_qualifications_allow_voice_recording",
                "In this experiment, you will be asked to record your voice. All the recordings we obtain during this "
                "research will be kept confidential, and nobody outside the group of researchers will be able to share "
                "or store them. Your recordings will not be associated with your name or other identifiers in any way. "
                "Your recordings will not be used to derive your real identity, and they will not be made public. "
                "Are you willing to record your voice?",
            ),
            labels=[
                _p("lucid_qualifications_allow_voice_recording", "Yes"),
                _p("lucid_qualifications_allow_voice_recording", "No"),
            ],
            allowed=allowed,
            time_estimate=time_estimate,
        )


class LucidMonolingualismQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, locale, time_estimate=2):
        _, _p = get_translator(locale)
        super().__init__(
            label="MONOLINGUALISM",
            question=_p(
                "lucid_qualifications_monolingualism",
                "Were you raised monolingual?",
            ),
            labels=[
                _p(
                    "lucid_qualifications_monolingualism",
                    "I was raised with my native language only",
                ),
                _p(
                    "lucid_qualifications_monolingualism",
                    "I was raised with two or more languages",
                ),
            ],
            time_estimate=time_estimate,
        )


class LucidLocaleSpecificQualification(LucidTwoForcedChoiceQualification):
    def __init__(self, question_id, language_tag, country_tag, locale):
        key = f"{question_id}_{language_tag}_{country_tag}"
        custom_qualifications_lucid = get_custom_qualifications(locale)
        assert key in custom_qualifications_lucid, f"Unknown key {key}."
        question_dict = custom_qualifications_lucid[key]
        super().__init__(
            label=key,
            question=question_dict["question"],
            labels=question_dict["options"],
            time_estimate=2,
        )


class LucidNativeQualification(LucidLocaleSpecificQualification):
    def __init__(self, language_tag, country_tag, locale):
        super().__init__(
            question_id="NATIVE",
            language_tag=language_tag,
            country_tag=country_tag,
            locale=locale,
        )


class LucidNationalityQualification(LucidLocaleSpecificQualification):
    def __init__(self, language_tag, country_tag, locale):
        super().__init__(
            question_id="NATIONALITY",
            language_tag=language_tag,
            country_tag=country_tag,
            locale=locale,
        )


class LucidBirthQualification(LucidLocaleSpecificQualification):
    def __init__(self, language_tag, country_tag, locale):
        super().__init__(
            question_id="BIRTH",
            language_tag=language_tag,
            country_tag=country_tag,
            locale=locale,
        )
