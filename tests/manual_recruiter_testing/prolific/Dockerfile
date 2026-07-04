FROM python:3.13-bookworm

RUN pip install uv

# This is necessary for installing Heroku CLI. Remove it once we remove Heroku.
# Heroku CLI is currently needed to run `psynet test local`, this should change soon
RUN apt-get update && apt-get install -y nodejs npm
RUN curl https://cli-assets.heroku.com/install.sh | sh

RUN mkdir /experiment
WORKDIR /experiment

COPY requirements.txt requirements.txt

ENV SKIP_DEPENDENCY_CHECK=""
ENV DALLINGER_NO_EGG_BUILD=1

RUN uv pip install -r requirements.txt --system

COPY *prepare_docker_image.sh prepare_docker_image.sh
RUN if test -f prepare_docker_image.sh ; then bash prepare_docker_image.sh ; fi

COPY . /experiment

ENV PORT=5000

ARG REMOTE_DEBUGGER_PORT
EXPOSE $REMOTE_DEBUGGER_PORT

CMD dallinger_heroku_web
