.. _pre_deploy_routines:

===================
Pre-deploy routines
===================

The idea behind :class:`~psynet.timeline.PreDeployRoutine` is to allow for the definition of tasks to be performed before deployment and the start of the experiment. PreDeployRoutines are thought to be added (in any number) to the beginning of the timeline of an experiment. To demonstrate its usage, we included below an example of the definition of a :class:`~psynet.timeline.PreDeployRoutine` as used in the demo at ``demos/non_adaptive_audio`` which facilitates the one-time setup of an Amazon S3 bucket.

::

  from psynet.media import prepare_s3_bucket_for_presigned_urls
  from psynet.timeline import PreDeployRoutine

  PreDeployRoutine(
      "prepare_s3_bucket_for_presigned_urls",
      prepare_s3_bucket_for_presigned_urls,
      {"bucket_name": "recordings_s3_bucket", "public_read": True, "create_new_bucket": True}
  )

A :class:`~psynet.timeline.PreDeployRoutine` expects three arguments: A ``label`` describing the pre-deployment task, the ``function`` to be executed and on its third position the ``arguments`` of the function to be executed. This function will then be run automatically as part of experiment launch.
