FROM ghcr.io/dallinger/dallinger:9.4.3
# If you want to pin a Dallinger development version, don't do it here!
# Instead pin it below (see comments)
#
# To build locally, run something like this (including the period at the end of the line!):
# docker build -t registry.gitlab.com/psynetdev/psynet:master .

RUN mkdir /PsyNet
WORKDIR /PsyNet

COPY pyproject.toml pyproject.toml
COPY LICENSE LICENSE

RUN apt update
RUN apt -f -y install curl redis-server unzip libpq-dev
RUN service redis-server start
RUN curl https://cli-assets.heroku.com/install.sh | sh
RUN wget -O chrome.deb http://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_109.0.5414.74-1_amd64.deb
RUN wget -O chrome-driver.zip https://chromedriver.storage.googleapis.com/109.0.5414.74/chromedriver_linux64.zip
RUN apt -f -y install ./chrome.deb
RUN unzip chrome-driver.zip chromedriver -d /usr/local/bin/

# TODO - Remove melody package and demo from PsyNet
RUN pip install --upgrade pip
RUN pip install "git+https://gitlab+deploy-token-478431:98jnkW1yq_AYWLYpRNtN@gitlab.com/computational-audition-lab/melody/melody-experiments@master#egg=melody_experiments[extract]"
RUN pip install "git+https://repp:tvKi4cirMxgnuf9s4Vma@gitlab.com/computational-audition-lab/repp@master#egg=repp"
RUN pip install "git+https://reppextension:s_Ux2u-2emzHPK4kVq6g@gitlab.com/computational-audition-lab/repp-technology/reppextension#egg=reppextension"
RUN pip install pytest-test-groups
RUN export HEADLESS=TRUE

# Ultimately we might want to decouple dev requirements from the Docker distribution
COPY ./dev-requirements.in dev-requirements.in
# For some reason you need a README before you can run pip-compile...?
RUN touch README.md

COPY psynet/version.py psynet/version.py

RUN pip-compile dev-requirements.in --verbose
RUN pip install --no-cache-dir -r dev-requirements.txt
RUN pip install -r dev-requirements.txt

COPY . .
RUN pip install --no-dependencies -e .

# The following code can be used to reinstall Dallinger from a particular development branch or commit
# RUN pip install "git+https://github.com/Dallinger/Dallinger.git@pmch-dev"

WORKDIR /PsyNet
COPY ./ci/.dallingerconfig /root/.dallingerconfig
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
