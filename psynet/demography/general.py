from psynet.modular_page import (
    DropdownControl,
    ModularPage,
    NumberControl,
    PushButtonControl,
    RadioButtonControl,
    TextControl,
)
from psynet.timeline import FailedValidation, Module, conditional, join
from psynet.utils import get_country_dict, get_language_dict, get_logger, get_translator

logger = get_logger()

DEFAULT_LOCALE = "en"


class BasicDemography(Module):
    def __init__(
        self,
        locale=DEFAULT_LOCALE,
        label="basic_demography",
    ):
        self.label = label
        self.elts = join(
            Gender(locale=locale),
            Age(locale=locale),
            CountryOfBirth(locale=locale),
            CountryOfResidence(locale=locale),
            FormalEducation(locale=locale),
        )
        super().__init__(self.label, self.elts)


class Language(Module):
    def __init__(
        self,
        label="language",
        locale=DEFAULT_LOCALE,
    ):
        self.label = label
        self.elts = join(
            MotherTongue(locale=locale),
            MoreThanOneLanguage(locale=locale),
            conditional(
                "more_than_one_language",
                lambda experiment, participant: participant.answer == "yes",
                LanguagesInOrderOfProficiency(),
            ),
        )
        super().__init__(self.label, self.elts)


class BasicMusic(Module):
    def __init__(
        self,
        label="basic_music",
        locale=DEFAULT_LOCALE,
    ):
        self.label = label
        self.elts = join(
            YearsOfFormalTraining(locale=locale),
            HoursOfDailyMusicListening(locale=locale),
            MoneyFromPlayingMusic(locale=locale),
        )
        super().__init__(self.label, self.elts)


class Dance(Module):
    def __init__(
        self,
        label="dance",
        locale=DEFAULT_LOCALE,
    ):
        self.label = label
        self.elts = join(
            DanceSociallyOrProfessionally(locale=locale),
            conditional(
                "dance_socially_or_professionally",
                lambda experiment, participant: (
                    participant.answer in ["socially", "professionally"]
                ),
                LastTimeDanced(locale=locale),
            ),
        )
        super().__init__(self.label, self.elts)


class SpeechDisorders(Module):
    def __init__(
        self,
        label="speech_disorders",
        locale=DEFAULT_LOCALE,
    ):
        self.label = label
        self.elts = join(
            SpeechLanguageTherapy(locale=locale),
            DiagnosedWithDyslexia(locale=locale),
        )
        super().__init__(self.label, self.elts)


class Income(Module):
    def __init__(
        self,
        label="income",
        locale=DEFAULT_LOCALE,
    ):
        self.label = label
        self.elts = join(
            HouseholdIncomePerYear(locale=locale),
        )
        super().__init__(self.label, self.elts)


class ExperimentFeedback(Module):
    def __init__(
        self,
        label="feedback",
        locale=DEFAULT_LOCALE,
    ):
        self.label = label
        self.elts = join(
            LikedExperiment(locale=locale),
            FoundExperimentDifficult(locale=locale),
            EncounteredTechnicalProblems(locale=locale),
        )
        super().__init__(self.label, self.elts)


# Basic demography #
class Gender(ModularPage):
    def __init__(
        self,
        label="gender",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        prompt = _p("gender", "How do you identify yourself?")
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = RadioButtonControl(
            ["female", "male", "non_binary", "not_specified", "prefer_not_to_say"],
            [
                _p("gender", "Female"),
                _p("gender", "Male"),
                _p("gender", "Non-binary"),
                _p("gender", "Not specified"),
                _p("gender", "I prefer not to answer"),
            ],
            name="gender",
            show_free_text_option=True,
            placeholder_text_free_text=_p("gender", "Specify yourself"),
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


class Age(ModularPage):
    def __init__(
        self,
        label="age",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.locale = locale
        self.prompt = _p("age", "What is your age?")
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=NumberControl(),
            time_estimate=self.time_estimate,
            save_answer=label,
        )

    def validate(self, response, **kwargs):
        _, _p, _np = get_translator(self.locale)
        answer = response.answer
        error_msg = _p(
            "age",
            "You need to provide your age as an integer between 0 and 120! Your answer was: '{}'",
        ).format(answer)
        try:
            age = int(answer)
            if not (0 < age < 120):
                return FailedValidation(error_msg)
            else:
                return None
        except ValueError:
            return FailedValidation(error_msg)


class CountryDropdown(ModularPage):
    def __init__(self, label, locale):
        self.label = label
        self.locale = locale
        _, _p, _np = self.get_translator()
        self.time_estimate = 5
        country_dict = get_country_dict(locale)
        control = DropdownControl(
            choices=list(country_dict.keys()) + ["OTHER"],
            labels=list(country_dict.values())
            + [_p("country-select", "Other country")],
            default_text=_p("country-select", "Select a country"),
            name=self.label,
        )
        super().__init__(
            self.label,
            self.get_prompt(),
            control=control,
            time_estimate=self.time_estimate,
            save_answer="country",
        )

    def get_translator(self):
        return get_translator(self.locale)

    def get_prompt(self):
        raise NotImplementedError()

    def validate(self, response, **kwargs):
        _, _p, _np = self.get_translator()
        if self.control.force_selection and response.answer == "":
            return FailedValidation(
                _p("country-select", "You need to select a country!")
            )
        return None


class CountryOfBirth(CountryDropdown):
    def __init__(
        self,
        label="country_of_birth",
        locale=DEFAULT_LOCALE,
    ):
        super().__init__(label, locale)

    def get_prompt(self):
        _, _p, _np = self.get_translator()
        return _p("country-select", "What country are you from?")


class CountryOfResidence(CountryDropdown):
    def __init__(
        self,
        label="country_of_residence",
        locale=DEFAULT_LOCALE,
    ):
        super().__init__(label, locale)

    def get_prompt(self):
        _, _p, _np = self.get_translator()
        return _p("country-select", "What is your current country of residence?")


class FormalEducation(ModularPage):
    def __init__(
        self,
        label="formal_education",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "formal-education", "What is your highest level of formal education?"
        )
        self.time_estimate = 5

        control = RadioButtonControl(
            [
                "none",
                "high_school",
                "college",
                "graduate_school",
                "postgraduate_degree_or_higher",
            ],
            [
                _p("formal-education", "None"),
                _p("formal-education", "High school"),
                _p("formal-education", "College"),
                _p("formal-education", "Graduate School"),
                _p("formal-education", "Postgraduate degree or higher"),
            ],
            name="formal_education",
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


# Language #
class MotherTongue(ModularPage):
    def __init__(
        self,
        label="mother_tongue",
        # TODO Change back to plural (add "(s)") once multi-select is implemented.
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.locale = locale
        self.prompt = _p(
            "language-select",
            "What is your mother tongue - i.e., the language which you have grown up speaking from early childhood)?",
        )
        self.time_estimate = 5

        language_dict = get_language_dict(locale)

        control = DropdownControl(
            choices=list(language_dict.keys()) + ["other"],
            labels=list(language_dict.values()) + ["Other language"],
            default_text=_p("language-select", "Select a language"),
            name=self.label,
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )

    def validate(self, response, **kwargs):
        _, _p, _np = get_translator(self.locale)
        if self.control.force_selection and response.answer == "":
            return FailedValidation(
                _p("language-select", "You need to select a language!")
            )
        return None


class MoreThanOneLanguage(ModularPage):
    def __init__(
        self,
        label="more_than_one_language",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p("language-select", "Do you speak more than one language?")
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no"],
            labels=[_("Yes"), _("No")],
            arrange_vertically=False,
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


class LanguagesInOrderOfProficiency(ModularPage):
    def __init__(
        self,
        label="languages_in_order_of_proficiency",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.locale = locale
        self.prompt = (
            _p(
                "language-select",
                "Please list the languages you speak in order of proficiency (first language first, second language second, ...)",
            ),
        )
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(),
            time_estimate=self.time_estimate,
            save_answer=label,
        )

    def validate(self, response, **kwargs):
        _, _p, _np = get_translator(self.locale)
        if not response.answer != "":
            return FailedValidation(
                _p("language-select", "Please list at least one language!")
            )
        return None


# Basic music #
class YearsOfFormalTraining(ModularPage):
    def __init__(
        self,
        label="years_of_formal_training",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = (
            _p(
                "music",
                "How many years of formal training on a musical instrument (including voice) have you had during your lifetime?",
            ),
        )
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=NumberControl(),
            time_estimate=self.time_estimate,
            save_answer=label,
        )


class HoursOfDailyMusicListening(ModularPage):
    def __init__(
        self,
        label="hours_of_daily_music_listening",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "music", "On average, how many hours do you listen to music daily?"
        )
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=NumberControl(),
            time_estimate=self.time_estimate,
            save_answer=label,
        )


class MoneyFromPlayingMusic(ModularPage):
    def __init__(
        self,
        label="money_from_playing_music",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = (_p("music", "Do you make money from playing music?"),)
        self.time_estimate = 5

        control = RadioButtonControl(
            ["frequently", "sometimes", "never"],
            [_p("music", "Frequently"), _p("music", "Sometimes"), _p("music", "Never")],
            name="money_from_playing_music",
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


# Hearing loss #
class HearingLoss(ModularPage):
    def __init__(
        self,
        label="hearing_loss",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "music", "Do you have hearing loss or any other hearing issues?"
        )
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no"],
            labels=[_("Yes"), _("No")],
            arrange_vertically=False,
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


# Dance #
class DanceSociallyOrProfessionally(ModularPage):
    def __init__(
        self,
        label="dance_socially_or_professionally",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p("dance", "Do you dance socially or professionally?")
        self.time_estimate = 5

        control = RadioButtonControl(
            ["socially", "professionally", "never_dance"],
            [
                _p("dance", "Socially"),
                _p("dance", "Professionally"),
                _p("dance", "I never dance"),
            ],
            name="dance_socially_or_professionally",
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


class LastTimeDanced(ModularPage):
    def __init__(
        self,
        label="last_time_danced",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "dance",
            "When was the last time you danced? (choose the most accurate answer):",
        )
        self.time_estimate = 5

        control = RadioButtonControl(
            [
                "this_week",
                "this_month",
                "this_year",
                "some_years_ago",
                "many_years_ago",
                "never_danced",
            ],
            [
                _p("dance", "This week"),
                _p("dance", "This month"),
                _p("dance", "This year"),
                _p("dance", "Some years ago"),
                _p("dance", "Many years ago"),
                _p("dance", "I never danced"),
            ],
            name="last_time_danced",
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


# Speech disorders #
class SpeechLanguageTherapy(ModularPage):
    def __init__(
        self,
        label="speech_language_therapy",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "speech-disorder", "Did you get speech-language therapy as a child?"
        )
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no", "dont_know"],
            labels=[_("Yes"), _("No"), _("I don’t know")],
            arrange_vertically=False,
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


class DiagnosedWithDyslexia(ModularPage):
    def __init__(
        self,
        label="diagnosed_with_dyslexia",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "speech-disorder", "Have you ever been diagnosed with dyslexia?"
        )
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no", "dont_know"],
            labels=[_("Yes"), _("No"), _("I don’t know")],
            arrange_vertically=False,
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


# Income #
class HouseholdIncomePerYear(ModularPage):
    def __init__(
        self,
        label="household_income_per_year",
        currency="USD",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p("income", "What is your total household income per year?")
        self.time_estimate = 5

        control = RadioButtonControl(
            [
                "ĺess_than_10000",
                "10000_to_19999",
                "20000_to_29999",
                "30000_to_39999",
                "40000_to_49999",
                "50000_to_59999",
                "60000_to_69999",
                "70000_to_79999",
                "80000_to_89999",
                "90000_to_99999",
                "100000_to_149999",
                "150000_or_more",
            ],
            [
                _p("income", "Less than 10,000 {}").format(currency),
                _p("income", "10,000 to 19,999 {}").format(currency),
                _p("income", "20,000 to 29,999 {}").format(currency),
                _p("income", "30,000 to 39,999 {}").format(currency),
                _p("income", "40,000 to 49,999 {}").format(currency),
                _p("income", "50,000 to 59,999 {}").format(currency),
                _p("income", "60,000 to 69,999 {}").format(currency),
                _p("income", "70,000 to 79,999 {}").format(currency),
                _p("income", "80,000 to 89,999 {}").format(currency),
                _p("income", "90,000 to 99,999 {}").format(currency),
                _p("income", "100,000 to 149,999 {}").format(currency),
                _p("income", "150,000 {} or more").format(currency),
            ],
            name="household_income_per_year",
        )
        super().__init__(
            self.label,
            self.prompt,
            control=control,
            time_estimate=self.time_estimate,
            save_answer=label,
        )


# ExperimentFeedback #
class LikedExperiment(ModularPage):
    def __init__(
        self,
        label="liked_experiment",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p("experiment-feedback", "Did you like the experiment?")
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(
                bot_response=lambda: "I'm a bot so I don't really have feelings..."
            ),
            time_estimate=self.time_estimate,
            save_answer=label,
        )


class FoundExperimentDifficult(ModularPage):
    def __init__(
        self,
        label="find_experiment_difficult",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "experiment-feedback", "Did you find the experiment difficult?"
        )
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(),
            time_estimate=self.time_estimate,
            bot_response=lambda: "I'm a bot so I found it pretty easy...",
            save_answer=label,
        )


class EncounteredTechnicalProblems(ModularPage):
    def __init__(
        self,
        label="encountered_technical_problems",
        locale=DEFAULT_LOCALE,
    ):
        _, _p, _np = get_translator(locale)
        self.label = label
        self.prompt = _p(
            "experiment-feedback",
            "Did you encounter any technical problems during the experiment? If so, please provide a few words describing the problem.",
        )
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(),
            time_estimate=self.time_estimate,
            bot_response=lambda: "No technical problems.",
            save_answer=label,
        )
