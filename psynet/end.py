from typing import List, Optional, Union

import dominate
from dominate import tags

from psynet.modular_page import NullControl
from psynet.timeline import (
    CodeBlock,
    Elt,
    EltCollection,
    PageMaker,
    TimelineLogic,
    join,
)
from psynet.utils import get_translator


class EndLogic(EltCollection):
    def resolve(self) -> Union[Elt, List[Elt]]:
        return join(
            CodeBlock(self.before_debrief),
            PageMaker(self.debrief_participant, time_estimate=0.0),
            CodeBlock(self.after_debrief),
            PageMaker(self.release_participant, time_estimate=0.0),
        )

    def before_debrief(self, experiment, participant) -> None:
        pass

    def debrief_participant(self, experiment, participant) -> TimelineLogic:
        raise NotImplementedError

    def after_debrief(self, experiment, participant) -> None:
        from psynet.bot import Bot

        if isinstance(participant, Bot):
            participant.status = "approved"

    def release_participant(self, experiment, participant) -> TimelineLogic:
        try:
            return experiment.recruiter.release_participant(experiment, participant)
        except AttributeError:
            raise ValueError(
                f"The selected recruiter ({experiment.recruiter}) is not fully implemented in PsyNet. "
                "No release_participant method was found."
            )

    def debrief_page(
        self, content, experiment, participant, show_finish_button=True
    ) -> TimelineLogic:
        from .modular_page import ModularPage, PushButtonControl

        # Todo - Once automatic translation is updated, revisit the logic in RejectedConsentPage,
        # and ask the participant to return the HIT if appropriate.
        if show_finish_button:
            control = PushButtonControl(["Finish"])
        else:
            control = NullControl()

        return ModularPage(
            self.__class__.__name__,
            content,
            control,
            show_next_button=False,
        )

    @property
    def should_show_reward(self) -> bool:
        from psynet.experiment import get_experiment
        from psynet.utils import get_config

        exp = get_experiment()
        config = get_config()

        return config.get("show_reward") and not exp.with_lucid_recruitment()

    def summarize_reward(self, experiment, participant):
        from psynet.utils import get_config

        config = get_config()
        _p = get_translator(context=True)

        # Todo - translation should not have HTML hard-coded.
        # Fix that and then refactor using dominate package.
        #
        # Todo - if there is no performance reward, skip reporting it.
        text = _p(
            "final-page-rewards",
            "You will receive a reward of <strong>{CURRENCY}{TIME_REWARD}</strong> for the time you spent "
            "on the experiment. You have also been awarded a performance reward of <strong>{CURRENCY}"
            "{PERFORMANCE_REWARD}</strong>! ",
        )
        text = text.format(
            CURRENCY=config.get("currency"),
            TIME_REWARD=f"{participant.time_reward:.2f}",
            PERFORMANCE_REWARD=f"{participant.performance_reward:.2f}",
        )

        return dominate.util.raw(text)


class SuccessfulEndLogic(EndLogic):
    def after_debrief(self, experiment, participant):
        super().after_debrief(experiment, participant)
        participant.complete = True
        participant.progress = 1.0

    def debrief_participant(self, experiment, participant) -> TimelineLogic:
        _ = get_translator()
        _p = get_translator(context=True)

        html = tags.span()

        with html:
            tags.span(_p("final_page_successful", "That's the end of the experiment!"))

            if self.should_show_reward:
                tags.span(self.summarize_reward(experiment, participant))

            tags.span(_("Thank you for taking part."))

            # Todo - consider improving our CSS to add automatic spacing after paragraphs
            tags.p(cls="vspace")

            if not experiment.with_lucid_recruitment():
                tags.p(_('Please click "Finish" to finalize the session.'))

        return self.debrief_page(html, experiment, participant)


class UnsuccessfulEndLogic(EndLogic):
    def __init__(self, failure_tags: Optional[List] = None, **kwargs):
        super().__init__()

        if failure_tags is None:
            failure_tags = []
        failure_tags = [*failure_tags, "UnsuccessfulEndPage"]
        self.failure_tags = failure_tags

        if "template_filename" in kwargs:
            raise ValueError(
                "UnsuccessfulEndPage no longer accepts a template_filename argument. "
                "Instead you should customize its content by subclassing its message attribute."
            )

    def before_debrief(self, experiment, participant) -> None:
        super().before_debrief(experiment, participant)
        participant.append_failure_tags(*self.failure_tags)
        participant.fail()

    def debrief_participant(self, experiment, participant) -> TimelineLogic:
        _ = get_translator()
        _p = get_translator(context=True)

        html = tags.span()

        with html:
            tags.span(
                _p(
                    "final_page_unsuccessful",
                    "Unfortunately the experiment must end early.",
                )
            )

            if self.should_show_reward:
                tags.span(
                    _p(
                        "final_page_unsuccessful",
                        "However, you will still be paid for the time you spent already.",
                    )
                )
                tags.span(self.summarize_reward(experiment, participant))

            # Todo - remove this if we end up removing the redirect logic
            if experiment.with_lucid_recruitment():
                tags.span(_("You will be redirected."))

            tags.span(_("Thank you for taking part."))

            # Todo - consider improving our CSS to add automatic spacing after paragraphs
            tags.p(cls="vspace")

            if not experiment.with_lucid_recruitment():
                tags.p(_('Please click "Finish" to finalize the session.'))

        return self.debrief_page(html, experiment, participant)


class RejectedConsentLogic(UnsuccessfulEndLogic):
    def after_debrief(self, experiment, participant):
        super().after_debrief(experiment, participant)
        participant.fail()

    def debrief_participant(self, experiment, participant) -> TimelineLogic:
        _ = get_translator()
        _p = get_translator(context=True)

        html = tags.span()

        with html:
            tags.span(_p("final_page_rejected_consent", "Consent was rejected."))
            tags.span(_p("final_page_rejected_consent", "End of experiment."))

        return self.debrief_page(
            html, experiment, participant, show_finish_button=False
        )
