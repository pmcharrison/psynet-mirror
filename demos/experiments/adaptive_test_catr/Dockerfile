# This Dockerfile is used both to specify a functional development environment
# (e.g. on GitHub Codespaces) and a deployment image.

FROM python:3.13-bookworm

RUN pip install uv


# This is necessary for installing Heroku CLI. Remove it once we remove Heroku.
# Heroku CLI is currently needed to run `psynet test local`, this should change soon
RUN apt-get update && apt-get install -y nodejs npm
RUN curl https://cli-assets.heroku.com/install.sh | sh

RUN mkdir /experiment
WORKDIR /experiment

COPY requirements.txt requirements.txt
COPY *constraints.txt constraints.txt
COPY *prepare_docker_image.sh prepare_docker_image.sh

ENV SKIP_DEPENDENCY_CHECK=""
ENV DALLINGER_NO_EGG_BUILD=1

# Run prepare_docker_image.sh BEFORE installing Python packages
# This is necessary because some Python packages (like rpy2) require
# system dependencies (like R) to be installed first
RUN if test -f prepare_docker_image.sh ; then bash prepare_docker_image.sh ; fi

RUN if [ -f constraints.txt ]; then \
        uv pip install -r constraints.txt --system; \
    else \
        uv pip install -r requirements.txt --system; \
    fi

COPY . /experiment

ENV PORT=5000

CMD dallinger_heroku_web
