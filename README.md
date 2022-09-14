# Links

![Logo](psynet/resources/logo.svg)

- [Online documentation](https://computational-audition-lab.gitlab.io/psynet/)
- [Contribution guidelines](https://computational-audition-lab.gitlab.io/psynet/developer/basic_workflow.html)

# Running tests

## Via a local Python installation

```
python -m pytest
```

## Via Docker (WIP)

```
# Build the Docker image
docker build --tag psynet-test .

# Start Redis/Postgres services
docker start dallinger_redis dallinger_postgres

# Launch a terminal in the Docker container
docker run --rm -it --network dallinger -p 5000:5000 -e FLASK_OPTIONS='-h 0.0.0.0' -e REDIS_URL=redis://dallinger_redis:6379 -e DATABASE_URL=postgresql://dallinger:dallinger@dallinger_postgres/dallinger -v $HOME/.dallingerconfig:/root/.dallingerconfig psynet-test

# Run all tests (if you want)
python -m pytest  

# Run a particular experiment test
cd /psynet/demos/static_audio
pytest -s test.py

# Close the Docker container with CTRL-D
```

# Building documentation locally

```
make -C docs html
open docs/_build/html/index.html
```
