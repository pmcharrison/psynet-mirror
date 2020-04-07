import psynet.experiment

from .participant import Participant, get_participant
from .timeline import (
    Timeline, 
    Module, 
    join, 
    Page, 
    PageMaker, 
    InfoPage, 
    NAFCPage, 
    CodeBlock, 
    SuccessfulEndPage, 
    FailedValidation
)

class Imitate(Module):
    items = []
    num_items = {
        "training": -1,
        "screening": -1,
        "main": - 1
    }

    def __init__(self, items: list):
        self.check()
        super().__init__(events=self._get_logic())

    def show_item(self, item):
        raise NotImplementedError

    def get_next_item(phase, experiment, participant):
        raise NotImplementedError

    def _check():
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError("<items> must be a non-empty list.")

        for key in ["training", "screening", "main"]:
            if self.num_items[key] < 0:
                raise ValueError(f"num_items.{key} cannot be negative. Did you forget to overwrite Imitate.num_items?")

    def _get_logic(self):
        return join(
            self._get_train_logic(),
            self._get_check_logic(),
            self._get_main_logic()
        )

    def _get_train_logic():
        return join(
            CodeBlock(lambda experiment, participant: participant.var.set("_train_item", 1)),
            while_loop(
                "imitate_training",
                condition=lambda experiment, participant: participant.var.get("_train_item") < self.num_items["training"],
                logic=PageMaker(
                    lambda experiment, participant: self.show_item(self.get_next_item("training", experiment, participant))
                ),
                expected_repetitions=self.num_items["training"]
            )
        )

    t

class Item():
    pass

# def imitation_experiment(
#     stimuli,

# )

# class Experiment(psynet.experiment.Experiment):
#     timeline = Timeline(

#     )