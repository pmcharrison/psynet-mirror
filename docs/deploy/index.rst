Deploying
=========

.. warning::

   The ``deploy.toml`` compatibility prototype currently requires POSIX
   descriptor-relative filesystem traversal and is not supported on Windows.
   A safe Windows-support carve-out is required before production rollout.
   Policy-free experiments continue to use Dallinger's existing legacy,
   cross-platform selection path outside this all-migrated PsyNet prototype.

.. toctree::
   :maxdepth: 1

   web_servers
   aws_automatic_provisioning
   aws_server_setup
   physical_server_setup
   ssh_server
   heroku_server
   deploy_from_archive
   data
   deployment_monitor
   errors
   troubleshooting
