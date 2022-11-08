======================
Upgrading to PsyNet 10
======================

Introduction
------------

PsyNet 10 brings a host of new features. We are excited about what these new features bring,
but they do necessitate a few changes to experiments implemented with earlier PsyNet versions.
This guide is intended to help you with that upgrade process.

Summary of breaking changes
---------------------------

Static versus Chain experiments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PsyNet 10 consolidates the underlying implementation for Static experiments and Chain experiments
into a common code-base. As a result, Chain experiments can now access various features that
were originally only available in Static experiments, such as blocked designs and stimulus pre-generation.

Stimuli
^^^^^^^

The former implementation of Static experiments was rather complicated. One had to implement so-called
StimulusSpecs and StimulusVersionSpecs, which PsyNet compiled under the hood into Stimulus
and Stimulus Version objects which were stored in the database.
PsyNet 10 massively streamlines this procedure.
There is now no longer such thing as a Stimulus or a Stimulus Version; one just uses Nodes instead.
Moreover, the way for predefining experiment structure is now homogenized between Static and Chain experiments.
Rather than defining Stimulus Sets (for Static experiments)
or defining ``balance_across_networks`` constructs (for Chain experiments),
one now just provides a simple list of Nodes to the trial maker,
with these Nodes defining e.g. the initial set of stimuli or the starting states of the chain networks.

Sources
^^^^^^^

Former PsyNet versions had the concept of Sources.
Sources were used as the starting point for chains in paradigms such as Serial Reproduction
and Gibbs Sampling with People.
We have now streamlined the syntax for such experiments and eliminated the need for Sources,
subsuming their function under the Node class.

S3 and asset management
^^^^^^^^^^^^^^^^^^^^^^^

Previous PsyNet versions required experimenters to rely on Amazon S3 storage for managing media files.
They were expected to use various functions to interact with S3 manually,
doing things like managing S3 access permissions, creating buckets, uploading to S3, and so on.
This made it difficult to generalize a particular experiment implementation to other storage
back-ends, or to run such experiments without Internet access (e.g. in the context of field research).

PsyNet 10 incorporates a much more sophisticated approach to media management. There is a new
database-backed object hierarchy based on the :class:`~psynet.asset.Asset` class, where each
media file is represented as an Asset object that is linked to the database.
Different storage backends are then represented by different subclasses of the
:class:`~psynet.asset.AssetStorage` class.
Now when the experimenter manipulates media files, they do not have to worry about things like S3 permissions,
file naming, anonymization, linking response data to uploaded media files, and so on.
They can simply write things like ``asset.deposit()`` and everything will be managed for them.
Switching between different storage back-ends (e.g. from S3 to local storage) can be achieved
just by changing a single line of code in the Experiment class.

Upgrading your experiments
--------------------------

