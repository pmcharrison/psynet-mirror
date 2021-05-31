from typing import Optional

from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage
from psynet.timeline import Module, join


class PEI(Module):
    """
    Confidence scale (PEI) questionnaire.

    Parameters
    ----------

    label : str, default: "pei"
        A label used to distinguish the module from other modules in the timeline.

    info_page : InfoPage, optional, default: `None`
        An :class:`~psynet.page.InfoPage` object to be used as an introductionary first page.
        If none is supplied the default one is displayed (see source code).
    """

    def __init__(
        self,
        label: str = "pei",
        info_page: Optional[InfoPage] = None,
    ):
        if info_page is None:
            info_page = InfoPage(
                "The following questions are designed to assess your confidence. Please answer as accurately as possible. Think about how the question applies to you during the last 2 months.",
                time_estimate=5,
            )
        self.label = label
        self.elts = join(
            info_page,
            PEI_01(),
            PEI_02(),
            PEI_03(),
            PEI_04(),
            PEI_05(),
            PEI_06(),
            PEI_07(),
        )
        super().__init__(self.label, self.elts)


class PEI_01(ModularPage):
    def __init__(
        self,
        label="pei_01",
        prompt="I often feel unsure of myself even in situations I have successfully dealt with in the past.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            agreement_scale()["choices"],
            agreement_scale()["labels"],
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class PEI_02(ModularPage):
    def __init__(
        self,
        label="pei_02",
        prompt="I lack some important capabilities that may keep me from being successful.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            agreement_scale()["choices"],
            agreement_scale()["labels"],
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class PEI_03(ModularPage):
    def __init__(
        self,
        label="pei_03",
        prompt="Much of the time I don’t feel as competent as many of the people around me.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            agreement_scale()["choices"],
            agreement_scale()["labels"],
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class PEI_04(ModularPage):
    def __init__(
        self,
        label="pei_04",
        prompt="I have fewer doubts about my abilities than most people.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            agreement_scale()["choices"],
            agreement_scale()["labels"],
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class PEI_05(ModularPage):
    def __init__(
        self,
        label="pei_05",
        prompt="When things are going poorly, I am usually confident that I can successfully deal with them.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            agreement_scale()["choices"],
            agreement_scale()["labels"],
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class PEI_06(ModularPage):
    def __init__(
        self,
        label="pei_06",
        prompt="I have more confidence in myself than most people I know.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            agreement_scale()["choices"],
            agreement_scale()["labels"],
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


class PEI_07(ModularPage):
    def __init__(
        self,
        label="pei_07",
        prompt="If I were more confident about myself, my life would be better.",
    ):
        self.label = label
        self.prompt = prompt
        self.time_estimate = 5

        control = PushButtonControl(
            agreement_scale()["choices"],
            agreement_scale()["labels"],
        )
        super().__init__(
            self.label, self.prompt, control=control, time_estimate=self.time_estimate
        )


def agreement_scale():
    return {
        "choices": list(range(1, 5)),
        "labels": [
            "Strongly Agree",
            "Mainly Agree",
            "Mainly Disagree",
            "Strongly Disagree",
        ],
    }
