from psynet.modular_page import ModularPage, MonitorControl
from psynet.utils import get_translator


class MonitorInformation(ModularPage):
    """
    This ModularPage records information about the participant's computer screen configuration. The participant just
    needs to press 'Next', and respond positively to a permissions request, then the information will be recorded
    automatically.
    """

    def __init__(
        self,
        label="monitor_information",
    ):
        _ = get_translator()
        self.prompt = _(
            "On the next page you may see a permissions request; please grant it."
        )
        self.time_estimate = 5

        super().__init__(
            self.label,
            self.prompt,
            control=MonitorControl(),
            time_estimate=self.time_estimate,
            save_answer=label,
        )
