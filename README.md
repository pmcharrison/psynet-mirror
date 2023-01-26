# Links

![Logo](psynet/resources/logo.svg)

PsyNet is a powerful new Python package for designing and running the next generation of online behavioural experiments.
It streamlines the development of highly complex experiment paradigms, ranging from simulated cultural evolution to
perceptual prior estimation to adaptive psychophysical experiments. Once an experiment is implemented, it can be
deployed with a single terminal command, which looks after server provisioning, participant recruitment, data-quality
monitoring, and participant payment. Researchers using PsyNet can enjoy a paradigm shift in productivity, running many
high-powered variants of the same experiment in the time it would ordinarily take to run an experiment once.

PsyNet is still heavily under development and we have not officially launched it yet. We plan to do so in early 2023.

To try some real-world PsyNet experiments for yourself, visit the following repositories:

- [Consonance profiles for carillon bells](https://github.com/pmcharrison/2022-consonance-carillon)
- [Emotional connotations of musical scales](https://github.com/pmcharrison/2022-musical-scales)
- [Vocal pitch matching in musical chords](https://github.com/pmcharrison/2022-vertical-processing-test)

For more information about PsyNet, visit the [documentation website](https://psynetdev.gitlab.io/PsyNet/).

# Running tests

## Via a local Python installation

```
python -m pytest
```

## Via Docker (WIP)

This assumes you've performed certain setup steps, see: https://github.com/Dallinger/Dallinger/pull/4293/files

```
# Build the Docker image
docker build --tag psynet-test .

# Start Redis/Postgres services
docker start dallinger_redis dallinger_postgres

# Launch a terminal in the Docker container
docker run --rm -it --network dallinger -p 5000:5000 -e HEADLESS=TRUE -e FLASK_OPTIONS='-h 0.0.0.0' -e REDIS_URL=redis://dallinger_redis:6379 -e DATABASE_URL=postgresql://dallinger:dallinger@dallinger_postgres/dallinger -v $HOME/.dallingerconfig:/root/.dallingerconfig psynet-test

# Run all tests (if you want)
pytest

# Run a particular test
pytest tests/isolated/test_demo_error_handling.py -s --chrome

pytest tests/isolated/test_demo_gibbs.py -s --chrome

# Run a particular experiment test
cd /psynet/demos/static_audio
pytest -s test.py

# Close the Docker container with CTRL-D
```
