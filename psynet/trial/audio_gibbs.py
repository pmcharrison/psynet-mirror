from psynet.modular_page import MediaSliderControl, ModularPage
from psynet.timeline import MediaSpec
from psynet.trial.media_gibbs import (
    MediaGibbsNetwork,
    MediaGibbsNode,
    MediaGibbsTrial,
    MediaGibbsTrialMaker,
)


class AudioGibbsNetwork(MediaGibbsNetwork):
    modality = "audio"
    pass


class AudioGibbsTrial(MediaGibbsTrial):
    def show_trial(self, experiment, participant):
        self._validate()

        start_value = self.initial_vector[self.active_index]
        vector_range = self.vector_ranges[self.active_index]
        return ModularPage(
            "gibbs_audio_trial",
            self._get_prompt(experiment, participant),
            control=MediaSliderControl(
                start_value=start_value,
                min_value=vector_range[0],
                max_value=vector_range[1],
                slider_media=self.media.audio,
                modality="audio",
                media_locations=self.media_locations,
                autoplay=self.autoplay,
                disable_while_playing=self.disable_while_playing,
                n_steps="n_media" if self.snap_slider_before_release else 10000,
                input_type=self.input_type,
                random_wrap=self.random_wrap,
                reverse_scale=self.reverse_scale,
                directional=False,
                snap_values="media_locations" if self.snap_slider else None,
                minimal_time=self.minimal_time,
                minimal_interactions=self.minimal_interactions,
            ),
            media=self.media,
            time_estimate=self.time_estimate,
        )

    @property
    def media(self):
        slider_stimuli = self.slider_stimuli
        return MediaSpec(
            audio={
                "slider_stimuli": {
                    "url": slider_stimuli["url"],
                    "ids": [x["id"] for x in slider_stimuli["all"]],
                    "type": "batch",
                }
            }
        )


class AudioGibbsNode(MediaGibbsNode):
    pass


class AudioGibbsTrialMaker(MediaGibbsTrialMaker):
    @property
    def default_network_class(self):
        return AudioGibbsNetwork
