FROM ghcr.io/dallinger/dallinger:11.5.3
# If you want to pin a Dallinger development version, don't do it here!
# Instead pin it below (see comments)
#
# To build locally, run something like this (including the period at the end of the line!):
# docker build -t registry.gitlab.com/psynetdev/psynet:v10.4.0 .

RUN mkdir /PsyNet
WORKDIR /PsyNet

COPY pyproject.toml pyproject.toml
COPY LICENSE LICENSE

RUN apt update && apt -f -y install curl gettext jq libasound2 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libgbm1 libnss3 libpq-dev libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 redis-server unzip
RUN service redis-server start
RUN curl -O https://cli-assets.heroku.com/install.sh
RUN sh -x install.sh

RUN pip install --upgrade pip
RUN pip install pip-tools --upgrade

RUN export HEADLESS=TRUE

# Ultimately we might want to decouple dev requirements from the Docker distribution
COPY ./requirements.in requirements.in
# For some reason you need a README before you can run pip-compile...?
RUN touch README.md

COPY psynet/version.py psynet/version.py

RUN pip-compile requirements.in /dallinger/requirements.txt --verbose --output-file requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-dependencies -e .

# The following code can be used to reinstall Dallinger from a particular development branch or commit
# RUN pip install "git+https://github.com/Dallinger/Dallinger.git@pmch-dev"

WORKDIR /PsyNet
COPY ./README.md README.md

RUN mkdir /psynet-data
RUN chmod a+rwx -R /psynet-data

#RUN mkdir /psynet-data/export
#RUN chmod a+rwx -R /psynet-data/export
#
#RUN mkdir /psynet-debug-storage
#RUN chmod a+rwx -R /psynet-debug-storage

RUN mkdir /.cache
RUN chmod a+rwx -R /.cache

RUN mkdir /.local
RUN chmod a+rwx -R /.local

RUN mkdir -p ~/.ssh && echo "Host *\n    StrictHostKeyChecking no" >> ~/.ssh/config

ENV PSYNET_IN_DOCKER=1
