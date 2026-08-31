Pregenerated public audiovisual stimuli should be placed in ``static/`` and
linked with ``/static/...`` URLs. The default deployment-plan size limit is
1024 MB so a typical stimulus set can ship in the experiment image. Before
raising ``EXP_MAX_SIZE_MB`` further, run ``dallinger deployment-files list``
and exclude anything that should stay local. Heroku deploys are capped at
500 MB. Use PsyNet assets for recordings and other files created during the
experiment.
