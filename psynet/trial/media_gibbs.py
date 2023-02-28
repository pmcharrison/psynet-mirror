# pylint: disable=unused-argument,abstract-method

import json
import os
import random
import tempfile
from uuid import uuid4

from flask import Markup, escape

from ..asset import ExperimentAsset
from ..field import claim_var
from ..media import make_batch_file
from ..modular_page import MediaSliderControl, ModularPage
from ..timeline import MediaSpec
from ..utils import get_logger, linspace
from .gibbs import GibbsNetwork, GibbsNode, GibbsTrial, GibbsTrialMaker

logger = get_logger()


class MediaGibbsNetwork(GibbsNetwork):
    """
    A Network class for Media Gibbs Sampler chains.
    The user should customise this by overriding the attributes
    :attr:`~psynet.trial.media_gibbs.MediaGibbsNetwork.synth_function_location`,
    :attr:`~psynet.trial.media_gibbs.MediaGibbsNetwork.vector_length`,
    :attr:`~psynet.trial.media_gibbs.MediaGibbsNetwork.vector_ranges`,
    and optionally
    :attr:`~psynet.trial.media_gibbs.MediaGibbsNetwork.granularity`,
    :attr:`~psynet.trial.media_gibbs.MediaGibbsNetwork.n_jobs`.
    The user is also invited to override the
    :meth:`psynet.trial.chain.ChainNetwork.make_definition` method
    in situations where different chains are to have different properties
    (e.g. different prompts).

    Attributes
    ----------

    synth_function_location: dict
        A dictionary specifying the function to use for synthesising
        stimuli. The dictionary should contain two arguments:
        one named ``"module_name"``, which identifies by name the module
        in which the function is contained,
        and one named ``"function_name"``, corresponding to the name
        of the function within that module.
        The synthesis function should take three arguments:

            - ``vector``, the parameter vector for the stimulus to be generated.

            - ``output_path``, the output path for the media file to be generated.

            - ``chain_definition``, the ``context`` dictionary for the current chain.

    s3_bucket : str
        Name of the S3 bucket in which the stimuli should be stored.
        The same bucket can be reused between experiments,
        the UUID system used to generate file names should keep them unique.

    vector_length : int
        Must be overridden with the length of the free parameter vector
        that is manipulated during the Gibbs sampling procedure.

    vector_ranges : list
        Must be overridden with a list with length equal to
        :attr:`~psynet.trial.media_gibbs.MediaGibbsNetwork.vector_length`.

    n_jobs : int
        Integer indicating how many parallel processes should be used by an individual worker node
        when generating the stimuli. Note that the final number of parallel processes may
        be considerably more than this; suppose 4 networks are generating stimuli at the same time,
        and we have 3 worker nodes, then the effective number of parallel processes will be 3 x 3 = 9.
        Default is 1, corresponding to no parallelization.

    granularity : Union[int, str]
        When a new :class:`~psynet.trial.media_gibbs.MediaGibbsNode`
        is created, a collection of stimuli are generated that
        span a given dimension of the parameter vector.
        If ``granularity`` is an integer, then this integer sets the number
        of stimuli that are generated, and the stimuli will be spaced evenly
        across the closed interval defined by the corresponding element of
        :attr:`~psynet.trial.media_gibbs.MediaGibbsNetwork.vector_ranges`.
        If ``granularity`` is equal to ``"custom"``, then the spacing of the
        stimuli is instead determined by the media generation function.
    """


class MediaGibbsTrial(GibbsTrial):
    """
    A Trial class for Media Gibbs Sampler chains.
    The user should customise this by overriding the
    :meth:`~psynet.trial.media_gibbs.MediaGibbsTrial.get_prompt`
    method.
    The user must also specify a time estimate
    by overriding the ``time_estimate`` class attribute.
    The user is also invited to override the
    :attr:`~psynet.trial.media_gibbs.MediaGibbsTrial.snap_slider`,
    :attr:`~psynet.trial.media_gibbs.MediaGibbsTrial.autoplay`,
    and
    :attr:`~psynet.trial.media_gibbs.MediaGibbsTrial.minimal_interactions`
    attributes.

    Attributes
    ----------

    snap_slider : bool
        If ``True``, the slider snaps to the location corresponding to the
        closest available media stimulus.
        If ``False`` (default), continuous values are permitted.

    snap_slider_before_release: bool
        If ``True``, the slider snaps to the closest stimulus before release
        rather than after release. This option is only available
        if the stimuli are equally spaced.

    autoplay : bool
        If ``True``, a media corresponding to the initial location on the
        slider will play as soon as the slider is ready for interactions.
        If ``False`` (default), the sound only plays once the participant
        first moves the slider.

    disable_while_playing : bool
        If `True`, the slider is disabled while the media is playing. Default: `False`.

    minimal_interactions : int : default: 3
        Minimal interactions with the slider before the user can go to next trial.

    minimal_time : float : default: 3.0
        Minimal amount of time that the user must spend on the page before
        they can proceed to the next trial.

    debug : bool
        If ``True``, then the page displays debugging information about the
        current trial. If ``False`` (default), no information is displayed.
        Override this to enable behaviour.

    input_type:
        Defaults to `"HTML5_range_slider"`, which gives a standard horizontal slider.
        The other option currently is `"circular_slider"`, which gives a circular slider.

    random_wrap:
        Defaults to `False`. If `True` then slider is wrapped twice so that there are no boundary jumps.
    """

    time_estimate = None
    snap_slider = False
    snap_slider_before_release = False
    autoplay = False
    disable_while_playing = False
    minimal_interactions = 3
    minimal_time = 3.0
    debug = False
    random_wrap = False
    input_type = "HTML5_range_slider"

    def show_trial(self, experiment, participant):
        self._validate()

        start_value = self.initial_vector[self.active_index]
        vector_range = self.vector_ranges[self.active_index]

        return ModularPage(
            "gibbs_media_trial",
            self._get_prompt(experiment, participant),
            control=MediaSliderControl(
                start_value=start_value,
                min_value=vector_range[0],
                max_value=vector_range[1],
                slider_media=self.media.data[self.network.modality],
                modality=self.network.modality,
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

    def _get_prompt(self, experiment, participant):
        main = self.get_prompt(experiment, participant)
        if not self.debug:
            return main
        else:
            return (
                (Markup(escape(main)) if isinstance(main, str) else main)
                + Markup("<pre style='overflow: scroll; max-height: 50vh;'>")
                + Markup(escape(json.dumps(self.summarize(), indent=4)))
                + Markup("</pre>")
            )

    def _validate(self):
        if self.snap_slider_before_release and not isinstance(
            self.network.granularity, int
        ):
            raise ValueError(
                "<snap_slider_before_release> can only equal <True> if <granularity> is an integer."
            )

    @property
    def media(self):
        slider_stimuli = self.slider_stimuli
        media_spec = MediaSpec()

        media_spec.add(
            self.network.modality,
            {
                "slider_stimuli": {
                    "url": slider_stimuli["url"],
                    "ids": [x["id"] for x in slider_stimuli["all"]],
                    "type": "batch",
                }
            },
        )
        return media_spec

    @property
    def media_locations(self):
        res = {}
        for stimulus in self.slider_stimuli["all"]:
            res[stimulus["id"]] = stimulus["value"]
        return res

    def get_prompt(self, experiment, participant):
        """
        Constructs and returns the prompt to display to the participant.
        This can either be a string of text to display, or raw HTML.
        In the latter case, the HTML should be wrapped in a call to
        ``flask.Markup``.
        """
        raise NotImplementedError

    @property
    def slider_stimuli(self):
        return self.node.slider_stimuli

    @property
    def vector_ranges(self):
        return self.node.vector_ranges


class MediaGibbsNode(GibbsNode):
    """
    A Node class for Media Gibbs sampler chains.
    The user should not have to modify this.
    """

    __extra_vars__ = GibbsNode.__extra_vars__.copy()

    vector_length = 0
    vector_ranges = []
    granularity = 100
    n_jobs = 1
    batch_synthesis = False

    slider_stimuli = claim_var("slider_stimuli", __extra_vars__)

    def validate(self):
        if not (isinstance(self.vector_length, int) and self.vector_length > 0):
            raise TypeError("<vector_length> must be a positive integer.")

        if not (
            isinstance(self.vector_ranges, list)
            and len(self.vector_ranges) == self.vector_length
        ):
            raise TypeError(
                "<vector_ranges> must be a list with length equal to <vector_length>."
            )

        for r in self.vector_ranges:
            if not (len(r) == 2 and r[0] < r[1]):
                raise ValueError(
                    "Each element of <vector_ranges> must be a list of two numbers in increasing order "
                    "identifying the legal range of the corresponding parameter in the vector."
                )

        if not ((isinstance(self.granularity, int) and self.granularity > 0)):
            raise ValueError("<granularity> must be a positive integer.")

    def random_sample(self, i):
        return random.uniform(self.vector_ranges[i][0], self.vector_ranges[i][1])

    def async_on_deploy(self):
        self.make_stimuli()

    def prepare_stimuli(self, range_to_sample, granularity, output_dir, modality):
        logger.info(modality)
        assert modality in ["audio", "video"]
        ext = ".wav" if modality == "audio" else ".mp4"
        values = linspace(range_to_sample[0], range_to_sample[1], granularity)
        ids = [f"slider_stimulus_{_i}" for _i, _ in enumerate(values)]
        files = [f"{_id}{ext}" for _id in ids]
        paths = [os.path.join(output_dir, _file) for _file in files]
        stimuli = [
            {"id": _id, "value": _value, "path": _path}
            for _id, _value, _path in zip(ids, values, paths)
        ]
        return values, ids, files, paths, stimuli

    def make_stimuli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            individual_stimuli_dir = os.path.join(temp_dir, "individual_stimuli")
            os.mkdir(individual_stimuli_dir)

            batch_file = f"{uuid4()}.batch"
            batch_path = os.path.join(temp_dir, batch_file)
            active_index = self.active_index
            granularity = self.granularity
            vector = self.vector
            range_to_sample = self.vector_ranges[active_index]
            values, ids, files, paths, stimuli = self.prepare_stimuli(
                range_to_sample,
                granularity,
                individual_stimuli_dir,
                self.network.modality,
            )

            if self.batch_synthesis:
                vectors = []

                for idx, value in enumerate(values):
                    _vector = vector.copy()
                    _vector[active_index] = value
                    vectors.append(_vector)

                self.synth_function(
                    vector=vectors,
                    output_path=batch_path,
                    chain_definition=self.context,
                )
            else:

                def _synth(value, path):
                    _vector = vector.copy()
                    _vector[active_index] = value
                    self.synth_function(
                        vector=_vector, output_path=path, chain_definition=self.context
                    )

                parallelize = self.n_jobs > 1
                if parallelize:
                    from joblib import Parallel, delayed

                    logger.info("Using %d processes in parallel" % self.n_jobs)

                    Parallel(n_jobs=self.n_jobs, backend="threading")(
                        delayed(_synth)(_value, _path)
                        for _value, _path in zip(values, paths)
                    )
                else:
                    for _value, _path in zip(values, paths):
                        _synth(_value, _path)

                stimuli = [
                    {"id": _id, "value": _value, "path": _path}
                    for _id, _value, _path in zip(ids, values, paths)
                ]
                self.make_media_batch_file(stimuli, batch_path)
            asset = ExperimentAsset(
                label="slider_stimulus",
                input_path=batch_path,
                parent=self,
            )
            asset.deposit()

            self.slider_stimuli = {"url": asset.url, "all": stimuli}

    @staticmethod
    def make_media_batch_file(stimuli, output_path):
        paths = [x["path"] for x in stimuli]
        make_batch_file(paths, output_path)

    def synth_function(self, vector, output_path, chain_definition=None):
        raise NotImplementedError


class MediaGibbsTrialMaker(GibbsTrialMaker):
    pass


class VideoGibbsNetwork(MediaGibbsNetwork):
    modality = "video"
    pass


class VideoGibbsTrial(MediaGibbsTrial):
    pass


class VideoGibbsNode(MediaGibbsNode):
    pass


class VideoGibbsTrialMaker(MediaGibbsTrialMaker):
    @property
    def default_network_class(self):
        return VideoGibbsNetwork
