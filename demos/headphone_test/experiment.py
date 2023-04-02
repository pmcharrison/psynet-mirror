# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import psynet.experiment
from psynet.asset import DebugStorage
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage, VolumeCalibration
from psynet.prescreen import AntiphaseHeadphoneTest, HugginsHeadphoneTest
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Headphone test demo"
    asset_storage = DebugStorage()

    timeline = Timeline(
        NoConsent(),
        VolumeCalibration(),
        HugginsHeadphoneTest(),
        AntiphaseHeadphoneTest(),
        SuccessfulEndPage(),
    )

    test_num_bots = 2

    def test_run_bots(self, bots):
        bots[0].var.is_good_bot = True
        bots[1].var.is_good_bot = False
        super().test_run_bots(bots)

    def test_check_bot(self, bot: Bot, **kwargs):
        from psynet.prescreen import AntiphaseHeadphoneTrial, HugginsHeadphoneTrial

        is_good_bot = bot.var.is_good_bot
        if not is_good_bot:
            pass

        assert bot.failed == (not is_good_bot)

        for trial_class, trial_maker_id in zip(
            [HugginsHeadphoneTrial, AntiphaseHeadphoneTrial],
            ["huggins_headphone_test", "antiphase_headphone_test"],
        ):
            trials = trial_class.query.filter_by(participant_id=bot.id).all()

            if not is_good_bot and trial_maker_id == "antiphase_headphone_test":
                # The bad bot should never get to the antiphase_headphone_test, so there should be no trials
                assert len(trials) == 0
            else:
                assert len(trials) == 6
                n_correct = sum(trial.score for trial in trials)
                performance_check = bot.module_states[trial_maker_id][
                    0
                ].performance_check
                assert performance_check["score"] == n_correct
                assert performance_check["passed"] == (performance_check["score"] >= 4)
