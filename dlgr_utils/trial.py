from dallinger.models import Info

from .timeline import (
    Page,
    InfoPage,
    CodeBlock,
    Module,
    join
)

class Trial(Info):
    def show(self, experiment, participant):
        """Returns a Page object with a defined answer."""
        raise NotImplementedError

class TrialGenerator(Module):
    def prepare_trial(self, experiment, participant):
        """Returns a Trial object."""
        raise NotImplementedError

    def finalise_trial(self, answer, trial, experiment, participant):
        raise NotImplementedError

    def _prepare_trial(self, experiment, participant):
        trial = self.prepare_trial(experiment=experiment, participant=participant)
        experiment.session.add(trial)
        participant.var.current_trial = trial.id
        experiment.save()

    def _show_trial(self, experiment, participant):
        trial = self.get_current_trial(self, participant)
        return trial.show(experiment=experiment, participant=participant)

    def _finalise_trial(self, experiment, participant):
        trial = self.get_current_trial(participant)
        answer = participant.answer
        self.finalise_trial(
            answer=answer,
            trial=trial,
            experiment=experiment,
            participant=participant
        )

    def get_current_trial(self, participant):
        trial_id = participant.var.current_trial
        return self.trial_class.query.get(trial_id)

    elts = join(
        CodeBlock(self._prepare_trial),
        ReactivePage(self._show_trial),
        CodeBlock(self.finalise_trial)
    )

    def __init__(self, label, trial_class):
        self.label = label
        self.trial_class = trial_class
