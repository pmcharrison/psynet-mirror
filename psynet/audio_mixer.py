from typing import Optional

from .modular_page import AudioPrompt, AudioRecordControl, ModularPage
from .timeline import MediaSpec


class AudioMixerPage(ModularPage):
    def __init__(
        self,
        label: str,
        prompt: AudioPrompt,
        control: AudioRecordControl,
        time_estimate: float,
        media: Optional[MediaSpec] = None,
        **kwargs,
    ):
        super().__init__(
            label=label,
            prompt=prompt,
            control=control,
            time_estimate=time_estimate,
            media=media,
            **kwargs,
        )
