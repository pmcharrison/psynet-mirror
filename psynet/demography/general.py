from psynet.modular_page import (
    DropdownControl,
    ModularPage,
    NumberControl,
    PushButtonControl,
    RadioButtonControl,
    TextControl,
)
from psynet.timeline import FailedValidation, Module, conditional, join
from psynet.utils import get_logger

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
        prompt="How do you identify yourself?",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = RadioButtonControl(
            ["female", "male", "non_binary", "not_specified", "prefer_not_to_say"],
            ["Female", "Male", "Non-binary", "Not specified", "I prefer not to answer"],
            name="gender",
            show_free_text_option=True,
            placeholder_text_free_text="Specify yourself",
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
            response.answer.isdigit()
            and int(response.answer) > 0
            and int(response.answer) < 120
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
            control=TextControl(),
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
        )


def countries():
    """
    List compiled using the pycountry package v20.7.3 with
    ``
    sorted([(lang.alpha_2, lang.name) for lang in pycountry.countries
        if hasattr(lang, 'alpha_2')], key=lambda country: country[1])
    ``
    """
    return [
        ("AF", "Afghanistan"),
        ("AL", "Albania"),
        ("DZ", "Algeria"),
        ("AS", "American Samoa"),
        ("AD", "Andorra"),
        ("AO", "Angola"),
        ("AI", "Anguilla"),
        ("AQ", "Antarctica"),
        ("AG", "Antigua and Barbuda"),
        ("AR", "Argentina"),
        ("AM", "Armenia"),
        ("AW", "Aruba"),
        ("AU", "Australia"),
        ("AT", "Austria"),
        ("AZ", "Azerbaijan"),
        ("BS", "Bahamas"),
        ("BH", "Bahrain"),
        ("BD", "Bangladesh"),
        ("BB", "Barbados"),
        ("BY", "Belarus"),
        ("BE", "Belgium"),
        ("BZ", "Belize"),
        ("BJ", "Benin"),
        ("BM", "Bermuda"),
        ("BT", "Bhutan"),
        ("BO", "Bolivia, Plurinational State of"),
        ("BQ", "Bonaire, Sint Eustatius and Saba"),
        ("BA", "Bosnia and Herzegovina"),
        ("BW", "Botswana"),
        ("BV", "Bouvet Island"),
        ("BR", "Brazil"),
        ("IO", "British Indian Ocean Territory"),
        ("BN", "Brunei Darussalam"),
        ("BG", "Bulgaria"),
        ("BF", "Burkina Faso"),
        ("BI", "Burundi"),
        ("CV", "Cabo Verde"),
        ("KH", "Cambodia"),
        ("CM", "Cameroon"),
        ("CA", "Canada"),
        ("KY", "Cayman Islands"),
        ("CF", "Central African Republic"),
        ("TD", "Chad"),
        ("CL", "Chile"),
        ("CN", "China"),
        ("CX", "Christmas Island"),
        ("CC", "Cocos (Keeling) Islands"),
        ("CO", "Colombia"),
        ("KM", "Comoros"),
        ("CG", "Congo"),
        ("CD", "Congo, The Democratic Republic of the"),
        ("CK", "Cook Islands"),
        ("CR", "Costa Rica"),
        ("HR", "Croatia"),
        ("CU", "Cuba"),
        ("CW", "Curaçao"),
        ("CY", "Cyprus"),
        ("CZ", "Czechia"),
        ("CI", "Côte d'Ivoire"),
        ("DK", "Denmark"),
        ("DJ", "Djibouti"),
        ("DM", "Dominica"),
        ("DO", "Dominican Republic"),
        ("EC", "Ecuador"),
        ("EG", "Egypt"),
        ("SV", "El Salvador"),
        ("GQ", "Equatorial Guinea"),
        ("ER", "Eritrea"),
        ("EE", "Estonia"),
        ("SZ", "Eswatini"),
        ("ET", "Ethiopia"),
        ("FK", "Falkland Islands (Malvinas)"),
        ("FO", "Faroe Islands"),
        ("FJ", "Fiji"),
        ("FI", "Finland"),
        ("FR", "France"),
        ("GF", "French Guiana"),
        ("PF", "French Polynesia"),
        ("TF", "French Southern Territories"),
        ("GA", "Gabon"),
        ("GM", "Gambia"),
        ("GE", "Georgia"),
        ("DE", "Germany"),
        ("GH", "Ghana"),
        ("GI", "Gibraltar"),
        ("GR", "Greece"),
        ("GL", "Greenland"),
        ("GD", "Grenada"),
        ("GP", "Guadeloupe"),
        ("GU", "Guam"),
        ("GT", "Guatemala"),
        ("GG", "Guernsey"),
        ("GN", "Guinea"),
        ("GW", "Guinea-Bissau"),
        ("GY", "Guyana"),
        ("HT", "Haiti"),
        ("HM", "Heard Island and McDonald Islands"),
        ("VA", "Holy See (Vatican City State)"),
        ("HN", "Honduras"),
        ("HK", "Hong Kong"),
        ("HU", "Hungary"),
        ("IS", "Iceland"),
        ("IN", "India"),
        ("ID", "Indonesia"),
        ("IR", "Iran, Islamic Republic of"),
        ("IQ", "Iraq"),
        ("IE", "Ireland"),
        ("IM", "Isle of Man"),
        ("IL", "Israel"),
        ("IT", "Italy"),
        ("JM", "Jamaica"),
        ("JP", "Japan"),
        ("JE", "Jersey"),
        ("JO", "Jordan"),
        ("KZ", "Kazakhstan"),
        ("KE", "Kenya"),
        ("KI", "Kiribati"),
        ("KP", "Korea, Democratic People's Republic of"),
        ("KR", "Korea, Republic of"),
        ("KW", "Kuwait"),
        ("KG", "Kyrgyzstan"),
        ("LA", "Lao People's Democratic Republic"),
        ("LV", "Latvia"),
        ("LB", "Lebanon"),
        ("LS", "Lesotho"),
        ("LR", "Liberia"),
        ("LY", "Libya"),
        ("LI", "Liechtenstein"),
        ("LT", "Lithuania"),
        ("LU", "Luxembourg"),
        ("MO", "Macao"),
        ("MG", "Madagascar"),
        ("MW", "Malawi"),
        ("MY", "Malaysia"),
        ("MV", "Maldives"),
        ("ML", "Mali"),
        ("MT", "Malta"),
        ("MH", "Marshall Islands"),
        ("MQ", "Martinique"),
        ("MR", "Mauritania"),
        ("MU", "Mauritius"),
        ("YT", "Mayotte"),
        ("MX", "Mexico"),
        ("FM", "Micronesia, Federated States of"),
        ("MD", "Moldova, Republic of"),
        ("MC", "Monaco"),
        ("MN", "Mongolia"),
        ("ME", "Montenegro"),
        ("MS", "Montserrat"),
        ("MA", "Morocco"),
        ("MZ", "Mozambique"),
        ("MM", "Myanmar"),
        ("NA", "Namibia"),
        ("NR", "Nauru"),
        ("NP", "Nepal"),
        ("NL", "Netherlands"),
        ("NC", "New Caledonia"),
        ("NZ", "New Zealand"),
        ("NI", "Nicaragua"),
        ("NE", "Niger"),
        ("NG", "Nigeria"),
        ("NU", "Niue"),
        ("NF", "Norfolk Island"),
        ("MK", "North Macedonia"),
        ("MP", "Northern Mariana Islands"),
        ("NO", "Norway"),
        ("OM", "Oman"),
        ("PK", "Pakistan"),
        ("PW", "Palau"),
        ("PS", "Palestine, State of"),
        ("PA", "Panama"),
        ("PG", "Papua New Guinea"),
        ("PY", "Paraguay"),
        ("PE", "Peru"),
        ("PH", "Philippines"),
        ("PN", "Pitcairn"),
        ("PL", "Poland"),
        ("PT", "Portugal"),
        ("PR", "Puerto Rico"),
        ("QA", "Qatar"),
        ("RO", "Romania"),
        ("RU", "Russian Federation"),
        ("RW", "Rwanda"),
        ("RE", "Réunion"),
        ("BL", "Saint Barthélemy"),
        ("SH", "Saint Helena, Ascension and Tristan da Cunha"),
        ("KN", "Saint Kitts and Nevis"),
        ("LC", "Saint Lucia"),
        ("MF", "Saint Martin (French part)"),
        ("PM", "Saint Pierre and Miquelon"),
        ("VC", "Saint Vincent and the Grenadines"),
        ("WS", "Samoa"),
        ("SM", "San Marino"),
        ("ST", "Sao Tome and Principe"),
        ("SA", "Saudi Arabia"),
        ("SN", "Senegal"),
        ("RS", "Serbia"),
        ("SC", "Seychelles"),
        ("SL", "Sierra Leone"),
        ("SG", "Singapore"),
        ("SX", "Sint Maarten (Dutch part)"),
        ("SK", "Slovakia"),
        ("SI", "Slovenia"),
        ("SB", "Solomon Islands"),
        ("SO", "Somalia"),
        ("ZA", "South Africa"),
        ("GS", "South Georgia and the South Sandwich Islands"),
        ("SS", "South Sudan"),
        ("ES", "Spain"),
        ("LK", "Sri Lanka"),
        ("SD", "Sudan"),
        ("SR", "Suriname"),
        ("SJ", "Svalbard and Jan Mayen"),
        ("SE", "Sweden"),
        ("CH", "Switzerland"),
        ("SY", "Syrian Arab Republic"),
        ("TW", "Taiwan, Province of China"),
        ("TJ", "Tajikistan"),
        ("TZ", "Tanzania, United Republic of"),
        ("TH", "Thailand"),
        ("TL", "Timor-Leste"),
        ("TG", "Togo"),
        ("TK", "Tokelau"),
        ("TO", "Tonga"),
        ("TT", "Trinidad and Tobago"),
        ("TN", "Tunisia"),
        ("TR", "Turkey"),
        ("TM", "Turkmenistan"),
        ("TC", "Turks and Caicos Islands"),
        ("TV", "Tuvalu"),
        ("UG", "Uganda"),
        ("UA", "Ukraine"),
        ("AE", "United Arab Emirates"),
        ("GB", "United Kingdom"),
        ("US", "United States"),
        ("UM", "United States Minor Outlying Islands"),
        ("UY", "Uruguay"),
        ("UZ", "Uzbekistan"),
        ("VU", "Vanuatu"),
        ("VE", "Venezuela, Bolivarian Republic of"),
        ("VN", "Viet Nam"),
        ("VG", "Virgin Islands, British"),
        ("VI", "Virgin Islands, U.S."),
        ("WF", "Wallis and Futuna"),
        ("EH", "Western Sahara"),
        ("YE", "Yemen"),
        ("ZM", "Zambia"),
        ("ZW", "Zimbabwe"),
        ("AX", "Åland Islands"),
    ]


def languages():
    """
    List compiled using the pycountry package v20.7.3 with
    ``
    sorted([(lang.alpha_2, lang.name) for lang in pycountry.languages
        if hasattr(lang, 'alpha_2')], key=lambda country: country[1])
    ``
    """
    return [
        ("ab", "Abkhazian"),
        ("aa", "Afar"),
        ("af", "Afrikaans"),
        ("ak", "Akan"),
        ("sq", "Albanian"),
        ("am", "Amharic"),
        ("ar", "Arabic"),
        ("an", "Aragonese"),
        ("hy", "Armenian"),
        ("as", "Assamese"),
        ("av", "Avaric"),
        ("ae", "Avestan"),
        ("ay", "Aymara"),
        ("az", "Azerbaijani"),
        ("bm", "Bambara"),
        ("ba", "Bashkir"),
        ("eu", "Basque"),
        ("be", "Belarusian"),
        ("bn", "Bengali"),
        ("bi", "Bislama"),
        ("bs", "Bosnian"),
        ("br", "Breton"),
        ("bg", "Bulgarian"),
        ("my", "Burmese"),
        ("ca", "Catalan"),
        ("km", "Central Khmer"),
        ("ch", "Chamorro"),
        ("ce", "Chechen"),
        ("zh", "Chinese"),
        ("cu", "Church Slavic"),
        ("cv", "Chuvash"),
        ("kw", "Cornish"),
        ("co", "Corsican"),
        ("cr", "Cree"),
        ("hr", "Croatian"),
        ("cs", "Czech"),
        ("da", "Danish"),
        ("dv", "Dhivehi"),
        ("nl", "Dutch"),
        ("dz", "Dzongkha"),
        ("en", "English"),
        ("eo", "Esperanto"),
        ("et", "Estonian"),
        ("ee", "Ewe"),
        ("fo", "Faroese"),
        ("fj", "Fijian"),
        ("fi", "Finnish"),
        ("fr", "French"),
        ("ff", "Fulah"),
        ("gl", "Galician"),
        ("lg", "Ganda"),
        ("ka", "Georgian"),
        ("de", "German"),
        ("gn", "Guarani"),
        ("gu", "Gujarati"),
        ("ht", "Haitian"),
        ("ha", "Hausa"),
        ("he", "Hebrew"),
        ("hz", "Herero"),
        ("hi", "Hindi"),
        ("ho", "Hiri Motu"),
        ("hu", "Hungarian"),
        ("is", "Icelandic"),
        ("io", "Ido"),
        ("ig", "Igbo"),
        ("id", "Indonesian"),
        ("ia", "Interlingua (International Auxiliary Language Association)"),
        ("ie", "Interlingue"),
        ("iu", "Inuktitut"),
        ("ik", "Inupiaq"),
        ("ga", "Irish"),
        ("it", "Italian"),
        ("ja", "Japanese"),
        ("jv", "Javanese"),
        ("kl", "Kalaallisut"),
        ("kn", "Kannada"),
        ("kr", "Kanuri"),
        ("ks", "Kashmiri"),
        ("kk", "Kazakh"),
        ("ki", "Kikuyu"),
        ("rw", "Kinyarwanda"),
        ("ky", "Kirghiz"),
        ("kv", "Komi"),
        ("kg", "Kongo"),
        ("ko", "Korean"),
        ("kj", "Kuanyama"),
        ("ku", "Kurdish"),
        ("lo", "Lao"),
        ("la", "Latin"),
        ("lv", "Latvian"),
        ("li", "Limburgan"),
        ("ln", "Lingala"),
        ("lt", "Lithuanian"),
        ("lu", "Luba-Katanga"),
        ("lb", "Luxembourgish"),
        ("mk", "Macedonian"),
        ("mg", "Malagasy"),
        ("ms", "Malay (macrolanguage)"),
        ("ml", "Malayalam"),
        ("mt", "Maltese"),
        ("gv", "Manx"),
        ("mi", "Maori"),
        ("mr", "Marathi"),
        ("mh", "Marshallese"),
        ("el", "Modern Greek (1453-)"),
        ("mn", "Mongolian"),
        ("na", "Nauru"),
        ("nv", "Navajo"),
        ("ng", "Ndonga"),
        ("ne", "Nepali (macrolanguage)"),
        ("nd", "North Ndebele"),
        ("se", "Northern Sami"),
        ("no", "Norwegian"),
        ("nb", "Norwegian Bokmål"),
        ("nn", "Norwegian Nynorsk"),
        ("ny", "Nyanja"),
        ("oc", "Occitan (post 1500)"),
        ("oj", "Ojibwa"),
        ("or", "Oriya (macrolanguage)"),
        ("om", "Oromo"),
        ("os", "Ossetian"),
        ("pi", "Pali"),
        ("pa", "Panjabi"),
        ("fa", "Persian"),
        ("pl", "Polish"),
        ("pt", "Portuguese"),
        ("ps", "Pushto"),
        ("qu", "Quechua"),
        ("ro", "Romanian"),
        ("rm", "Romansh"),
        ("rn", "Rundi"),
        ("ru", "Russian"),
        ("sm", "Samoan"),
        ("sg", "Sango"),
        ("sa", "Sanskrit"),
        ("sc", "Sardinian"),
        ("gd", "Scottish Gaelic"),
        ("sr", "Serbian"),
        ("sh", "Serbo-Croatian"),
        ("sn", "Shona"),
        ("ii", "Sichuan Yi"),
        ("sd", "Sindhi"),
        ("si", "Sinhala"),
        ("sk", "Slovak"),
        ("sl", "Slovenian"),
        ("so", "Somali"),
        ("nr", "South Ndebele"),
        ("st", "Southern Sotho"),
        ("es", "Spanish"),
        ("su", "Sundanese"),
        ("sw", "Swahili (macrolanguage)"),
        ("ss", "Swati"),
        ("sv", "Swedish"),
        ("tl", "Tagalog"),
        ("ty", "Tahitian"),
        ("tg", "Tajik"),
        ("ta", "Tamil"),
        ("tt", "Tatar"),
        ("te", "Telugu"),
        ("th", "Thai"),
        ("bo", "Tibetan"),
        ("ti", "Tigrinya"),
        ("to", "Tonga (Tonga Islands)"),
        ("ts", "Tsonga"),
        ("tn", "Tswana"),
        ("tr", "Turkish"),
        ("tk", "Turkmen"),
        ("tw", "Twi"),
        ("ug", "Uighur"),
        ("uk", "Ukrainian"),
        ("ur", "Urdu"),
        ("uz", "Uzbek"),
        ("ve", "Venda"),
        ("vi", "Vietnamese"),
        ("vo", "Volapük"),
        ("wa", "Walloon"),
        ("cy", "Welsh"),
        ("fy", "Western Frisian"),
        ("wo", "Wolof"),
        ("xh", "Xhosa"),
        ("yi", "Yiddish"),
        ("yo", "Yoruba"),
        ("za", "Zhuang"),
        ("zu", "Zulu"),
    ]
