Installation overview
=====================

There are several possible ways to install PsyNet on your local machine.
The right way will depend on the computer that you have and the things that you want to do with PsyNet.

One approach is to use **Docker**. Docker simplifies some aspects of using PsyNet; it makes it much simpler
to install, and it makes it easier to manage your experiment dependencies.
It's also the only possible way to run PsyNet on a Windows computer.
However, it does have a couple of disadvantages.

One disadvantage is that Docker is a relatively recent method of installing
PsyNet, so we are still working out various edge cases for cross-platform compatibility.
In particular, deploying experiments from a local Docker installation is not very well tested yet,
and may not work out-of-the box for all machines. We're keen to hear your experiences though as they will
help us to resolve these issues.

A second issue is that running code in Docker can be slower than running it natively. In particular, we are aware
that Dockerized PsyNet runs rather slowly on Apple Silicon (M1/M2) Macs, due to the need for these platforms
to emulate Intel processing. If you experience problems on such hardware, you should consider following the
alternative installation approach. Docker also incurs additional RAM overhead, so you might want to avoid it
if your computer doesn't have much RAM.

An alternative approach is to use the so-called **developer** route. This involves installing various
related services (e.g. Heroku, Redis, Postgres), which makes the installation process relatively involved.
However once you've done all this you do get good access to the underlying software components of PsyNet,
and this can be helpful for making contributions to PsyNet itself.

We recommend you bear these issues in mind when choosing to install PsyNet via the Docker route or the
developer route. In either case, do let us know how you get on as it can help us to improve the
installation processes.

.. toctree::
    :maxdepth: 1

    docker_installation/index
    developer_installation/index
