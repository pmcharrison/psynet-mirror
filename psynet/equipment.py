from psynet.modular_page import ModularPage, MonitorControl
from psynet.utils import get_translator


class MonitorInformation(ModularPage):
    def __init__(
        self,
        label="monitor_information",
    ):
        _ = get_translator()
        self.label = label
        self.prompt = _(
            "We are detecting your monitor information. Please give the permission to access your monitor information."
        )
        self.time_estimate = 1

        super().__init__(
            self.label,
            self.prompt,
            control=MonitorControl(),
            time_estimate=self.time_estimate,
            save_answer=label,
        )
