# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################
from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ImagePrompt, ModularPage, PushButtonControl, TextControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.create_and_rate import (
    CreateAndRateNode,
    CreateAndRateTrialmakerMixin,
    CreateTrialMixin,
    RateTrialMixin,
    SelectTrialMixin,
)
from psynet.trial.imitation_chain import ImitationChainTrial, ImitationChainTrialMaker
from psynet.utils import get_logger

logger = get_logger()


def animal_prompt(text, img_url):
    return ImagePrompt(
        url=img_url,
        text=Markup(
            text
            + """
            <style>
            img {
            max-width: 500px; max-height: 500px; margin: 0 auto;
            }
            """
        ),
        width="100%",
        height="auto",
    )


class CreateTrial(ImitationChainTrial, CreateTrialMixin):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return ModularPage(
            "create_trial",
            animal_prompt(text="Describe the animal", img_url=self.context["img_url"]),
            TextControl(),
            time_estimate=self.time_estimate,
        )


class SingleRateTrial(ImitationChainTrial, RateTrialMixin):
    time_estimate = 5

    def __init__(self, experiment, node, participant, *args, **kwargs):
        super().__init__(experiment, node, participant, *args, **kwargs)
        super(RateTrialMixin, self).__init__()

    def show_trial(self, experiment, participant):
        assert self.trial_maker.target_selection_method == "load_balanced"
        import pydevd_pycharm

        pydevd_pycharm.settrace(
            "localhost", port=2343, stdoutToServer=True, stderrToServer=True
        )
        assert len(self.targets) == 1
        target = self.targets[0]
        creation = self.get_target_answer(target)
        return ModularPage(
            "rate_trial",
            animal_prompt(
                text=f"How well does this description match the animal? ({creation})",
                img_url=self.context["img_url"],
            ),
            PushButtonControl(
                choices=[1, 2, 3, 4, 5],
                labels=["not at all", "a little", "somewhat", "very", "perfectly"],
                arrange_vertically=False,
            ),
        )


class SelectTrial(ImitationChainTrial, SelectTrialMixin):
    time_estimate = 5

    def __init__(self, experiment, node, participant, *args, **kwargs):
        super().__init__(experiment, node, participant, *args, **kwargs)
        super(SelectTrial, self).__init__()

    def show_trial(self, experiment, participant):
        eids = [self.get_eid(target) for target in self.targets]
        answers = [self.get_target_answer(target) for target in self.targets]
        return ModularPage(
            "select_trial",
            animal_prompt(
                text="Which of these descriptions is the best?",
                img_url=self.context["img_url"],
            ),
            PushButtonControl(
                choices=eids,
                labels=answers,
            ),
        )


start_nodes = [CreateAndRateNode(context={"img_url": "static/dog.jpg"})]


class CreateAndRateTrialmaker(ImitationChainTrialMaker, CreateAndRateTrialmakerMixin):
    def __init__(
        self,
        num_creators,
        num_raters,
        node_class,
        creator_class,
        rater_class,
        mixin_kwargs,
        trial_maker_kwargs,
    ):
        CreateAndRateTrialmakerMixin.__init__(
            self,
            num_creators,
            num_raters,
            node_class,
            creator_class,
            rater_class,
            **mixin_kwargs,
        )
        trial_maker_kwargs = self.update_trial_maker_kwargs(trial_maker_kwargs)
        super().__init__(**trial_maker_kwargs)

    def finalize_trial(self, answer, trial, experiment, participant):
        answer = self.finalize_create_and_rate_trial(self, trial)
        return super().finalize_trial(answer, trial, experiment, participant)

    def get_trial_class(self, node, participant, experiment):
        return self.get_role(node, participant, experiment)


##########################################################################################
# Experiment
##########################################################################################


class Exp(psynet.experiment.Experiment):
    label = "basic"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        CreateAndRateTrialmaker(
            num_creators=2,
            num_raters=2,
            node_class=CreateAndRateNode,
            creator_class=CreateTrial,
            rater_class=SingleRateTrial,
            mixin_kwargs={},
            trial_maker_kwargs={
                "id_": "picnic",
                "chain_type": "across",
                "expected_trials_per_participant": len(start_nodes),
                "max_trials_per_participant": len(start_nodes),
                "start_nodes": start_nodes,
                "chains_per_experiment": len(start_nodes),
                "balance_across_chains": False,
                "check_performance_at_end": True,
                "check_performance_every_trial": False,
                "propagate_failure": False,
                "recruit_mode": "n_trials",
                "target_n_participants": None,
                "wait_for_networks": False,
                "max_nodes_per_chain": 2,
            },
        ),
        SuccessfulEndPage(),
    )
