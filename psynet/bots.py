from sqlalchemy import Column, Float

from .experiment import Experiment
from .participant import Participant
from utils import import_local_experiment

class Bot(Participant):
    @cached_property
    def experiment(self) -> Experiment:
        return import_local_experiment["class"]()

    @cached_property
    def timeline(self):
        return self.experiment.timeline

    def take_experiment(self, time_factor=0):
        """
        Parameters
        ----------

        time_factor :
            Determines how long the bot spends on each page.
            If 0, the bot spends no time on each page.
            If 1, the bot spends ``time_estimate`` time on each page.
            This
        """
        while self.status == "working":
            self.take_page(time_factor)


    def take_page(self, time_factor):
        bot = self
        experiment = self.experiment
        page = self.get_current_page()

        response = page.call__present_to_bot(experiment, bot)
        experiment.process_response(
            participant_id=self.id,
            raw_answer = response.get("raw_answer", default=page.NoArgumentProvided),
            blobs=response.get("blobs"),
            metadata=response.get("metadata"),
            page_uuid=self.page_uuid,
            client_ip_address=response.get("client_ip_address"),
            formatted_answer=response.get("answer", default=page.NoArgumentProvided),
        )

        if time_factor > 0:
            time.sleep(page.time_estimate * time_factor)
