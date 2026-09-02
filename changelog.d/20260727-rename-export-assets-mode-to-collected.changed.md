Renamed the default export asset mode from ``experiment`` to ``collected``.

``--assets collected`` exports managed assets deposited during the deployment
(for example recordings), excluding cached stimuli, external URLs, and
on-demand generation. ``--assets all`` still includes those pre-existing and
generated assets. The dashboard export UI uses the same wording.
