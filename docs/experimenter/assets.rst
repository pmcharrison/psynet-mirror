========
Assets
========

Overview
--------

In PsyNet terminology, an :class:`~psynet.asset.Asset` is some kind of file (or collection of files) that
is referenced during an experiment. These might for example be video files that we play
to the participant, or perhaps audio recordings that we collect from the participant.

Working within PsyNet's :class:`~psynet.asset.Asset` framework brings various advantages. It abstracts away
the notion of file storage, meaning that you can switch between storage backends
(e.g. Amazon S3 versus your private web server) with just a single line of code.
It deals with the tedious book-keeping of keeping track of the different assets
associated with a given experiment, and it implements clever caching routines that
save time when redeploying different versions of the same experiment, as well as
asynchronous functionality that minimizes the performance impact of incorporating
large assets in your experiment. Moreover, it provides a handy export functionality
that allows you to compile all your generated assets in an organized fasion
suitable for your research paper's Supplementary Materials.

Types of assets
---------------

PsyNet defines several types of Assets, each with their own specific applications.
Click on the links to see more details about these asset types.

An :class:`~psynet.asset.ExternalAsset`...

An :class:`~psynet.asset.ExperimentAsset`...

A :class:`~psynet.asset.CachedAsset`...

A :class:`~psynet.asset.CachedFunctionAsset`...

A :class:`~psynet.asset.FastFunctionAsset`...


Creating an asset
-----------------

There are two main modes of creating an asset:
before launching an experiment, and during an experiment.
The former is appropriate if you know what your stimuli will be in advance;
the latter is appropriate if you are generating the stimuli dynamically
during the experiment.

Creating an asset before launching the experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you create an asset in advance, you can either make it a property of a
:class:`~psynet.timeline.Module` or a property of a :class:`psynet.trial.main.TrialNode`.
A Module is a portion of the experiment timeline,
whereas a Trial Node is an object that generates Trials.
See the class documentation for more details on Trials and Modules.

Creating an asset within a module
"""""""""""""""""""""""""""""""""

You can create an asset within a module by passing it to the module constructor's
``assets`` argument. This argument expects a list, and you can populate
this list with multiple assets. For example:

::

    import psynet.experiment
    from psynet.asset import CachedAsset

    class Exp(psynet.experiment.Experiment):
        timeline = join(
            Module(
                "my_module",
                my_pages(),
                assets={
                    "logo": CachedAsset("logo.svg"),
                }
            )
        )

You can then access this asset within your module as follows:

::

    from psynet.timeline import PageMaker

    def my_pages():
        return PageMaker(
            lambda assets: ModularPage(
                "audio_player",
                ImagePrompt(assets["logo"], "Look at this image."),
                time_estimate=5,
            )
        )

Note how the asset must be accessed within a ``PageMaker``,
and is pulled from the optional ``assets`` argument that we included
in the lambda function. This ``assets`` argument is populated with a dictionary
of assets from the current module.

Creating an asset within a Node
"""""""""""""""""""""""""""""""

You can alternatively create an asset within a Trial Node. This is most relevant
if you are planning to use your asset within a PsyNet Trial. There are several
ways that you can create Trial Nodes as part of your experiment initialization,
but the most common is to build a Trial Maker and pass a list of Trial Nodes
to the ``nodes`` or ``start_nodes`` argument, for example:

::

    nodes = [
        StaticNode(
            definition={
                "frequency_gradient": frequency_gradient,
                "start_frequency": start_frequency,
                "frequencies": [start_frequency + i * frequency_gradient for i in range(5)],
            },
            assets={
                "stimulus": CachedFunctionAsset(
                    function=synth_stimulus,
                    extension=".wav",
                )
            },
        )
        for frequency_gradient in [-100, 0, 100]
        for start_frequency in [-100, 0, 100]
    ]

    StaticTrialMaker(
        id_="static_audio",
        trial_class=CustomTrial,
        nodes=nodes,
        expected_trials_per_participant=len(nodes),
        target_n_participants=3,
        recruit_mode="n_participants",
    )

See how, similar to the Module use case, we pass the Node constructor a dictionary
for its `assets` argument, which we can then access during the trial as follows:

::

    class CustomTrial(StaticTrial):
    _time_trial = 3
    _time_feedback = 2

    time_estimate = _time_trial + _time_feedback
    wait_for_feedback = True

    def show_trial(self, experiment, participant):
        return ModularPage(
            "imitation",
            AudioPrompt(
                self.assets["stimulus"],
                "Please imitate the spoken word as closely as possible.",
            ),
            AudioRecordControl(duration=3.0, bot_response_media="example-bier.wav"),
            time_estimate=self._time_trial,
        )

See in particular how we access the asset by calling ``self.assets["stimulus"]``
within the Trial method.

Creating an asset during the experiment
"""""""""""""""""""""""""""""""""""""""

There are several situations in which we might want to create an asset
during the experiment:

- Creating an asset from the participant's response;
- Creating an asset when we create a Trial Node;
- Creating an asset when we create a Trial.

Let's discuss each in turn.


Creating an asset from the participant's response
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are several built-in PsyNet components that will automatically create
an asset from the participant's response. For example,
if we use an :class:`~psynet.modular_page.AudioRecordControl` in our experiment,
PsyNet will automatically create an asset corresponding to our audio recording
which we can then access afterwards. See the following example code from
the static audio demo:

::

    class CustomTrial(StaticTrial):
        def show_trial(self, experiment, participant):
            return ModularPage(
                "imitation",
                AudioPrompt(
                    self.assets["stimulus"],
                    "Please imitate the spoken word as closely as possible.",
                ),
                AudioRecordControl(duration=3.0, bot_response_media="example-bier.wav"),
                time_estimate=self._time_trial,
            )

        def show_feedback(self, experiment, participant):
            return ModularPage(
                "feedback_page",
                AudioPrompt(
                    self.assets["imitation"],
                    "Listen back to your recording. Did you do a good job?",
                ),
                time_estimate=self._time_feedback,
            )

See how the ``AudioRecordTrial`` has created an asset with the label ``"imitation"``,
and a link to this asset is saved in the Trial object, accessed using the code
``self.assets["imitation"]``.

Let's look at the code that PsyNet uses to create this asset; we can find this
at `psynet/modular_page.py`. Let's look in particular at the
:meth:`psynet.modular_page.AudioRecordControl.format_answer` method of the
:class:`psynet.modular_page.AudioRecordControl` class.

::

    def format_answer(self, raw_answer, **kwargs):
        blobs = kwargs["blobs"]
        audio = blobs["audioRecording"]
        trial = kwargs["trial"]
        participant = kwargs["participant"]

        if trial:
            parent = trial
        else:
            parent = participant

        # Need to leave file deletion to the depositing process
        # if we're going to run it asynchronously
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            audio.save(tmp_file.name)

            from .trial.record import Recording

            label = self.page.label

            asset = Recording(
                label=label,
                input_path=tmp_file.name,
                extension=self.file_extension,
                parent=parent,
                variables=dict(),
                personal=self.personal,
            )

            try:
                asset.deposit(async_=True, delete_input=True)
            except Asset.InconsistentContentError:
                raise ValueError(
                    f"This participant already has an asset with the label '{label}'. "
                    "You should update your AudioRecordControl labels to make them distinct."
                )

        return {
            "origin": "AudioRecordControl",
            "supports_record_trial": True,
            "key": asset.key,
            "url": asset.url,
            "duration_sec": self.duration,  # TODO - base this on the actual audio file?
        }


There's a special class being used here called
:class:`~psynet.trial.record.Recording`. This is just a wrapper for
:class:`~psynet.asset.ExperimentAsset`:

::

    class Recording(ExperimentAsset):
        pass


So, how does the code create the asset?
First, it extracts the page's label.
It then creates a Recording object,
passing ``self`` (the Trial) as the parent.
It then calls ``asset.deposit``, setting ``async_=True`` so that
the user interface won't freeze while we wait for the asset to deposit.

::


            from .trial.record import Recording

            label = self.page.label

            asset = Recording(
                label=label,
                input_path=tmp_file.name,
                extension=self.file_extension,
                parent=parent,
                variables=dict(),
                personal=self.personal,
            )

            try:
                asset.deposit(async_=True, delete_input=True)


Creating an asset when we create a Trial Node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is often useful to create a new asset whenever we create a new Trial Node.
This happens for example in imitation chain experiments using audio files.
Let's look at the source code for
:class:`~psynet.trial.record.MediaImitationChainNode`, which implements this functionality.

::

    class MediaImitationChainNode(ImitationChainNode):
        """
        A Node class for media imitation chains.
        Users must override the
        :meth:`~psynet.trial.audio.MediaImitationChainNode.synthesize_target` method.
        """

        __extra_vars__ = ImitationChainNode.__extra_vars__.copy()

        media_extension = None

        def synthesize_target(self, output_file):
            """
            Generates the target stimulus (i.e. the stimulus to be imitated by the participant).
            """
            raise NotImplementedError

        def async_on_deploy(self):
            logger.info("Synthesizing media for node %i...", self.id)

            with tempfile.NamedTemporaryFile() as temp_file:
                from ..asset import ExperimentAsset

                self.synthesize_target(temp_file.name)
                asset = ExperimentAsset(
                    label="stimulus",
                    input_path=temp_file.name,
                    extension=self.media_extension,
                    parent=self,
                )
                asset.deposit()


We perform the asset generation by overriding the ``async_on_deploy`` method.
This method is called whenever a new Node is 'deployed', i.e., instantiated
on the web server. The 'async' prefix indicates that this method is run
asynchronously, so we don't need to worry about blocking server execution,
and so we don't worry about setting ``async_=True`` in ``deposit()``.


Creating an asset when we create a Trial
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, PsyNet Trials inherit their definitions from the Trial Nodes that
created them. However, sometimes we add some additional manipulations to this definition,
for example adding a randomization component. We typically do this by overriding the
:meth:`~psynet.trial.main.Trial.finalize_definition` method.
At this point, we may then want to generate a new asset that reflects this updated
definition. This can be done as follows (source code from the third 'static audio'
demo):

::

    class CustomTrial(StaticTrial):
        _time_trial = 3
        _time_feedback = 2

        time_estimate = _time_trial + _time_feedback
        wait_for_feedback = True

        def finalize_definition(self, definition, experiment, participant):
            definition["start_frequency"] = random.uniform(-100, 100)
            definition["frequencies"] = [
                definition["start_frequency"] + i * definition["frequency_gradient"]
                for i in range(5)
            ]
            self.add_assets(
                {
                    "stimulus": FastFunctionAsset(
                        function=synth_stimulus,
                        extension=".wav",
                    )
                }
            )
            return definition


Look in particular at the ``add_assets`` method. This takes a dictionary of assets
that can be created on the basis of the dynamically generated definition,
and will then be added to the trials ``assets`` slot.


Storage back-ends
-----------------

PsyNet supports several different storage back-ends, and provides hooks for you
to define your own back-ends should you need them. The built-in back-ends include
the following:

:class:`~psynet.asset.S3Storage` stores the assets using Amazon Web Services'
S3 Storage system. This service is relatively inexpensive as long as your
file collection does not number more than a few gigabytes. To use this
service you will need to sign up for an Amazon Web Services account.

:class:`~psynet.asset.LocalStorage` stores the assets on the same web server
that is running your Python code. This approach is suitable when you are
running experiments on a single local machine (e.g. when doing fieldwork
or laboratory-based data collection), and when you are deploying your experiments
to your own remote web server via Docker. It is *not* appropriate if you
deploy your experiments via Heroku, because Heroku deployments split the processing
over multiple web servers, and these different web servers do not share the
same file system.

TODO - rename DebugStorage to LocalStorage, and add a check that prevents
you from deploying on Heroku if you've selected LocalStorage.

You select your storage backend by setting the ``asset_storage`` property
of your ``Experiment`` class in experiment.py, for example:

::

    import psynet.experiment
    from psynet.asset import S3Storage

    class Exp(psynet.experiment.Experiment):
        asset_storage = S3Storage("psynet-tests", "repp-tests")

For more details about individual storage back-ends follow the class documentation
links above.


Inheriting assets
-----------------

Sometimes we run an experiment that produces some assets (e.g. audio recordings from
our participants), and we then want to follow up that experiment with another
experiment that uses those assets (e.g. to produce some kind of validation ratings).
PsyNet provides a helper class for these situations called
:class:`~psynet.asset.InheritedAssets`.
This class allows you to inherit assets from a previously exported experiment
and use them in your new experiment. See the class documentation for details.


Exporting assets
----------------

It is not strictly necessary to export your assets once you've run an experiment.
By default, PsyNet organizes your storage back-end in a sensible hierarchy
so that you can easily look up assets generated from a given historic experiment
deployment. However, there are some limitations of working with this format:

- The file names often contain obfuscation components for security purposes,
  for example ``config_variables__abfe4815-f038-4a47-b59d-8c462d3d5b28.txt``,
  which are ugly to retain in the long term.
- Cached files won't be included in the experiment directory, so if you want
  to construct a full set of your experiment's assets for your research paper's
  Supplementary Materials, you'll have to do some extra work digging those out
  from elsewhere in your storage back-end.

PsyNet therefore provides an additional workflow for exporting assets.
This workflow is accessed via the standard ``psynet export`` command
that is responsible for exporting the database contents once an experiment is finished.
In particular, there is an option ``--assets`` which can be used to specify
what assets should be exported. The default, ``--assets experiment``, exports
all Experiment Assets. Alternatively, setting ``--assets all`` means that
all assets will be exported; setting ``--assets none`` means that no assets
will be exported. See the documentation for :func:`~psynet.command_line.export`
for more details.
