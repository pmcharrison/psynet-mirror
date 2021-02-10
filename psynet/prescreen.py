import random
import ipinfo
import json
import urllib.request

from flask import Markup

from .modular_page import (
    AudioPrompt,
    ColourPrompt,
    ImagePrompt,
    ModularPage,
    PushButtonControl,
    TextControl,
    DropdownControl
)
from .page import InfoPage, UnsuccessfulEndPage
from .timeline import Module, join, conditional, CodeBlock
from .trial.non_adaptive import (
    NonAdaptiveTrial,
    NonAdaptiveTrialMaker,
    StimulusSet,
    StimulusSpec,
)
from .demography.general import CountryOfResidence

class ColorBlindnessTest(Module):
    """
    The color blindness test checks the participant's ability to perceive
    colours. In each trial an image is presented which contains a number and the
    participant must enter the number that is shown into a text box. The image
    disappears after 3 seconds by default, which can be adjusted by providing a different
    value in the ``hide_after`` parameter.

    Parameters
    ----------

    label : string, optional
        The label for the color blindness test, default: "color_blindness_test".

    media : string, optional
        The url under which the images to be displayed can be referenced, default:
        "https://s3.amazonaws.com/ishihara-eye-test/jpg"

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 5.0.

    performance_threshold : int, optional
        The performance threshold, default: 4.

    hide_after : float, optional
        The time in seconds after which the image disappears, default: 3.0.

    """
    def __init__(
            self,
            label = "color_blindness_test",
            media_url: str = "https://s3.amazonaws.com/ishihara-eye-test/jpg",
            time_estimate_per_trial: float = 5.0,
            performance_threshold: int = 4,
            hide_after: float = 3.0,
        ):
        self.label = label
        self.events = join(
            self.instruction_page(hide_after),
            self.trial_maker(
                media_url, time_estimate_per_trial,
                performance_threshold,
                hide_after
            )
        )
        super().__init__(self.label, self.events)


    def instruction_page(self, hide_after):
        if hide_after is None:
            hidden_instructions = ""
        else:
            hidden_instructions = f"This image will disappear after {hide_after} seconds."
        return InfoPage(Markup(
            f"""
            <p>We will now perform a quick test to check your ability to perceive colors.</p>
            <p>
                In each trial, you will be presented with an image that contains a number.
                {hidden_instructions}
                You must enter the number that you see into the text box.
            </p>
            """
        ), time_estimate=10)

    def trial_maker(
            self,
            media_url: str,
            time_estimate_per_trial: float,
            performance_threshold: int,
            hide_after: float
        ):
        class ColorBlindnessTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score +=1
                passed = score >= performance_threshold
                return {
                    "score": score,
                    "passed": passed
                }

        return ColorBlindnessTrialMaker(
            id_="color_blindness",
            trial_class=self.trial(time_estimate_per_trial, hide_after),
            phase="experiment",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False
        )

    def trial(self, time_estimate: float, hide_after: float):
        class ColorBlindnessTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "color_blindness_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "color_blindness_trial",
                    ImagePrompt(
                        self.definition["url"],
                        "Write down the number in the image.",
                        width="410px",
                        height="403px",
                        hide_after=hide_after,
                        margin_bottom="15px",
                        text_align="center"
                    ),
                    TextControl(width="100px"),
                    time_estimate=time_estimate
                )
        return ColorBlindnessTrial

    def get_stimulus_set(self, media_url: str):
        return StimulusSet("color_blindness", [
            StimulusSpec(
                definition={
                    "label": label,
                    "correct_answer": answer,
                    "url": f"{media_url}/ishihara-{label}.jpg"
                },
                phase="experiment"
            )
            for label, answer in
            [
                ("1", "12"),
                ("2", "8"),
                ("3", "29"),
                ("4", "5"),
                ("5", "3"),
                ("6", "15")
            ]
        ])


class ColorVocabularyTest(Module):
    """
    The color vocabulary test checks the participant's ability to name colours. In each trial, a
    colored box is presented and the participant must choose from a set of colors which color is
    displayed in the box. The colors which are presented can be freely chosen by providing an
    optional ``colors`` parameter. See the documentation for further details.

    Parameters
    ----------

    label : string, optional
        The label for the color vocabulary test, default: "color_vocabulary_test".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 5.0.

    performance_threshold : int, optional
        The performance threshold, default: 4.

    colors : list, optional
        A list of tuples each representing one color option. The tuples are of
        the form ("color-name", [R,G,B]) where R, G, and B are numbers in the
        range of 0 - 255 representing a color in the RGB color system. In each
        trial the colors are presented in random order. Default: the list of the
        six colors "turquoise", "magenta", "granite", "ivory", "maroon", and
        "navy".
    """
    def __init__(
            self,
            label = "color_vocabulary_test",
            time_estimate_per_trial: float = 5.0,
            performance_threshold: int = 4,
            colors: list = None
        ):
        self.label = label
        self.colors = self.colors if colors is None else colors
        self.events = join(
            self.instruction_page(),
            self.trial_maker(
                time_estimate_per_trial,
                performance_threshold,
                self.colors
            )
        )
        super().__init__(self.label, self.events)


    colors = [
        ("turquoise", [174, 72,  56]),
        ("magenta",   [300, 100, 50]),
        ("granite",   [0,   0,   40]),
        ("ivory",     [60,  100, 97]),
        ("maroon",    [0,   100, 25]),
        ("navy",      [240, 100, 25]),
    ]

    def instruction_page(self):
        return InfoPage(Markup(
            """
            <p>We will now perform a quick test to check your ability to name colors.</p>
            <p>
                In each trial, you will be presented with a colored box.
                You must choose which color you see in the box.
            </p>
            """
        ), time_estimate=10)

    def trial_maker(
            self,
            time_estimate_per_trial: float,
            performance_threshold: int,
            colors: list
        ):
        class ColorVocabularyTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score += 1
                passed = score >= performance_threshold
                return {
                    "score": score,
                    "passed": passed
                }

        return ColorVocabularyTrialMaker(
            id_="color_vocabulary",
            trial_class=self.trial(time_estimate_per_trial),
            phase="experiment",
            stimulus_set=self.get_stimulus_set(colors),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False
        )

    def trial(self, time_estimate: float):
        class ColorVocabularyTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "color_vocabulary_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "color_vocabulary_trial",
                    ColourPrompt(
                        self.definition["target_hsl"],
                        "Which color is shown in the box?",
                        text_align="center"
                    ),
                    PushButtonControl(
                        self.definition["choices"],
                        arrange_vertically=False,
                        style="min-width: 150px; margin: 10px"
                    ),
                    time_estimate=time_estimate
                )
        return ColorVocabularyTrial

    def get_stimulus_set(self, colors: list):
        stimuli = []
        words = [x[0] for x in colors]
        for (correct_answer, hsl) in colors:
            choices = words.copy()
            random.shuffle(choices)
            definition = {
                "target_hsl": hsl,
                "choices": choices,
                "correct_answer": correct_answer
            }
            stimuli.append(StimulusSpec(definition=definition, phase="experiment"))
        return StimulusSet("color_vocabulary", stimuli)


class HeadphoneCheck(Module):
    """
    The headphone check makes sure that the participant is wearing headphones. In each trial,
    three sounds separated by silences are played and the participent's must judge which sound
    was the softest (quietest). See the documentation for further details.

    Parameters
    ----------

    label : string, optional
        The label for the color headphone check, default: "headphone_check".

    media : string, optional
        The url under which the images to be displayed can be referenced, default:
        "https://s3.amazonaws.com/headphone-check"

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 7.5.

    performance_threshold : int, optional
        The performance threshold, default: 4.
    """
    def __init__(
            self,
            label = "headphone_check",
            media_url: str = "https://s3.amazonaws.com/headphone-check",
            time_estimate_per_trial: float = 7.5,
            performance_threshold: int = 4,
        ):
        self.label = label
        self.events = join(
            self.instruction_page(),
            self.trial_maker(
                media_url,
                time_estimate_per_trial,
                performance_threshold
            )
        )
        super().__init__(self.label, self.events)

    def instruction_page(self):
        return InfoPage(Markup(
            """
            <p>We will now perform a quick test to check that you are wearing headphones.</p>
            <p>
                In each trial, you will hear three sounds separated by silences.
                Your task will be to judge
                <strong>which sound was softest (quietest).</strong>
            </p>
            """
        ), time_estimate=10)

    def trial_maker(
            self,
            media_url: str,
            time_estimate_per_trial: float,
            performance_threshold: int
        ):
        class HeadphoneTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score +=1
                passed = score >= performance_threshold
                return {
                    "score": score,
                    "passed": passed
                }

        return HeadphoneTrialMaker(
            id_="headphone_check_trials",
            trial_class=self.trial(time_estimate_per_trial),
            phase="experiment",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False
        )

    def trial(self, time_estimate: float):
        class HeadphoneTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "headphone_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "headphone_trial",
                    AudioPrompt(
                        self.definition["url"],
                        "Which sound was softest (quietest) -- 1, 2, or 3?"
                    ),
                    PushButtonControl(
                        ["1", "2", "3"]
                    ),
                    time_estimate=time_estimate
                )
        return HeadphoneTrial

    def get_stimulus_set(self, media_url: str):
        return StimulusSet("headphone_check", [
            StimulusSpec(
                definition={
                    "label": label,
                    "correct_answer": answer,
                    "url": f"{media_url}/antiphase_HC_{label}.wav"
                },
                phase="experiment"
            )
            for label, answer in
            [
                ("ISO", "2"),
                ("IOS", "3"),
                ("SOI", "1"),
                ("SIO", "1"),
                ("OSI", "2"),
                ("OIS", "3")
            ]
        ])

def USstates():
    """
    List compiled using the pycountry package v20.7.3 with
    ``
    sorted([(lang.alpha_2, lang.name) for lang in pycountry.countries
        if hasattr(lang, 'alpha_2')], key=lambda country: country[1])
    ``
    """
    return [
       ("AL", "Alabama"),
       ("AK", "Alaska"),
       ("AZ", "Arizona"),
       ("AR", "Arkansas"),
       ("CA", "California"),
       ("CO", "Colorado"),
       ("CT", "Connecticut"),
       ("DE", "Delaware"),
       ("FL", "Florida"),
       ("GA", "Georgia"),
       ("HI", "Hawaii"),
       ("ID", "Idaho"),
       ("IL", "Illinois"),
       ("IN", "Indiana"),
       ("IA", "Iowa"),
       ("KS", "Kansas"),
       ("KY", "Kentucky"),
       ("LA", "Louisiana"),
       ("ME", "Maine"),
       ("MD", "Maryland"),
       ("MA", "Massachusetts"),
       ("MI", "Michigan"),
       ("MN", "Minnesota"),
       ("MS", "Mississippi"),
       ("MO", "Missouri"),
       ("MT", "Montana"),
       ("NE", "Nebraska"),
       ("NV", "Nevada"),
       ("NH", "New Hampshire"),
       ("NJ", "New Jersey"),
       ("NM", "New Mexico"),
       ("NY", "New York"),
       ("NYC", "New York City"), # **** SPECIAL CASE ****
       ("NC", "North Carolina"),
       ("ND", "North Dakota"),
       ("OH", "Ohio"),
       ("OK", "Oklahoma"),
       ("OR", "Oregon"),
       ("PA", "Pennsylvania"),
       ("RI", "Rhode Island"),
       ("SC", "South Carolina"),
       ("SD", "South Dakota"),
       ("TN", "Tennessee"),
       ("TX", "Texas"),
       ("UT", "Utah"),
       ("VT", "Vermont"),
       ("VA", "Virginia"),
       ("WA", "Washington"),
       ("WV", "West Virginia"),
       ("WI", "Wisconsin"),
       ("WY", "Wyoming"),
       ("DC", "District of Columbia"),
       ("AS", "American Samoa"),
       ("GU", "Guam"),
       ("MP", "Northern Mariana Islands"),
       ("PR", "Puerto Rico"),
       ("UM", "United States Minor Outlying Islands"),
       ("VI", "U.S.Virgin Islands")]

class USRegionOfResidence(ModularPage):
    def __init__(
        self,
        label="US_region",
        prompt="Which state are you joining this experiment from?"
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5
        control = DropdownControl(
            choices=[country[0] for country in USstates()],
            labels=[country[1] for country in USstates()],
            default_text = "Select a state",
            name = self.label,
        )
        super().__init__(self.label, self.prompt, control=control, time_estimate=self.time_estimate)

class Geolocate(Module):
    def __init__(
            self,
            label="geolocation",
            ipinfo_token=None,
            iphub_token=None,
            fail_if_using_VPN=False,
            fail_if_region_not_matched=False,
	    time_estimate_per_trial = 5.0
        ):
        self.label = label
        self.ipinfo_token = ipinfo_token
        self.iphub_token = iphub_token
        self.fail_if_using_VPN = fail_if_using_VPN
        self.fail_if_region_not_matched = fail_if_region_not_matched

        self.events = join(
            CountryOfResidence(),
            CodeBlock(lambda experiment, participant: participant.var.set("cor_reported", participant.answer)), 
            USRegionOfResidence(), 
            CodeBlock(lambda experiment, participant: participant.var.set("ror_reported", participant.answer)), 
            CodeBlock(lambda experiment, participant: participant.var.set("geolocate_country", self.geolocate_details(client_ip=participant.client_ip_address)["country"])),
            CodeBlock(lambda experiment, participant: participant.var.set("geolocate_region", self.geolocate_details(client_ip=participant.client_ip_address)["region"])),
            CodeBlock(lambda experiment, participant: participant.var.set("VPN_Used", self.using_vpn(client_ip=participant.client_ip_address))),
            conditional(
                label="vpn_fail", 
                condition=lambda experiment, participant: self.fail_if_using_VPN == True and participant.var.VPN_Used == True,
                logic_if_true = UnsuccessfulEndPage()
            ),
            conditional(
                label="region_match",
                condition=lambda experiment, participant: self.fail_if_region_not_matched == True and participant.var.ror_reported != participant.var.geolocate_region,
                logic_if_true = UnsuccessfulEndPage()
            )
        )
        super().__init__(self.label, self.events)

    def geolocate_details(self, client_ip):
        if client_ip == "127.0.0.1": # running localhost
            return {
            "country": "US",
            "region": "NYC" # arbitrary
        }
        
        handler = ipinfo.getHandler(self.ipinfo_token)
        details = handler.getDetails(client_ip)

        return {
            "country": details.country,
            "region": details.region
        }

    def using_vpn(self, client_ip):
        if client_ip == "127.0.0.1": # running localhost
            return False

        response = urllib.request.Request("http://v2.api.iphub.info/ip/{}".format(client_ip))
        response.add_header("X-Key", self.iphub_token)
        try:
            response = json.loads(urllib.request.urlopen(response).read().decode())
        except:
            return False

        if response.get("block") == 1:
            return True
        else:
            return False


