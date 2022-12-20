.. _docker:

Docker
======

It is now possible to develop PsyNet experiments entirely within Docker.
Docker is a virtualization platform that runs software in 'containers' that behave like
self-contained operating systems. This enables us to run the same PsyNet code on different
operating systems (Windows, MacOS, Linux) without worrying about differences between these environments.
For more information see https://www.docker.com/.

We are starting to encourage people to use Docker as the primary approach for developing and deploying
PsyNet experiments. It has several key advantages:

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

There are a few disadvantages too -- we think they're small, but worth noting nonetheless.

- Using Docker introduces a performance overhead to local debugging, meaning slower start-up times
  and increased memory usage. It's helpful to use a computer with at least 16 GB of RAM.
- Docker adds an extra layer between you and code execution, which can make it a little harder to debug
  processes. However there are various techniques that can reduce the impact of this which we'll talk about later.
