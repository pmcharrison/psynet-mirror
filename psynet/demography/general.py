from psynet.modular_page import (
    DropdownControl,
    ModularPage,
    NumberControl,
    PushButtonControl,
    RadioButtonControl,
    TextControl,
)
from psynet.timeline import FailedValidation, Module, conditional, join
from psynet.utils import get_logger, get_translator

logger = get_logger()


class BasicDemography(Module):
    def __init__(
        self,
        label="basic_demography",
    ):
        self.label = label
        self.elts = join(
            Gender(),
            Age(),
            CountryOfBirth(),
            CountryOfResidence(),
            FormalEducation(),
        )
        super().__init__(self.label, self.elts)


class Language(Module):
    def __init__(
        self,
        label="language",
    ):
        self.label = label
        self.elts = join(
            MotherTongue(),
            MoreThanOneLanguage(),
            conditional(
                "Does the participant speak more than one language?",
                lambda experiment, participant: participant.answer == "yes",
                LanguagesInOrderOfProficiency(),
            ),
        )
        super().__init__(self.label, self.elts)


class BasicMusic(Module):
    def __init__(
        self,
        label="basic_music",
    ):
        self.label = label
        self.elts = join(
            YearsOfFormalTraining(),
            HoursOfDailyMusicListening(),
            MoneyFromPlayingMusic(),
        )
        super().__init__(self.label, self.elts)


class Dance(Module):
    def __init__(
        self,
        label="dance",
    ):
        self.label = label
        self.elts = join(
            DanceSociallyOrProfessionally(),
            conditional(
                "dance_socially_or_professionally",
                lambda experiment, participant: (
                    participant.answer in ["socially", "professionally"]
                ),
                LastTimeDanced(),
            ),
        )
        super().__init__(self.label, self.elts)


class SpeechDisorders(Module):
    def __init__(
        self,
        label="speech_disorders",
    ):
        self.label = label
        self.elts = join(
            SpeechLanguageTherapy(),
            DiagnosedWithDyslexia(),
        )
        super().__init__(self.label, self.elts)


class Income(Module):
    def __init__(
        self,
        label="income",
    ):
        self.label = label
        self.elts = join(
            HouseholdIncomePerYear(),
        )
        super().__init__(self.label, self.elts)


class ExperimentFeedback(Module):
    def __init__(
        self,
        label="feedback",
    ):
        self.label = label
        self.elts = join(
            LikedExperiment(),
            FoundExperimentDifficult(),
            EncounteredTechnicalProblems(),
        )
        super().__init__(self.label, self.elts)


# Basic demography #
class Gender(ModularPage):
    def __init__(
        self,
        label="gender",
        prompt="What is your gender?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = RadioButtonControl(
            ["male", "female", "other", "prefer_not_to_say"],
            ["Male", "Female", "Other", "Prefer not to say"],
            name="gender",
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class Age(ModularPage):
    def __init__(
        self,
        label="age",
        prompt="What is your age?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=NumberControl(),
            time_estimate=self.time_estimate,
        )

    @staticmethod
    def validate(response, **kwargs):
        if not (
            0 < response.answer < 120
            and round(response.answer) == float(response.answer)
        ):
            return FailedValidation(
                "You need to provide your age as an integer between 0 and 120!"
            )
        return None


class CountryOfBirth(ModularPage):
    def __init__(self, label="country_of_birth", prompt="What country are you from?"):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = DropdownControl(
            choices=[country[0] for country in countries()] + ["OTHER"],
            labels=[country[1] for country in countries()] + ["Other country"],
            default_text="Select a country",
            name=self.label,
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )

    def validate(self, response, **kwargs):
        if self.control.force_selection and response.answer == "":
            return FailedValidation("You need to select a country!")
        return None


class CountryOfResidence(ModularPage):
    def __init__(
        self,
        label="country_of_residence",
        prompt="What is your current country of residence?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = DropdownControl(
            choices=[country[0] for country in countries()] + ["OTHER"],
            labels=[country[1] for country in countries()] + ["Other country"],
            default_text="Select a country",
            name=self.label,
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )

    def validate(self, response, **kwargs):
        if self.control.force_selection and response.answer == "":
            return FailedValidation("You need to select a country!")
        return None


class FormalEducation(ModularPage):
    def __init__(
        self,
        label="formal_education",
        prompt="What is your highest level of formal education?",
    ):
        self.label = label
        self.prompt = prompt
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
                "None",
                "High school",
                "College",
                "Graduate School",
                "Postgraduate degree or higher",
            ],
            name="formal_education",
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


# Language #
class MotherTongue(ModularPage):
    def __init__(
        self,
        label="mother_tongue",
        # TODO Change back to plural (add "(s)") once multi-select is implemented.
        prompt="What is your mother tongue - i.e., the language which you have grown up speaking from early childhood)?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = DropdownControl(
            choices=[language[0] for language in languages()] + ["other"],
            labels=[language[1] for language in languages()] + ["Other language"],
            default_text="Select a language",
            name=self.label,
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )

    def validate(self, response, **kwargs):
        if self.control.force_selection and response.answer == "":
            return FailedValidation("You need to select a language!")
        return None


class MoreThanOneLanguage(ModularPage):
    def __init__(
        self,
        label="more_than_one_language",
        prompt="Do you speak more than one language?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no"],
            labels=["Yes", "No"],
            arrange_vertically=False,
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class LanguagesInOrderOfProficiency(ModularPage):
    def __init__(
        self,
        label="languages_in_order_of_proficiency",
        prompt="Please list the languages you speak in order of proficiency (first language first, second language second, ...)",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(),
            time_estimate=self.time_estimate,
        )

    @staticmethod
    def validate(response, **kwargs):
        if not response.answer != "":
            return FailedValidation("Please list at least one language!")
        return None


# Basic music #
class YearsOfFormalTraining(ModularPage):
    def __init__(
        self,
        label="years_of_formal_training",
        prompt="How many years of formal training on a musical instrument (including voice) have you had during your lifetime?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=NumberControl(),
            time_estimate=self.time_estimate,
        )


class HoursOfDailyMusicListening(ModularPage):
    def __init__(
        self,
        label="hours_of_daily_music_listening",
        prompt="On average, how many hours do you listen to music daily?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=NumberControl(),
            time_estimate=self.time_estimate,
        )


class MoneyFromPlayingMusic(ModularPage):
    def __init__(
        self,
        label="money_from_playing_music",
        prompt="Do you make money from playing music?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = RadioButtonControl(
            ["frequently", "sometimes", "never"],
            ["Frequently", "Sometimes", "Never"],
            name="money_from_playing_music",
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


# Hearing loss #
class HearingLoss(ModularPage):
    def __init__(
        self,
        label="hearing_loss",
        prompt="Do you have hearing loss or any other hearing issues?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no"],
            labels=["Yes", "No"],
            arrange_vertically=False,
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


# Dance #
class DanceSociallyOrProfessionally(ModularPage):
    def __init__(
        self,
        label="dance_socially_or_professionally",
        prompt="Do you dance socially or professionally?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = RadioButtonControl(
            ["socially", "professionally", "never_dance"],
            ["Socially", "Professionally", "I never dance"],
            name="dance_socially_or_professionally",
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class LastTimeDanced(ModularPage):
    def __init__(
        self,
        label="last_time_danced",
        prompt="When was the last time you danced? (choose the most accurate answer):",
    ):
        self.label = label
        self.prompt = prompt
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
                "This week",
                "This month",
                "This year",
                "Some years ago",
                "Many years ago",
                "I never danced",
            ],
            name="last_time_danced",
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


# Speech disorders #
class SpeechLanguageTherapy(ModularPage):
    def __init__(
        self,
        label="speech_language_therapy",
        prompt="Did you get speech-language therapy as a child?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no", "dont_know"],
            labels=["Yes", "No", "I Don’t know"],
            arrange_vertically=False,
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class DiagnosedWithDyslexia(ModularPage):
    def __init__(
        self,
        label="diagnosed_with_dyslexia",
        prompt="Have you ever been diagnosed with dyslexia?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            choices=["yes", "no", "dont_know"],
            labels=["Yes", "No", "I Don’t know"],
            arrange_vertically=False,
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


# Income #
class HouseholdIncomePerYear(ModularPage):
    def __init__(
        self,
        label="household_income_per_year",
        prompt="What is your total household income per year?",
    ):
        self.label = label
        self.prompt = prompt
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
                "Less than $10,000",
                "$10,000 to $19,999",
                "$20,000 to $29,999",
                "$30,000 to $39,999",
                "$40,000 to $49,999",
                "$50,000 to $59,999",
                "$60,000 to $69,999",
                "$70,000 to $79,999",
                "$80,000 to $89,999",
                "$90,000 to $99,999",
                "$100,000 to $149,999",
                "$150,000 or more",
            ],
            name="household_income_per_year",
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


# ExperimentFeedback #
class LikedExperiment(ModularPage):
    def __init__(
        self,
        label="liked_experiment",
        prompt="Did you like the experiment?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(
                bot_response=lambda: "I'm a bot so I don't really have feelings..."
            ),
            time_estimate=self.time_estimate,
        )


class FoundExperimentDifficult(ModularPage):
    def __init__(
        self,
        label="find_experiment_difficult",
        prompt="Did you find the experiment difficult?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(),
            time_estimate=self.time_estimate,
            bot_response=lambda: "I'm a bot so I found it pretty easy...",
        )


class EncounteredTechnicalProblems(ModularPage):
    def __init__(
        self,
        label="encountered_technical_problems",
        prompt="Did you encounter any technical problems during the experiment? If so, please provide a few words describing the problem.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        super().__init__(
            self.label,
            self.prompt,
            control=TextControl(),
            time_estimate=self.time_estimate,
            bot_response=lambda: "No technical problems.",
        )


def countries(locale=None):
    """
    List compiled using the pycountry package v20.7.3 with
    ``
    sorted([(lang.alpha_2, lang.name) for lang in pycountry.countries
        if hasattr(lang, 'alpha_2')], key=lambda country: country[1])
    ``
    """
    _, _p, _np = get_translator(locale)
    return [
        ("AF", _("Afghanistan")),
        ("AL", _("Albania")),
        ("DZ", _("Algeria")),
        ("AS", _("American Samoa")),
        ("AD", _("Andorra")),
        ("AO", _("Angola")),
        ("AI", _("Anguilla")),
        ("AQ", _("Antarctica")),
        ("AG", _("Antigua and Barbuda")),
        ("AR", _("Argentina")),
        ("AM", _("Armenia")),
        ("AW", _("Aruba")),
        ("AU", _("Australia")),
        ("AT", _("Austria")),
        ("AZ", _("Azerbaijan")),
        ("BS", _("Bahamas")),
        ("BH", _("Bahrain")),
        ("BD", _("Bangladesh")),
        ("BB", _("Barbados")),
        ("BY", _("Belarus")),
        ("BE", _("Belgium")),
        ("BZ", _("Belize")),
        ("BJ", _("Benin")),
        ("BM", _("Bermuda")),
        ("BT", _("Bhutan")),
        ("BO", _("Bolivia, Plurinational State of")),
        ("BQ", _("Bonaire, Sint Eustatius and Saba")),
        ("BA", _("Bosnia and Herzegovina")),
        ("BW", _("Botswana")),
        ("BV", _("Bouvet Island")),
        ("BR", _("Brazil")),
        ("IO", _("British Indian Ocean Territory")),
        ("BN", _("Brunei Darussalam")),
        ("BG", _("Bulgaria")),
        ("BF", _("Burkina Faso")),
        ("BI", _("Burundi")),
        ("CV", _("Cabo Verde")),
        ("KH", _("Cambodia")),
        ("CM", _("Cameroon")),
        ("CA", _("Canada")),
        ("KY", _("Cayman Islands")),
        ("CF", _("Central African Republic")),
        ("TD", _("Chad")),
        ("CL", _("Chile")),
        ("CN", _("China")),
        ("CX", _("Christmas Island")),
        ("CC", _("Cocos (Keeling) Islands")),
        ("CO", _("Colombia")),
        ("KM", _("Comoros")),
        ("CG", _("Congo")),
        ("CD", _("Congo, The Democratic Republic of the")),
        ("CK", _("Cook Islands")),
        ("CR", _("Costa Rica")),
        ("HR", _("Croatia")),
        ("CU", _("Cuba")),
        ("CW", _("Curaçao")),
        ("CY", _("Cyprus")),
        ("CZ", _("Czechia")),
        ("CI", _("Côte d'Ivoire")),
        ("DK", _("Denmark")),
        ("DJ", _("Djibouti")),
        ("DM", _("Dominica")),
        ("DO", _("Dominican Republic")),
        ("EC", _("Ecuador")),
        ("EG", _("Egypt")),
        ("SV", _("El Salvador")),
        ("GQ", _("Equatorial Guinea")),
        ("ER", _("Eritrea")),
        ("EE", _("Estonia")),
        ("SZ", _("Eswatini")),
        ("ET", _("Ethiopia")),
        ("FK", _("Falkland Islands (Malvinas)")),
        ("FO", _("Faroe Islands")),
        ("FJ", _("Fiji")),
        ("FI", _("Finland")),
        ("FR", _("France")),
        ("GF", _("French Guiana")),
        ("PF", _("French Polynesia")),
        ("TF", _("French Southern Territories")),
        ("GA", _("Gabon")),
        ("GM", _("Gambia")),
        ("GE", _("Georgia")),
        ("DE", _("Germany")),
        ("GH", _("Ghana")),
        ("GI", _("Gibraltar")),
        ("GR", _("Greece")),
        ("GL", _("Greenland")),
        ("GD", _("Grenada")),
        ("GP", _("Guadeloupe")),
        ("GU", _("Guam")),
        ("GT", _("Guatemala")),
        ("GG", _("Guernsey")),
        ("GN", _("Guinea")),
        ("GW", _("Guinea-Bissau")),
        ("GY", _("Guyana")),
        ("HT", _("Haiti")),
        ("HM", _("Heard Island and McDonald Islands")),
        ("VA", _("Holy See (Vatican City State)")),
        ("HN", _("Honduras")),
        ("HK", _("Hong Kong")),
        ("HU", _("Hungary")),
        ("IS", _("Iceland")),
        ("IN", _("India")),
        ("ID", _("Indonesia")),
        ("IR", _("Iran, Islamic Republic of")),
        ("IQ", _("Iraq")),
        ("IE", _("Ireland")),
        ("IM", _("Isle of Man")),
        ("IL", _("Israel")),
        ("IT", _("Italy")),
        ("JM", _("Jamaica")),
        ("JP", _("Japan")),
        ("JE", _("Jersey")),
        ("JO", _("Jordan")),
        ("KZ", _("Kazakhstan")),
        ("KE", _("Kenya")),
        ("KI", _("Kiribati")),
        ("KP", _("Korea, Democratic People's Republic of")),
        ("KR", _("Korea, Republic of")),
        ("KW", _("Kuwait")),
        ("KG", _("Kyrgyzstan")),
        ("LA", _("Lao People's Democratic Republic")),
        ("LV", _("Latvia")),
        ("LB", _("Lebanon")),
        ("LS", _("Lesotho")),
        ("LR", _("Liberia")),
        ("LY", _("Libya")),
        ("LI", _("Liechtenstein")),
        ("LT", _("Lithuania")),
        ("LU", _("Luxembourg")),
        ("MO", _("Macao")),
        ("MG", _("Madagascar")),
        ("MW", _("Malawi")),
        ("MY", _("Malaysia")),
        ("MV", _("Maldives")),
        ("ML", _("Mali")),
        ("MT", _("Malta")),
        ("MH", _("Marshall Islands")),
        ("MQ", _("Martinique")),
        ("MR", _("Mauritania")),
        ("MU", _("Mauritius")),
        ("YT", _("Mayotte")),
        ("MX", _("Mexico")),
        ("FM", _("Micronesia, Federated States of")),
        ("MD", _("Moldova, Republic of")),
        ("MC", _("Monaco")),
        ("MN", _("Mongolia")),
        ("ME", _("Montenegro")),
        ("MS", _("Montserrat")),
        ("MA", _("Morocco")),
        ("MZ", _("Mozambique")),
        ("MM", _("Myanmar")),
        ("NA", _("Namibia")),
        ("NR", _("Nauru")),
        ("NP", _("Nepal")),
        ("NL", _("Netherlands")),
        ("NC", _("New Caledonia")),
        ("NZ", _("New Zealand")),
        ("NI", _("Nicaragua")),
        ("NE", _("Niger")),
        ("NG", _("Nigeria")),
        ("NU", _("Niue")),
        ("NF", _("Norfolk Island")),
        ("MK", _("North Macedonia")),
        ("MP", _("Northern Mariana Islands")),
        ("NO", _("Norway")),
        ("OM", _("Oman")),
        ("PK", _("Pakistan")),
        ("PW", _("Palau")),
        ("PS", _("Palestine, State of")),
        ("PA", _("Panama")),
        ("PG", _("Papua New Guinea")),
        ("PY", _("Paraguay")),
        ("PE", _("Peru")),
        ("PH", _("Philippines")),
        ("PN", _("Pitcairn")),
        ("PL", _("Poland")),
        ("PT", _("Portugal")),
        ("PR", _("Puerto Rico")),
        ("QA", _("Qatar")),
        ("RO", _("Romania")),
        ("RU", _("Russian Federation")),
        ("RW", _("Rwanda")),
        ("RE", _("Réunion")),
        ("BL", _("Saint Barthélemy")),
        ("SH", _("Saint Helena, Ascension and Tristan da Cunha")),
        ("KN", _("Saint Kitts and Nevis")),
        ("LC", _("Saint Lucia")),
        ("MF", _("Saint Martin (French part)")),
        ("PM", _("Saint Pierre and Miquelon")),
        ("VC", _("Saint Vincent and the Grenadines")),
        ("WS", _("Samoa")),
        ("SM", _("San Marino")),
        ("ST", _("Sao Tome and Principe")),
        ("SA", _("Saudi Arabia")),
        ("SN", _("Senegal")),
        ("RS", _("Serbia")),
        ("SC", _("Seychelles")),
        ("SL", _("Sierra Leone")),
        ("SG", _("Singapore")),
        ("SX", _("Sint Maarten (Dutch part)")),
        ("SK", _("Slovakia")),
        ("SI", _("Slovenia")),
        ("SB", _("Solomon Islands")),
        ("SO", _("Somalia")),
        ("ZA", _("South Africa")),
        ("GS", _("South Georgia and the South Sandwich Islands")),
        ("SS", _("South Sudan")),
        ("ES", _("Spain")),
        ("LK", _("Sri Lanka")),
        ("SD", _("Sudan")),
        ("SR", _("Suriname")),
        ("SJ", _("Svalbard and Jan Mayen")),
        ("SE", _("Sweden")),
        ("CH", _("Switzerland")),
        ("SY", _("Syrian Arab Republic")),
        ("TW", _("Taiwan, Province of China")),
        ("TJ", _("Tajikistan")),
        ("TZ", _("Tanzania, United Republic of")),
        ("TH", _("Thailand")),
        ("TL", _("Timor-Leste")),
        ("TG", _("Togo")),
        ("TK", _("Tokelau")),
        ("TO", _("Tonga")),
        ("TT", _("Trinidad and Tobago")),
        ("TN", _("Tunisia")),
        ("TR", _("Turkey")),
        ("TM", _("Turkmenistan")),
        ("TC", _("Turks and Caicos Islands")),
        ("TV", _("Tuvalu")),
        ("UG", _("Uganda")),
        ("UA", _("Ukraine")),
        ("AE", _("United Arab Emirates")),
        ("GB", _("United Kingdom")),
        ("US", _("United States")),
        ("UM", _("United States Minor Outlying Islands")),
        ("UY", _("Uruguay")),
        ("UZ", _("Uzbekistan")),
        ("VU", _("Vanuatu")),
        ("VE", _("Venezuela, Bolivarian Republic of")),
        ("VN", _("Viet Nam")),
        ("VG", _("Virgin Islands, British")),
        ("VI", _("Virgin Islands, U.S.")),
        ("WF", _("Wallis and Futuna")),
        ("EH", _("Western Sahara")),
        ("YE", _("Yemen")),
        ("ZM", _("Zambia")),
        ("ZW", _("Zimbabwe")),
        ("AX", _("Åland Islands")),
    ]


def languages(locale=None):
    """
    List compiled using the pycountry package v20.7.3 with
    ``
    sorted([(lang.alpha_2, lang.name) for lang in pycountry.languages
        if hasattr(lang, 'alpha_2')], key=lambda country: country[1])
    ``
    """
    _, _p, _np = get_translator(locale)
    return [
        ("ab", _("Abkhazian")),
        ("aa", _("Afar")),
        ("af", _("Afrikaans")),
        ("ak", _("Akan")),
        ("sq", _("Albanian")),
        ("am", _("Amharic")),
        ("ar", _("Arabic")),
        ("an", _("Aragonese")),
        ("hy", _("Armenian")),
        ("as", _("Assamese")),
        ("av", _("Avaric")),
        ("ae", _("Avestan")),
        ("ay", _("Aymara")),
        ("az", _("Azerbaijani")),
        ("bm", _("Bambara")),
        ("ba", _("Bashkir")),
        ("eu", _("Basque")),
        ("be", _("Belarusian")),
        ("bn", _("Bengali")),
        ("bi", _("Bislama")),
        ("bs", _("Bosnian")),
        ("br", _("Breton")),
        ("bg", _("Bulgarian")),
        ("my", _("Burmese")),
        ("ca", _("Catalan")),
        ("km", _("Central Khmer")),
        ("ch", _("Chamorro")),
        ("ce", _("Chechen")),
        ("zh", _("Chinese")),
        ("cu", _("Church Slavic")),
        ("cv", _("Chuvash")),
        ("kw", _("Cornish")),
        ("co", _("Corsican")),
        ("cr", _("Cree")),
        ("hr", _("Croatian")),
        ("cs", _("Czech")),
        ("da", _("Danish")),
        ("dv", _("Dhivehi")),
        ("nl", _("Dutch")),
        ("dz", _("Dzongkha")),
        ("en", _("English")),
        ("eo", _("Esperanto")),
        ("et", _("Estonian")),
        ("ee", _("Ewe")),
        ("fo", _("Faroese")),
        ("fj", _("Fijian")),
        ("fi", _("Finnish")),
        ("fr", _("French")),
        ("ff", _("Fulah")),
        ("gl", _("Galician")),
        ("lg", _("Ganda")),
        ("ka", _("Georgian")),
        ("de", _("German")),
        ("gn", _("Guarani")),
        ("gu", _("Gujarati")),
        ("ht", _("Haitian")),
        ("ha", _("Hausa")),
        ("he", _("Hebrew")),
        ("hz", _("Herero")),
        ("hi", _("Hindi")),
        ("ho", _("Hiri Motu")),
        ("hu", _("Hungarian")),
        ("is", _("Icelandic")),
        ("io", _("Ido")),
        ("ig", _("Igbo")),
        ("id", _("Indonesian")),
        ("ia", _("Interlingua (International Auxiliary Language Association)")),
        ("ie", _("Interlingue")),
        ("iu", _("Inuktitut")),
        ("ik", _("Inupiaq")),
        ("ga", _("Irish")),
        ("it", _("Italian")),
        ("ja", _("Japanese")),
        ("jv", _("Javanese")),
        ("kl", _("Kalaallisut")),
        ("kn", _("Kannada")),
        ("kr", _("Kanuri")),
        ("ks", _("Kashmiri")),
        ("kk", _("Kazakh")),
        ("ki", _("Kikuyu")),
        ("rw", _("Kinyarwanda")),
        ("ky", _("Kirghiz")),
        ("kv", _("Komi")),
        ("kg", _("Kongo")),
        ("ko", _("Korean")),
        ("kj", _("Kuanyama")),
        ("ku", _("Kurdish")),
        ("lo", _("Lao")),
        ("la", _("Latin")),
        ("lv", _("Latvian")),
        ("li", _("Limburgan")),
        ("ln", _("Lingala")),
        ("lt", _("Lithuanian")),
        ("lu", _("Luba-Katanga")),
        ("lb", _("Luxembourgish")),
        ("mk", _("Macedonian")),
        ("mg", _("Malagasy")),
        ("ms", _("Malay (macrolanguage)")),
        ("ml", _("Malayalam")),
        ("mt", _("Maltese")),
        ("gv", _("Manx")),
        ("mi", _("Maori")),
        ("mr", _("Marathi")),
        ("mh", _("Marshallese")),
        ("el", _("Modern Greek (1453-)")),
        ("mn", _("Mongolian")),
        ("na", _("Nauru")),
        ("nv", _("Navajo")),
        ("ng", _("Ndonga")),
        ("ne", _("Nepali (macrolanguage)")),
        ("nd", _("North Ndebele")),
        ("se", _("Northern Sami")),
        ("no", _("Norwegian")),
        ("nb", _("Norwegian Bokmål")),
        ("nn", _("Norwegian Nynorsk")),
        ("ny", _("Nyanja")),
        ("oc", _("Occitan (post 1500)")),
        ("oj", _("Ojibwa")),
        ("or", _("Oriya (macrolanguage)")),
        ("om", _("Oromo")),
        ("os", _("Ossetian")),
        ("pi", _("Pali")),
        ("pa", _("Panjabi")),
        ("fa", _("Persian")),
        ("pl", _("Polish")),
        ("pt", _("Portuguese")),
        ("ps", _("Pushto")),
        ("qu", _("Quechua")),
        ("ro", _("Romanian")),
        ("rm", _("Romansh")),
        ("rn", _("Rundi")),
        ("ru", _("Russian")),
        ("sm", _("Samoan")),
        ("sg", _("Sango")),
        ("sa", _("Sanskrit")),
        ("sc", _("Sardinian")),
        ("gd", _("Scottish Gaelic")),
        ("sr", _("Serbian")),
        ("sh", _("Serbo-Croatian")),
        ("sn", _("Shona")),
        ("ii", _("Sichuan Yi")),
        ("sd", _("Sindhi")),
        ("si", _("Sinhala")),
        ("sk", _("Slovak")),
        ("sl", _("Slovenian")),
        ("so", _("Somali")),
        ("nr", _("South Ndebele")),
        ("st", _("Southern Sotho")),
        ("es", _("Spanish")),
        ("su", _("Sundanese")),
        ("sw", _("Swahili (macrolanguage)")),
        ("ss", _("Swati")),
        ("sv", _("Swedish")),
        ("tl", _("Tagalog")),
        ("ty", _("Tahitian")),
        ("tg", _("Tajik")),
        ("ta", _("Tamil")),
        ("tt", _("Tatar")),
        ("te", _("Telugu")),
        ("th", _("Thai")),
        ("bo", _("Tibetan")),
        ("ti", _("Tigrinya")),
        ("to", _("Tonga (Tonga Islands)")),
        ("ts", _("Tsonga")),
        ("tn", _("Tswana")),
        ("tr", _("Turkish")),
        ("tk", _("Turkmen")),
        ("tw", _("Twi")),
        ("ug", _("Uighur")),
        ("uk", _("Ukrainian")),
        ("ur", _("Urdu")),
        ("uz", _("Uzbek")),
        ("ve", _("Venda")),
        ("vi", _("Vietnamese")),
        ("vo", _("Volapük")),
        ("wa", _("Walloon")),
        ("cy", _("Welsh")),
        ("fy", _("Western Frisian")),
        ("wo", _("Wolof")),
        ("xh", _("Xhosa")),
        ("yi", _("Yiddish")),
        ("yo", _("Yoruba")),
        ("za", _("Zhuang")),
        ("zu", _("Zulu")),
    ]
