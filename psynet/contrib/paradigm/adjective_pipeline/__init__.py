__version__ = "0.1.0"

import hashlib
import json
import pathlib
import random
import subprocess
import zipfile
from collections import Counter
from html import escape, unescape
from typing import Optional

import pandas as pd
from dallinger import db
from dallinger.models import Notification, Participant
from flask import Markup, render_template_string
from pkg_resources import resource_filename

from psynet.modular_page import (
    AudioPrompt,
    Control,
    ImagePrompt,
    ModularPage,
    VideoPrompt,
)
from psynet.page import InfoPage
from psynet.timeline import ExtraResource, join
from psynet.trial.imitation_chain import (
    ImitationChainNetwork,
    ImitationChainNode,
    ImitationChainSource,
    ImitationChainTrial,
    ImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


# The practice trials are currently problematic. It biases people as they only view a limited number of initial
#  starting stimuli with their tags. Also, since we are using across chains it might be that people occupy all the spots
#  in the training phase meaning that not all participants do the same number of practice trials
#  Alternatives are to take within chains for practice, but this would require prepopulated chains and this also biases
#  the participant…


class AdjectiveTarget:
    def __init__(self, url, initial_tags=[]):
        self.url = url
        self.initial_tags = initial_tags


class AdjectiveControl(Control):
    macro = "adjective_input"

    external_template = "adjective_input.html"
    # return os.path.join(os.path.dirname(__file__), "templates", "adjective_input.html")

    def __init__(self, template_args=None):
        super().__init__()
        if template_args is None:
            template_args = {}
        self.template_args = template_args

    @property
    def metadata(self):
        return {
            "template_args": self.template_args,
        }


class AdjectiveTrial(ImitationChainTrial):
    wait_for_feedback = True

    # TODO refactor custom table
    @staticmethod
    def get_user_creations__query(participant_id):
        """
        Query all the adjectives created by a participant.
        """
        return Notification.query.filter_by(property3=str(participant_id)).filter_by(
            event_type="creation"
        )

    def url_and_tag_created_by_user(self, participant_id):
        """
        Get's all urls and tags created by a participant.
        """
        return [
            (adj.property1, adj.property2)
            for adj in self.get_user_creations__query(participant_id).all()
        ]

    @staticmethod
    def get_usernames(worker_ids):
        """
        Looks up participants from a list of ids. If the participants have a field called `username` we'll return it, if
        not we return "worker <participant.id>".
        """
        query = Participant.query.filter(Participant.id.in_(worker_ids))
        if query.count() > 0:
            usernames = []
            for participant in query.all():
                usernames.append(
                    participant.var.username
                    if participant.var.has("username")
                    else f"worker {participant.id}"
                )
            return usernames
        else:
            logger.warning(f"No usernames found for {worker_ids}")
            return []

    def get_feedback_new_word(self, trial_maker, tag, url):
        """
        Prints the feedback if the participant discovered a completely new word. This method can easily be overwritten.
        """
        html_emb = self.preview_stimulus_in_html(url, trial_maker.file_extensions)
        monetary_feedback = (
            f"We award you with a bonus of {trial_maker.new_word_bonus}$!"
            if trial_maker.monetary_feedback
            else ""
        )
        return f"""
            You just unlocked an entirely new word: "{tag}" for {html_emb}<br><br>
            {monetary_feedback}
            <br><br>
            <div class="alert alert-warning" role="alert">
            <strong>Note:</strong> Please keep in mind that if your tags are later flagged as irrelevant,
            your experiment will terminate early.
            </div>
            """

    def check_new_word(self, participant, trial_maker, feedback_dictionary):
        """
        Checks if the participant added an entirely new word in the last trials
        """

        # We can only give feedback if the participant did at least 1 trial
        if self.get_user_creations__query(participant.id).count() > 0:
            # We want to find out which adjectives were used in the experiment so far and how often they were used
            adjective_count = Counter(
                [
                    adj.property2
                    for adj in Notification.query.filter_by(event_type="creation").all()
                ]
            )

            # Avoid to give the same bonus for an unique word over and over again
            if not participant.var.has("bonused_unique_words"):
                participant.var.set(
                    "bonused_unique_words", feedback_dictionary["new_word"]["history"]
                )
            else:
                feedback_dictionary["new_word"]["history"] = participant.var.get(
                    "bonused_unique_words"
                )

            # Now we grab the adjectives that are created by the user and occur only once in all adjectives
            unique_user_adjectives_with_url = [
                [adj.property1, adj.property2]
                for adj in self.get_user_creations__query(participant.id).all()
                if adj.property2 not in feedback_dictionary["new_word"]["history"]
                and adjective_count[adj.property2] == 1
            ]
            if len(unique_user_adjectives_with_url) > 0:
                feedback_dictionary["new_word"]["available"] = True
                url, new_word = unique_user_adjectives_with_url[0]
                feedback_dictionary["new_word"]["history"].append(new_word)
                feedback_dictionary["new_word"]["message"] = self.get_feedback_new_word(
                    trial_maker, new_word, url
                )
        return feedback_dictionary

    @staticmethod
    def preview_stimulus_in_html(url, file_extensions):
        """
        Creates a HTML snippet to display a stimulus, which can be embedded into some markdown.
        """
        if url.lower().endswith(tuple(file_extensions["audio"])):
            return f"""<audio id="audio" controls>
                    <source src="{url}" type="audio/wav">
                    Your browser does not support the audio element.
                    </audio>"""
        elif url.lower().endswith(tuple(file_extensions["video"])):
            source = (
                f'<source src="{url}" type="video/mp4">'
                if url.lower().endswith("mp4")
                else f'<source src="{url}" type="video/webm">'
            )
            return f"""
            <video width="560" controls>{source} Your browser does not support the video tag.</video>
            """
        elif url.lower().endswith(tuple(file_extensions["image"])):
            return f'<img src="{url}" alt="flagged image" class="img-thumbnail">'
        else:
            raise NotImplementedError("Unsupported media type!")

    @staticmethod
    def get_stimulus_type(url, file_extensions):
        """
        Returns the type of media from a url.
        """
        for file_type in file_extensions.keys():
            if url.lower().endswith(tuple(file_extensions[file_type])):
                return file_type

        raise NotImplementedError("Unsupported media type!")

    def get_feedback_flagged(self, flagged_adjectives, trial_maker):
        """
        Prints the feedback in case a word of a participant was flagged. This method can easily be overwritten.
        """
        flagged_lines = []
        flagging_threshold = trial_maker.flagging_threshold

        for flagged_adjective in flagged_adjectives:
            worker_ids = flagged_adjective["worker_ids"]
            users = ", ".join(self.get_usernames(worker_ids))
            tag = flagged_adjective["tag"]
            url = flagged_adjective["url"]
            stimulus_type = self.get_stimulus_type(url, trial_maker.file_extensions)
            html_emb = self.preview_stimulus_in_html(url, trial_maker.file_extensions)
            flagged_lines.append(
                f'{users} flagged your label "{tag}" for {stimulus_type}. {html_emb}'
            )

        message = "<br>".join(flagged_lines) + "<br><br>"

        if len(flagged_adjectives) >= flagging_threshold:
            message += "<b>You will now be excluded from the experiment</b>"
        elif len(flagged_adjectives) == (flagging_threshold - 1):
            message += (
                "<b>If this happens again, you will be excluded from the experiment</b>"
            )
        else:
            message += "<b>If this keeps happening, you will be excluded from the experiment</b>"
        return message

    def check_flagged(self, participant, trial_maker, feedback_dictionary):
        """
        Checks if the participant added a word which has been flagged by other users
        """

        # We can only give feedback if the participant did at least 1 trial
        if self.get_user_creations__query(participant.id).count() > 0:
            # Let's check if the participant got flagged before
            if not participant.var.has("flagged_creations"):
                participant.var.set(
                    "flagged_creations", feedback_dictionary["flagged"]["history"]
                )
            else:
                feedback_dictionary["flagged"]["history"] = participant.var.get(
                    "flagged_creations"
                )

            flagged_adjectives = []
            for url, tag in self.url_and_tag_created_by_user(participant.id):
                query = (
                    Notification.query.filter_by(property1=url)
                    .filter_by(property2=tag)
                    .filter_by(property4=trial_maker.id)
                    .filter_by(event_type="flag")
                )

                # We reset the flagging for an adjective, once the adjective has been added again
                if query.count() % trial_maker.flagging_threshold > 0:
                    # The adjective was flagged by at least one other participant
                    flagged_adjectives.append(
                        {
                            "worker_ids": [adj.property3 for adj in query.all()],
                            "url": url,
                            "tag": tag,
                        }
                    )

                    if (url, tag) not in feedback_dictionary["flagged"]["history"]:
                        feedback_dictionary["flagged"]["history"].append((url, tag))
                        feedback_dictionary["flagged"]["available"] = True
                        feedback_dictionary["flagged"][
                            "message"
                        ] = self.get_feedback_flagged(flagged_adjectives, trial_maker)
        return feedback_dictionary

    def get_feedback_upvoted(self, trial_maker, tag, url, worker_ids, bonus):
        """
        Prints the feedback in case of an upvote. This method can easily be overwritten.
        """
        users = ", ".join(self.get_usernames(worker_ids))
        stimulus_type = self.get_stimulus_type(url, trial_maker.file_extensions)
        html_emb = self.preview_stimulus_in_html(url, trial_maker.file_extensions)
        monetary_feedback = (
            f"<b>You will receive a bonus of {bonus} $</b>"
            if trial_maker.monetary_feedback
            else ""
        )
        return f"""
            {users} upvoted your label "{tag}" for {stimulus_type} {html_emb}<br><br>
            {monetary_feedback}
            """

    def check_upvoted(self, participant, trial_maker, feedback_dictionary):
        """
        Checks if the participant added a word which has been upvoted by other users
        """

        # We can only give feedback if the participant did at least 1 trial
        if self.get_user_creations__query(participant.id).count() > 0:
            if not participant.var.has("upvoted_creations"):
                participant.var.set(
                    "upvoted_creations", feedback_dictionary["upvoted"]["history"]
                )
            else:
                feedback_dictionary["upvoted"]["history"] = participant.var.get(
                    "upvoted_creations"
                )

            for url, tag in self.url_and_tag_created_by_user(participant.id):
                # Only give a bonus for a tag once -> i.e. same tag for two stimuli will not be awarded twice
                if tag not in feedback_dictionary["upvoted"]["history"]:
                    creation_ids = trial_maker.get_creation_ids(url, tag)
                    query = (
                        Notification.query.filter_by(property1=url)
                        .filter_by(property2=tag)
                        .filter_by(property4=trial_maker.id)
                        # Ignore all the upvotes that happened before the adjective was flagged
                        .filter(Notification.id > max(creation_ids))
                        .filter(Notification.event_type.in_(trial_maker.upvote_options))
                    )

                    if query.count() > 0:
                        worker_ids = [adj.property3 for adj in query.all()]
                        feedback_dictionary["upvoted"]["available"] = True
                        feedback_dictionary["upvoted"][
                            "message"
                        ] = self.get_feedback_upvoted(
                            trial_maker, tag, url, worker_ids, trial_maker.upvote_bonus
                        )
                        feedback_dictionary["upvoted"]["history"].append(tag)
                        break
        return feedback_dictionary

    def create_feedback(self, experiment, participant):
        """
        Performs multiple feedback checks and returns the result
        """
        trial_maker = experiment.timeline.get_trial_maker(self.network.trial_maker_id)
        EVENTS = ["new_word", "upvoted", "flagged"]
        feedback_dictionary = {
            event: {"available": False, "message": None, "history": []}
            for event in EVENTS
        }

        feedback_dictionary = self.check_new_word(
            participant, trial_maker, feedback_dictionary
        )
        feedback_dictionary = self.check_flagged(
            participant, trial_maker, feedback_dictionary
        )
        feedback_dictionary = self.check_upvoted(
            participant, trial_maker, feedback_dictionary
        )

        return feedback_dictionary

    def gives_feedback(self, experiment, participant):
        """
        This function makes the decision if there is any trial-to-trial feedback for the participant or not. If there
        is feedback available, it is stored in the participant object.
        """

        # Don't give intermediate feedback from trial to trial during practice
        if self.network.role == "practice":
            return False

        logger.info(
            f"Checking if feedback is available for participant {participant.id}"
        )
        feedback_dictionary = self.create_feedback(experiment, participant)

        feedback_available = [
            feedback["available"] for feedback in feedback_dictionary.values()
        ]

        if not any(feedback_available):
            logger.info(f"No feedback available for participant {participant.id}")
            return False

        # Always immediately display feedback to the user
        if feedback_dictionary["flagged"]["available"]:
            # Here we update the flagged creations
            participant.var.set(
                "flagged_creations", feedback_dictionary["flagged"]["history"]
            )
            participant.var.set(
                "feedback", escape(feedback_dictionary["flagged"]["message"])
            )
            participant.var.set("custom_bonus", 0)
            return True
        else:

            # On average display this positive feedback every `show_positive_feedback_every` pages
            trial_maker = experiment.timeline.get_trial_maker(
                self.network.trial_maker_id
            )
            if trial_maker.show_positive_feedback_every == 0:
                give_feedback = False
            else:
                give_feedback = (
                    random.randint(0, trial_maker.show_positive_feedback_every - 1) == 0
                )

            if not give_feedback:
                # We decided to give no feedback this time!
                return False
            else:
                available_feedback = {
                    key: feedback
                    for key, feedback in feedback_dictionary.items()
                    if feedback["available"]
                }
                idx = random.randint(0, len(available_feedback) - 1)

                key = list(available_feedback.keys())[idx]

                if key == "upvoted":
                    participant.var.set(
                        "upvoted_creations", available_feedback[key]["history"]
                    )
                    if trial_maker.monetary_feedback:
                        participant.inc_performance_bonus(trial_maker.upvote_bonus)
                elif key == "new_word":
                    participant.var.set(
                        "bonused_unique_words", available_feedback[key]["history"]
                    )
                    if trial_maker.monetary_feedback:
                        participant.inc_performance_bonus(trial_maker.new_word_bonus)

                participant.var.set(
                    "feedback", escape(available_feedback[key]["message"])
                )
                return True

    def show_feedback(self, experiment, participant):
        """
        Defines how we show the feedback. The decision to present feedback was made in `gives_feedback`. Feedback is
        stored in the participant object.
        """
        feedback_page = InfoPage(Markup(unescape(participant.var.get("feedback"))))
        return feedback_page

    def get_adjective_control(self, template_args):
        """
        Makes sure all expected template arguments (`template_args`) are present
        """

        if "stimulus_type_singular" in template_args.keys():
            stimulus_type = template_args["stimulus_type_singular"]

            if "initial_instruction" not in template_args.keys():
                logger.info(
                    f"Creating generic initial instruction for stimulus type: {stimulus_type}"
                )

                template_args["initial_instruction"] = Markup(
                    f"""
                                <h3 for="new_tags">Add some initial tags</h3>
                                <div class="alert alert-primary" role="alert">
                                Type in tags describing the {stimulus_type}. You can either select tags from a dropdown
                                 list or create entirely new ones. Submit your response for a new tag by pressing the
                                <kbd>enter</kbd> key. <strong>You can add more than one tag.</strong>
                                </div>
                                """
                )

            if "later_instruction" not in template_args.keys():
                logger.info(
                    f"Creating generic instruction displayed after first iteration for stimulus type: {stimulus_type}"
                )

                template_args["later_instruction"] = Markup(
                    f"""
                <h3 for="new_tags">Are any tags missing?</h3>
                <div class="alert alert-primary" role="alert">
                Type in words describing the {stimulus_type}, that are missing above. You can either select tags
                from a dropdown list or create entirely new ones. Submit your response for a new tag by pressing the
                <kbd>enter</kbd> key. <strong>You can add more than one tag.</strong>
                </div>
                """
                )

        assert (
            sum(
                [
                    key in template_args.keys()
                    for key in ["initial_instruction", "later_instruction"]
                ]
            )
            == 2
        ), "You must supply an instruction to the adjective trial!"

        return AdjectiveControl(template_args)

    @staticmethod
    def audio_visual_js_injection(
        stimulus_type, play_duration=None, randomize_start=None
    ):
        attach_to_id = (
            "prompt-text" if stimulus_type == "audio" else "prompt-video-container"
        )
        if stimulus_type == "video":
            try:
                float(play_duration)
            except ValueError:
                logger.error(
                    "`play_duration` is not convertible to a float! Silently defaulting to 0."
                )
                play_duration = 0
            end_row = (
                "" if play_duration == 0 else "endAt = startAt + min_play_duration;"
            )
            media_duration = (
                "psynet.audio.prompt.buffer.duration"
                if stimulus_type == "audio"
                else "psynet.video.prompt.player.duration"
            )
            start_str = (
                f"({media_duration} - min_play_duration) * Math.random()"
                if randomize_start
                else "0"
            )
            prepare_media_fn = f"""
                    $( document ).ready(function(){{
                        // Initialize an empty array to store the starting times of the video
                        metadata['start_times_video'] = [];
                    }})
                    prepare_media = function(){{
                        var min_play_duration = {play_duration};
                        startAt = {start_str};
                        {end_row}
                        psynet.log.info('Video starting at: ' + startAt)
                        metadata['start_times_video'].push(startAt);
                    }}
                """
        else:
            if sum([arg is None for arg in [play_duration, randomize_start]]) < 2:
                logger.warning(
                    "The arguments play_duration and randomize_start may only be used for video!"
                )
            prepare_media_fn = "prepare_media = function(){}"
        return f"""
        <script>
                {prepare_media_fn}
                psynet.trial.onEvent("submitEnable", psynet.submit.disable);
                custom_play = function() {{
                    psynet.page.prompt.stop();
                    prepare_media();
                    psynet.page.prompt.play();
                    $('.btn').each(function (idx, x) {{
                        x.disabled = true
                    }})
                }}
                enable_buttons = function() {{
                    $('.btn').each(function (idx, x) {{
                        x.disabled = false
                    }})
                }}
                $( document ).ready(function(){{
                    $('#{attach_to_id}').append(createElementFromHTML('<button class="btn btn-secondary mt-3" id="play_button" onclick="custom_play();">Play again</button>'))
                    psynet.trial.onEvent("promptStart", custom_play);
                    psynet.trial.onEvent("promptEnd", enable_buttons);
                }})
                </script>
        """

    def show_trial(self, experiment, participant):
        """
        Shows the adjective trial
        """
        tags = self.definition["tags"]
        hashes = [hashlib.sha1(t.encode()).hexdigest() for t in tags]
        logger.info(self.definition)
        url = self.definition["url"]
        trial_maker = experiment.timeline.get_trial_maker(self.network.trial_maker_id)

        template_args = {
            "tag_dict": dict(zip(hashes, tags)),
            "available_adjectives": self.get_all_adjectives(),
            "upvote_n_buttons": trial_maker.upvote_n_buttons,
            "upvote_icon": trial_maker.upvote_icon,
            **trial_maker.template_args,
        }

        def get_if_exists(dict_obj, key, fallback):
            return dict_obj[key] if key in dict_obj.keys() else fallback

        width = get_if_exists(template_args, "width", 400)

        if url.lower().endswith(tuple(trial_maker.file_extensions["audio"])):
            prompt = AudioPrompt(
                url,
                Markup(
                    f"""{self.audio_visual_js_injection('audio')}
                """
                ),
            )
        elif url.lower().endswith(tuple(trial_maker.file_extensions["video"])):
            play_duration = get_if_exists(template_args, "play_duration", 0)
            randomize_start = get_if_exists(template_args, "randomize_start", False)
            prompt = VideoPrompt(
                url,
                Markup(
                    f"""
                <style>
                    #prompt-video-container {{
                        width: {width}px;
                        position: fixed;
                        right: 2em;
                        display: block !important;
                    }}
                    #content {{
                        width: calc(100% - {width}px);
                    }}
                </style>
                {self.audio_visual_js_injection('video', play_duration, randomize_start)}
                """
                ),
                text_align="center",
                width=f"{width}px",
                hide_when_finished=False,
            )
        elif url.lower().endswith(tuple(trial_maker.file_extensions["image"])):
            # TODO refactor this
            height = get_if_exists(template_args, "height", 400)
            prompt = ImagePrompt(
                url,
                Markup(
                    f"""
                <style>
                    #prompt-image {{
                        width: {width}px;
                        position: fixed;
                        right: 2em;
                    }}
                    #content {{
                        width: calc(100% - {width}px);
                    }}
                </style>
                """
                ),
                width=width,
                height=height,
            )
        else:
            raise NotImplementedError("Unsupported media type!")

        return ModularPage(
            "rate_trial",
            prompt,
            control=self.get_adjective_control(template_args),
        )

    def get_all_adjectives(self):
        """
        Returns all adjectives produced in the main part of the experiment (i.e. not during the practice session)
        """
        return list(
            set(
                [
                    adj.property2
                    for adj in Notification.query.filter_by(event_type="creation").all()
                ]
            )
        )


class AdjectiveNetwork(ImitationChainNetwork):
    """
    Defines each adjective network
    """

    def make_definition(self):
        trial_maker = self.experiment.timeline.get_trial_maker(self.trial_maker_id)
        targets = trial_maker.targets
        idx = self.id % len(targets)
        target = targets[idx]
        initial_tags = target.initial_tags
        url = target.url
        if initial_tags != []:
            logger.info(f"Prepopulate network {self.id} with: {initial_tags}")
            for tag in initial_tags:
                trial_maker.create_notification(
                    url, tag.lower(), "creation", "experiment", trial_maker.id
                )
        return {
            "url": url,
            "initial_tags": initial_tags,
            "stimulus_type": AdjectiveTrial.get_stimulus_type(
                url, trial_maker.file_extensions
            ),
        }


class AdjectiveSource(ImitationChainSource):
    """
    Defines the initial state of each adjective chain
    """

    def generate_seed(self, network, experiment, participant):
        return {
            "url": network.definition["url"],
            "tags": network.definition["initial_tags"],
        }


class AdjectiveNode(ImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "adjective_node"}

    def summarize_trials(self, trials: list, experiment, participant):
        trial = trials[len(trials) - 1]
        trial_maker = experiment.timeline.get_trial_maker(trial.trial_maker_id)
        return trial_maker._summarize_trial(trial, False, trial_maker)


class AdjectivePipeline(ImitationChainTrialMaker):
    """
    High level abstraction of the adjective pipeline (Work In Progress!)

    Parameters
    ----------

    targets
        A list of urls or of instances of the AdjectiveTarget class.

    num_trials_per_participant
        Maximum number of trials that each participant may complete;
        once this number is reached, the participant will move on
        to the next stage in the timeline.

    base_time_estimate
        Time estimate in seconds just to watch a single stimulus

    tag_rating_time_estimate
        Time estimate in seconds to rate a tag, default 1 second.

    new_tag_time_estimate
        Time estimate in seconds to create a new tag, default 4 seconds.

    max_new_tags
        Maximal number of new tags a participant get's paid out per trial (i.e. max max_new_tags *
        new_tag_time_estimate), default 10. This avoids that a fraudulent participants just keeps adding irrelevant
        tags to get a high performance bonus.

    max_rating
        Maximal number of ratings we pay out per trial (i.e. max max_rating *
        new_tag_time_estimate), default 10. This avoids that a fraudulent participants just keeps adding irrelevant
        tags to get a high performance bonus.

    phase
        Label for this phase of the experiment, either "practice" or "experiment".

    min_iterations
        Mininmal number of iterations per chain, default 10 iterations.

    max_iterations
        Maximal number of iterations per chain, default 10 iterations.

    stop_early_if
        Condition to end a chain early if iteration > min_iterations. Default: {"mean_rating": 3, "num_adjectives": 2,
        "min_upvotes": 3}. This means to end a chain early, there must be at least 2 adjectives, that received at least
         3 upvotes per tag and with a mean rating of 3. You can overwrite these settings.

    TODO fill in the remaining parameters
        upvote_icon: str = "star",
        upvote_n_buttons=None,
        flagging_threshold: int = 2,
        prune_flags: bool = False,
        network_class=AdjectiveNetwork,
        source_class=AdjectiveSource,
        trial_class=AdjectiveTrial,
        new_word_bonus: Optional[float] = None,
        upvote_bonus: Optional[float] = None,
        show_positive_feedback_every: int = 0,
        monetary_feedback: bool = True,
        practice_threshold: int = 0,
        template_args=None,
        prepopulate_networks=False,
        allow_revisiting: bool = False,
    """

    file_extensions = {
        "audio": [".wav", ".mp3"],
        "video": [".mp4", ".webm"],
        "image": [".jpg", ".jpeg", ".png"],
    }

    upvote_n_buttons = 5

    def __init__(
        self,
        *,
        id_,
        targets: list,
        num_trials_per_participant: int,
        base_time_estimate: int,
        tag_rating_time_estimate: int = 1,
        new_tag_time_estimate: int = 4,
        max_new_tags: int = 10,
        max_rating: int = 15,
        phase: str,
        min_iterations: int = 10,
        max_iterations: int = 20,
        stop_early_if=None,
        upvote_icon: str = "star",
        upvote_n_buttons=None,
        flagging_threshold: int = 2,
        prune_flags: bool = False,
        network_class=AdjectiveNetwork,
        source_class=AdjectiveSource,
        trial_class=AdjectiveTrial,
        new_word_bonus: Optional[float] = None,
        upvote_bonus: Optional[float] = None,
        show_positive_feedback_every: int = 0,
        monetary_feedback: bool = True,
        practice_threshold: int = 0,
        template_args=None,
        allow_revisiting: bool = False,
    ):
        # Avoid default arguments to be mutable
        if template_args is None:
            template_args = dict()
        if stop_early_if is None:
            stop_early_if = {"mean_rating": 3, "num_adjectives": 2, "min_upvotes": 3}

        # Assertions
        assert phase in [
            "experiment",
            "practice",
        ], "Only experiment and practice phase are supported!"
        assert (
            len(targets) > 0
        ), "You need to specify at least one url or AdjectiveTarget"

        type_tuple = (
            sum([isinstance(target, str) for target in targets]),
            sum([isinstance(target, AdjectiveTarget) for target in targets]),
        )

        n = len(targets)

        # Either you only specify Targets or just urls
        assert (0, n) in [(0, n), (n, 0)]

        if type_tuple == (n, 0):
            # Internally convert urls to Targets
            targets = [AdjectiveTarget(url) for url in targets]

        flat_extensions = tuple(
            [item for ext in self.file_extensions.values() for item in ext]
        )

        assert all(
            [target.url.lower().endswith(flat_extensions) for target in targets]
        ), "Some urls have a non-supported file extension!"

        assert num_trials_per_participant > 0
        if phase == "practice":
            assert num_trials_per_participant == len(targets)
        assert base_time_estimate > 0
        assert tag_rating_time_estimate > 0
        assert min_iterations > 0
        assert max_iterations > min_iterations
        self.min_iterations = min_iterations
        self.max_iterations = max_iterations

        assert stop_early_if is None or all(
            [
                key in ["mean_rating", "num_adjectives", "min_upvotes"]
                for key in stop_early_if.keys()
            ]
        )
        self.stop_early_if = stop_early_if

        assert upvote_icon in ["star"], "Currently only star icons are supported"
        self.upvote_icon = upvote_icon
        if upvote_n_buttons is not None:
            self.upvote_n_buttons = upvote_n_buttons
        assert self.upvote_n_buttons > 0

        self.upvote_options = [str(s + 1) for s in range(self.upvote_n_buttons)]

        # Find an upper bound of the maximum trial duration. We set this based on the stimulus viewing
        # duration + time per rating X the max expected number of words
        self.response_timeout_sec = max(
            60,  # at least a minute
            base_time_estimate * 2
            + new_tag_time_estimate * max_new_tags
            + max_iterations * max_rating * tag_rating_time_estimate,
        )

        self.monetary_feedback = monetary_feedback

        assert flagging_threshold >= 0

        prepare_n_bonus = sum([b is not None for b in [new_word_bonus, upvote_bonus]])

        assert (
            (not monetary_feedback)
            or (show_positive_feedback_every == 0 and prepare_n_bonus == 0)
            or (show_positive_feedback_every > 0 and prepare_n_bonus > 0)
        ), "If you want to show a bonus to the participant, you need to specify at least one bonus amount!"

        assert practice_threshold >= 0
        practice_n_repeat_trials = (
            0 if phase == "experiment" else num_trials_per_participant
        )
        assert (
            phase == "experiment"
            and practice_threshold == 0
            and practice_n_repeat_trials == 0
        ) or (phase == "practice" and practice_threshold <= practice_n_repeat_trials)

        assert all(
            [type(target.initial_tags) == list for target in targets]
        ), "The tags for each chain must consist of lists of strings"
        assert all(
            [type(tag) == str for target in targets for tag in target.initial_tags]
        ), "All tags must be strings!"

        # Ad hoc classes
        trial_class.time_estimate = base_time_estimate

        self.targets = targets
        num_chains_per_experiment = len(targets)
        self.base_time_estimate = base_time_estimate
        self.network_class = network_class
        self.source_class = source_class
        self.trial_class = trial_class
        self.phase = phase
        self.template_args = template_args
        self.show_positive_feedback_every = show_positive_feedback_every
        self.practice_threshold = practice_threshold
        self.flagging_threshold = flagging_threshold
        self.prune_flags = prune_flags
        self.new_word_bonus = new_word_bonus
        self.upvote_bonus = upvote_bonus
        self.tag_rating_time_estimate = tag_rating_time_estimate
        self.new_tag_time_estimate = new_tag_time_estimate
        self.max_new_tags = max_new_tags
        self.max_rating = max_rating

        check_performance_at_end = practice_threshold > 0 and phase == "practice"
        check_performance_every_trial = phase == "experiment"

        if phase == "experiment":
            num_iterations_per_chain = max_iterations
        else:
            num_iterations_per_chain = int(
                (num_trials_per_participant / num_chains_per_experiment)
                * max_iterations
            )

        super().__init__(
            id_=id_,
            network_class=network_class,
            trial_class=trial_class,
            node_class=AdjectiveNode,
            source_class=source_class,
            phase=phase,
            chain_type="across",
            num_trials_per_participant=num_trials_per_participant,
            num_repeat_trials=practice_n_repeat_trials,  # Only applies if phase == 'practice'
            num_iterations_per_chain=num_iterations_per_chain,
            num_chains_per_participant=None,
            num_chains_per_experiment=num_chains_per_experiment,
            trials_per_node=1,
            balance_across_chains=True,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            recruit_mode="num_trials",
            target_num_participants=None,
            allow_revisiting_networks_in_across_chains=allow_revisiting,
        )
        self.elts = join(
            self.elts,
            ExtraResource(
                resource_filename(
                    "psynet",
                    "contrib/paradigm/adjective_pipeline/resources/libraries/bootstrap-tagsinput/bootstrap-tagsinput-0.8.0.js",
                ),
                "/static/scripts/bootstrap-tagsinput-0.8.0.js",
            ),
            ExtraResource(
                resource_filename(
                    "psynet",
                    "contrib/paradigm/adjective_pipeline/resources/libraries/typeahead/typeahead-0.11.1.js",
                ),
                "/static/scripts/typeahead-0.11.1.js",
            ),
            ExtraResource(
                resource_filename(
                    "psynet",
                    "contrib/paradigm/adjective_pipeline/resources/images/icons/flag-fill.svg",
                ),
                "/static/images/icons/flag-fill.svg",
            ),
            ExtraResource(
                resource_filename(
                    "psynet",
                    "contrib/paradigm/adjective_pipeline/resources/images/icons/star.svg",
                ),
                "/static/images/icons/star.svg",
            ),
            ExtraResource(
                resource_filename(
                    "psynet",
                    "contrib/paradigm/adjective_pipeline/templates/adjective_input.html",
                ),
                "/templates/adjective_input.html",
            ),
        )

    # def experiment_setup_routine(self, experiment):
    #     n_stimuli = len(self.targets)
    #     # For each stimuli we only do the minimum number of iterations
    #     # and pay participants for watching the stimulus + giving one rating or new tag
    #
    #     min_payment_trial_maker = self.seconds_to_dollars(
    #         n_stimuli
    #         * self.min_iterations
    #         * (
    #             self.base_time_estimate
    #             + max(self.new_tag_time_estimate, self.tag_rating_time_estimate)
    #         ),
    #         experiment.var.wage_per_hour,
    #     )
    #
    #     # For each stimulus we do the MAXIMUM number of iterations
    #     # and pay participants for watching the stimulus
    #     # participants give the maximum number of tags
    #     # participants give the maximum number of ratings
    #     # assume payment of a bonus (upvote or new word) after every trial
    #     max_payment_trial_maker = (
    #         n_stimuli
    #         * self.max_iterations
    #         * (
    #             self.seconds_to_dollars(
    #                 self.base_time_estimate
    #                 + self.max_new_tags * self.new_tag_time_estimate
    #                 + self.max_rating * self.tag_rating_time_estimate,
    #                 experiment.var.wage_per_hour,
    #             )
    #             + max(
    #                 [
    #                     self.new_word_bonus if self.new_word_bonus is not None else 0,
    #                     self.upvote_bonus if self.upvote_bonus is not None else 0,
    #                 ]
    #             )
    #         )
    #     )
    #
    #     logger.info(
    #         f"Setting the response timeout for trialmaker {self.id} to {(self.response_timeout_sec / 60):.2f} minutes"
    #     )
    #
    #     if self.allow_revisiting_networks_in_across_chains:
    #         logger.warning(
    #             """
    #         You set `allow_revisiting` to True. This should only be used for debugging. NEVER USE THIS WHEN DEPLOYING!
    #         """
    #         )
    #
    #     logger.info(
    #         f"""
    #                 In the best case scenario we pay {min_payment_trial_maker:.2f}$ to annotate {n_stimuli} stimuli in
    #                 trialmaker {self.id}. In the worst case we pay {max_payment_trial_maker:.2f}$.
    #                 """
    #     )

    def finalize_trial(self, answer, trial, experiment, participant):
        super().finalize_trial(answer, trial, experiment, participant)

        is_main_experiment = trial.network.role == "experiment"
        trial_maker = experiment.timeline.get_trial_maker(trial.trial_maker_id)
        self._summarize_trial(trial, is_main_experiment, trial_maker)
        bonus_per_rating = experiment.var.wage_per_hour * (
            self.tag_rating_time_estimate / 60**2
        )
        n_given_ratings = len(answer["ratings"])
        n_ratings = min(self.max_rating, n_given_ratings)
        if trial_maker.monetary_feedback and n_given_ratings > self.max_rating:
            logger.warning(
                f"Participant {participant.id} in trial {trial.id} rated {n_given_ratings} tags which is more than"
                f" the maximum allowed number of ratings per trial, which is {self.max_rating}."
            )

        full_rating_bonus = n_ratings * bonus_per_rating

        bonus_per_new_tag = experiment.var.wage_per_hour * (
            self.new_tag_time_estimate / 60**2
        )
        n_given_tags = len(answer["new_tags"])
        n_new_tags = min(self.max_new_tags, n_given_tags)
        if trial_maker.monetary_feedback and n_given_tags > self.max_new_tags:
            logger.warning(
                f"Participant {participant.id} in trial {trial.id} entered {n_given_tags} new tags which is more than"
                f" the maximum allowed number of tags, which is {self.max_new_tags}."
            )
        full_new_tag_bonus = n_new_tags * bonus_per_new_tag

        total_performance_bonus = full_rating_bonus + full_new_tag_bonus

        bonus_payment_lines = []

        def append_payment_line(n, bonus, singular, plural):
            if n > 0:
                word = singular if n == 1 else plural
                bonus_payment_lines.append(f"{bonus}$ for {n} {word}")

        append_payment_line(n_ratings, full_rating_bonus, "rating", "ratings")
        append_payment_line(n_new_tags, full_new_tag_bonus, "new tag", "new tags")
        if trial_maker.monetary_feedback:
            logger.info(
                f"""
                Paying participant {participant.id} a total performance bonus of {total_performance_bonus}$ consisting of:
                {' and '.join(bonus_payment_lines)}.
                """
            )
            participant.inc_performance_bonus(total_performance_bonus)

    def seconds_to_dollars(self, seconds, wage_per_hour):
        return wage_per_hour * (seconds / 60**2)

    @staticmethod
    def _summarize_trial(trial, is_main_experiment, trial_maker):
        url = trial.definition["url"]
        tags = []
        logger.info(f"Answer: {trial.answer}")

        if len(trial.answer["ratings"]) > 0:
            for tag, rating in trial.answer["ratings"].items():
                if rating == "flag":
                    logger.warning(f'The tag "{tag}" was flagged')

                tags.append(tag)

                if is_main_experiment:
                    # Only store flags and upvotes during the main experiment
                    trial_maker.create_notification(
                        url, tag, rating, trial.participant_id, trial.trial_maker_id
                    )

        if "new_tags" in trial.answer.keys():
            for new_tag in trial.answer["new_tags"]:
                tags.append(new_tag.lower())
                if is_main_experiment:
                    # Only store new words during the main experiment
                    trial_maker.create_notification(
                        url,
                        new_tag.lower(),
                        "creation",
                        trial.participant_id,
                        trial.trial_maker_id,
                    )

        flagged_adj_dict = Counter(
            [
                adj.property2
                for adj in Notification.query.filter_by(property1=url)
                .filter_by(property4=trial.trial_maker_id)
                .filter_by(event_type="flag")
                .all()
            ]
        )

        created_adj_dict = Counter(
            [
                adj.property2
                for adj in Notification.query.filter_by(property1=url)
                .filter_by(property4=trial.trial_maker_id)
                .filter_by(event_type="creation")
                .all()
            ]
        )

        # Remove adjectives when they are flagged more than `flagging_threshold`
        #  The removed tags can re-emerge
        for tag, total_n_flags in flagged_adj_dict.items():
            total_n_creations = created_adj_dict[tag]
            relative_n_flags = total_n_flags - trial_maker.flagging_threshold * (
                total_n_creations - 1
            )
            # logger.info(f'Relative number of flags for tag "{tag}": {relative_n_flags}')
            if relative_n_flags == trial_maker.flagging_threshold:
                logger.warning(
                    f'Removing tag "{tag}" from {tags}. The tag "{tag}" can be added again in later iterations.'
                )
                tags = [old_tag for old_tag in tags if tag != old_tag]

        if (
            trial.degree > trial_maker.min_iterations  # minimal depth of iterations
            and not trial.failed  # only count trials that are not failed
            and not trial.is_repeat_trial  # don't count repeat trials
            and trial.answer is not None  # don't include if the answer is empty
            and trial_maker.stop_early_if
            is not None  # only do early stopping if we specified it
        ):
            n_qualifying_adjectives = 0
            for tag in tags:
                creation_ids = trial_maker.get_creation_ids(url, tag)
                upvotes_per_tag = [
                    int(upvote.event_type)
                    for upvote in (
                        Notification.query.filter_by(property1=url)
                        .filter_by(property2=tag)
                        .filter_by(property4=trial_maker.id)
                        # Ignore all the upvotes that happened before the adjective was flagged
                        .filter(Notification.id > max(creation_ids))
                        .filter(Notification.event_type.in_(trial_maker.upvote_options))
                        .all()
                    )
                ]

                n_upvotes = len(upvotes_per_tag)
                if n_upvotes < trial_maker.stop_early_if["min_upvotes"]:
                    continue
                mean_rating = sum(upvotes_per_tag) / n_upvotes
                if mean_rating < trial_maker.stop_early_if["mean_rating"]:
                    continue
                n_qualifying_adjectives += 1

            if n_qualifying_adjectives >= trial_maker.stop_early_if["num_adjectives"]:
                logger.info(
                    f"Network {trial.network_id} converged early at iteration {trial.degree}"
                )
                trial.network.full = True
                db.session.commit()  # Make sure it's committed

        return {"url": url, "tags": tags}

    def performance_check(self, experiment, participant, participant_trials):
        if self.phase == "experiment":
            # Feedback during the main experiment
            if not participant.var.has("flagged_creations"):
                flagged_creations = []
                participant.var.set("flagged_creations", flagged_creations)
            else:
                flagged_creations = participant.var.get("flagged_creations")
            return {
                "score": len(flagged_creations),
                "passed": len(flagged_creations) < self.flagging_threshold,
            }
        else:
            # Feedback after the practice
            response_dict = {}
            repeat_dict = {}
            for trial in participant_trials:
                url = trial.definition["url"]
                if trial.is_repeat_trial:
                    repeat_dict[url] = list(trial.answer["ratings"].values())
                else:
                    response_dict[url] = list(trial.answer["ratings"].values())

            response_urls = sorted(response_dict)
            repeat_urls = sorted(repeat_dict)
            assert response_urls == repeat_urls

            # FUTURE: do inline flattening here
            initial_response = []
            [initial_response.extend(response_dict[url]) for url in repeat_urls]

            # FUTURE: do inline flattening here too
            repeat_response = []
            [repeat_response.extend(repeat_dict[url]) for url in repeat_urls]

            if len(initial_response) == 0 and len(repeat_response) == 0:
                # Let the first participants of the chain always pass
                score = 1
            else:
                summed_matches = sum(
                    [
                        repeat_response[idx] == resp
                        for idx, resp in enumerate(initial_response)
                    ]
                )
                score = summed_matches / len(repeat_response)
            return {"score": score, "passed": score >= self.practice_threshold}

    @staticmethod
    def create_notification(url, adjective, event_type, worker_id, trial_maker_id):
        # Create notifications
        notif = Notification(assignment_id=0, event_type=event_type)
        notif.failed = False
        notif.property1 = url
        notif.property2 = adjective
        notif.property3 = worker_id
        notif.property4 = trial_maker_id
        db.session.add(notif)
        db.session.commit()

    def get_creation_ids(self, url, tag):
        # Add id of 1 to never return an empty sequence
        # This may happen in entirely new chains without any tag
        return [
            creation.id
            for creation in (
                Notification.query.filter_by(property1=url)
                .filter_by(property2=tag)
                .filter_by(property4=self.id)
                .filter_by(event_type="creation")
                .all()
            )
        ] + [1]


class AdjectiveExporter:
    @staticmethod
    def unzip_experiment(zip_path, unzip_to):
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(unzip_to)
        return True

    @staticmethod
    def dallinger_export(app_name, scrub=False):
        scrub_arg = "" if scrub else " --noscrub"
        subprocess.call(f"dallinger export --app {app_name}{scrub_arg}", shell=True)
        data_dir = f"data/{app_name}-data/"
        zip_path = f"data/{app_name}-data.zip"
        AdjectiveExporter.unzip_experiment(zip_path, data_dir)
        return data_dir

    @staticmethod
    def lookup_filetype(url):
        for media_type, extensions in AdjectivePipeline.file_extensions.items():
            if url.endswith(extensions):
                return media_type
        return None

    @staticmethod
    def save_ratings_to_csv(ratings, csv_out_path):
        ratings.to_csv(csv_out_path, index=False)
        return True

    @staticmethod
    def export_pipelines_from_archive(
        data_dir, csv_out_path=None, export_only="experiment"
    ):
        assert export_only in ["experiment", "practice", None]
        network_query = "type=='AdjectiveNetwork'"
        if export_only is not None:
            network_query += f" and role=='{export_only}'"
        networks = (
            pd.read_csv(data_dir + "data/network.csv")
            .sort_values("id")
            .query(network_query)
        )
        network_ids = networks.id  # This is need for the trial query below
        trials = (
            pd.read_csv(data_dir + "data/info.csv")
            .sort_values("id")
            .query(
                "type == 'AdjectiveTrial' and failed == 'f' and is_repeat_trial == 'f' and not answer.isnull()"
            )
            .query("network_id.isin(@network_ids)")
        )

        ratings = pd.DataFrame()
        for network_id in set(network_ids):
            iteration = 0
            for idx, row in trials.query(f"network_id == {network_id}").iterrows():
                iteration += 1
                if iteration == 1:
                    continue
                answer = json.loads(row.answer)
                rating_dict = answer["ratings"]
                ratings = ratings.append(
                    pd.DataFrame(
                        {
                            "url": json.loads(row.definition)["url"],
                            "iteration": iteration,
                            "tag": list(rating_dict.keys()),
                            "rating": list(rating_dict.values()),
                            "new_tags": ", ".join(answer["new_tags"]),
                            "network_id": network_id,
                        }
                    )
                )
        if csv_out_path is not None:
            AdjectiveExporter.save_ratings_to_csv(ratings, csv_out_path)
        return ratings

    @staticmethod
    def export_pipelines_from_database(networks, export_only=None):
        assert export_only in ["experiment", "practice", None]
        ratings = pd.DataFrame()
        for network in networks:
            if export_only is not None:
                if network.role != export_only:
                    continue
            iteration = 0
            infos = network.infos()
            info_dict = dict(zip([info.id for info in infos], infos))
            info_dict = dict(sorted(info_dict.items()))  # sort it
            for info in info_dict.values():
                if (
                    not info.failed
                    and not info.is_repeat_trial
                    and info.answer is not None
                ):
                    iteration += 1
                    if iteration == 1:
                        continue
                    answer = info.answer
                    rating_dict = answer["ratings"]
                    ratings = ratings.append(
                        pd.DataFrame(
                            {
                                "url": network.definition["url"],
                                "iteration": iteration,
                                "tag": list(rating_dict.keys()),
                                "rating": list(rating_dict.values()),
                                "new_tags": ", ".join(answer["new_tags"]),
                                "network_id": network.id,
                            }
                        )
                    )
        return ratings

    @staticmethod
    def required_css():
        return read_template_string("adjective_styles.css", flatten=True).replace(
            "\n", ""
        )

    @staticmethod
    def save_html(path, string):
        with open(path, "w") as f:
            f.write(string)
        return True

    @staticmethod
    def generate_html(
        ratings,
        html_out_path=None,
        upvote_n_buttons=AdjectivePipeline.upvote_n_buttons,
        title="Adjective Ratings",
    ):
        def print_new_tags(new_tags):
            new_tags = [
                f"<span class='badge badge-dark'>{tag}</span>" for tag in new_tags
            ]
            return f"<span>{' '.join(new_tags)}</span>"

        if html_out_path is None:
            html_out = ""
        else:
            html_out = (
                """
                                <!DOCTYPE html>
                                <html lang="en">
                                <head>
                                    <meta charset="UTF-8">
                                    <title>"""
                + title
                + f"""</title>
                        </head>
                        <body>
                        <link rel="stylesheet"
                        href="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap.min.css"
                        integrity="sha384-TX8t27EcRE3e/ihU7zmQxVncDAy5uIKz4rEkgIXeMed4M0jlfIDPvg6uqKI2xXr2"
                        crossorigin="anonymous"><style>
                        {AdjectiveExporter.required_css()}
                        </style>
                        """
            )
        html_out += '<div class="container">'

        network_ids = list(set(ratings.network_id))

        for network_id in network_ids:
            network_ratings = ratings.query(f"network_id == {network_id}")
            html_out += f"<h1>Network {network_id}</h1>"
            html_out += AdjectiveTrial.preview_stimulus_in_html(
                network_ratings.url.iloc[0], AdjectivePipeline.file_extensions
            )

            min_iter = min(network_ratings.iteration)
            max_iter = max(network_ratings.iteration)
            new_tags = network_ratings.query(f"iteration == {min_iter}").tag.to_list()
            html_out += '<div class="media-item">'
            html_out += print_new_tags(new_tags)
            html_out += "</div>"
            for iteration in range(min_iter, max_iter + 1):
                html_out += '<div class="media-item">'
                iteration_ratings = network_ratings.query(f"iteration == {iteration}")
                for idx, row in iteration_ratings.iterrows():
                    rating = row["rating"]
                    tag = row["tag"]
                    background = "bg-danger" if rating == "flag" else "bg-success"
                    html_out += f"""
                                            <div class="tag-item bg-secondary">
                                                <div class="row tag-name {background}" id="{tag}-tag">{tag}</div>
                                                <div class="btn-group btn-group-toggle" data-toggle="buttons">"""
                    is_flagged = rating == "flag"
                    rating_number = int(rating) if not is_flagged else None
                    for n in range(1, upvote_n_buttons + 1):
                        html_out += f"""<label class="btn btn-secondary icon rating{n} star"
                                                       style='{'opacity: 1' if not is_flagged and n <= rating_number else 'opacity: 0.5'}'>
                                                    <input type="radio"'>
                                                </label>"""

                    html_out += f"""<label class="btn btn-secondary icon flag {'active' if rating == 'flag' else ''}" style="{'opacity: 1' if rating == 'flag' else 'opacity: 0.5'}">
                                                        <input type="radio" name="{tag}" id="{tag}_flag">
                                                    </label>
                                                </div>
                                            </div>
                                            """
                html_out += print_new_tags(
                    iteration_ratings.new_tags.iloc[0].split(", ")
                )
                html_out += "</div>"

        html_out += "</div>"  # Close container

        if html_out_path is not None:
            html_out += """
                        </div>
                        </body>
                        </html>
                        """
            AdjectiveExporter.save_html(html_out_path, html_out)
        return html_out

    @staticmethod
    def export_experiment_and_process(
        app_name,
        csv_out_path=None,
        html_out_path=None,
        scrub=False,
        export_only="experiment",
    ):
        data_dir = AdjectiveExporter.dallinger_export(app_name, scrub)
        ratings = AdjectiveExporter.export_pipelines_from_archive(
            data_dir, csv_out_path, export_only
        )
        AdjectiveExporter.generate_html(ratings, html_out_path)


def read_template_string(filename, flatten=False):
    path = pathlib.Path(__file__).parent.resolve() / "templates" / filename

    with open(path) as f:
        lines = f.readlines()
        if flatten:
            lines = "".join(lines)
        return lines


def render_adjective_pipelines_summary(cls):
    exp = cls.new(db.session)
    panes = exp.monitoring_panels()

    summaries = []

    for d in exp.timeline.modules()["modules"]:
        module_id = d["id"]
        module = exp.timeline.get_trial_maker(module_id)
        if isinstance(module, AdjectivePipeline):
            ratings = AdjectiveExporter.export_pipelines_from_database(module.networks)
            network_htmls = {}
            if ratings.shape[0] > 0:
                for network_id in set(ratings.network_id):
                    network_htmls[network_id] = AdjectiveExporter.generate_html(
                        ratings.query(f"network_id=={network_id}")
                    )
            iteration_dict = dict(Counter([n.degree - 1 for n in module.networks]))
            iteration_dict = dict(sorted(iteration_dict.items()))  # sort it
            breakdown = []
            for iteration, num_networks in iteration_dict.items():
                breakdown.append(f"{num_networks}x networks at iteration {iteration}")
            summaries.append(
                {
                    "module_id": module_id,
                    "n_complete": sum([n.full for n in module.networks]),
                    "n_total": len(module.networks),
                    "breakdown": breakdown,
                    "networks": network_htmls,
                }
            )
    html = read_template_string("dashboard_adjective.html")
    return render_template_string(
        "".join(html),
        title="Adjective modules",
        panes=panes,
        summaries=summaries,
        network_htmls=network_htmls,
        css=AdjectiveExporter.required_css(),
    )
