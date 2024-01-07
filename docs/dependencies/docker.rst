.. _docker:

Docker
======

PsyNet uses Docker as a platform for developing and deploying experiments.
Docker is a virtualization platform that runs software in 'containers' that behave like
self-contained operating systems. Docker brings several key advantages:

- **Simplifying installation.** Previously it would take many steps to install PsyNet on a local computer,
  as one had to install many supporting services such as Redis and Postgres. Now all of this is wrapped in Docker,
  so the installation process is massively simplified.
- **Simplifying environment management.** Previously one had to to be very careful about the maintenance of
  'virtual environments' that kept appropriate versions of packages installed for given experiment implementations.
  It was easy to get these virtual environments mixed up, or broken. With Docker, the user doesn't have to worry
  about any of this, as Docker manages everything.
- **Simplifying deployment.** Using Docker, experiments are deployed via identical Docker images to those used
  for local debugging. This significantly reduces the possibility of unforeseen divergences between local and
  deployment environments that might cause bugs.
- **Enhancing reproducibility.**  When we deploy an experiment using Docker, the experiment deployment is then
  stored as a standalone Docker image that captures all of its dependencies, and should be perfectly reproducible
  years into the future. This contrasts with previous approaches, where incremental changes to Python versions
  and operating system conditions would often eventually break experiments.

For more information see the `official Docker website <https://www.docker.com/>`_.
