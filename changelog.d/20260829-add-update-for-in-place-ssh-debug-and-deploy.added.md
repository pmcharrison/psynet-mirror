Added ``--update`` / ``-u`` to ``psynet debug ssh`` and ``psynet deploy ssh``
so you can rebuild a running SSH app without wiping participant data.
Pre-deposited stimulus files stay in place, recruitment is not re-opened,
and the command warns against timeline changes while anyone is still taking
the experiment.
