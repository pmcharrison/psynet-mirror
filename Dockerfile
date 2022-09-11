FROM ghcr.io/dallinger/dallinger:9.1.0a1

RUN mkdir /psynet
WORKDIR /psynet

COPY setup.py setup.py

RUN apt update
RUN apt -f -y install curl redis-server unzip libpq-dev
RUN service redis-server start
RUN curl https://cli-assets.heroku.com/install.sh | sh
RUN wget -O chrome.deb http://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_101.0.4951.64-1_amd64.deb
RUN wget -O chrome-driver.zip https://chromedriver.storage.googleapis.com/101.0.4951.41/chromedriver_linux64.zip
RUN apt -f -y install ./chrome.deb
RUN unzip chrome-driver.zip chromedriver -d /usr/local/bin/

# TODO - Remove melody package and demo from PsyNet
RUN pip install "git+https://gitlab+deploy-token-478431:98jnkW1yq_AYWLYpRNtN@gitlab.com/computational-audition-lab/melody/melody-experiments@master#egg=melody_experiments[extract]"
RUN pip install "git+https://repp:tvKi4cirMxgnuf9s4Vma@gitlab.com/computational-audition-lab/repp@master#egg=repp"
RUN pip install "git+https://reppextension:s_Ux2u-2emzHPK4kVq6g@gitlab.com/computational-audition-lab/repp-technology/reppextension#egg=reppextension"
RUN pip install pytest-test-groups
RUN export HEADLESS=TRUE

# Ultimately we might want to decouple dev requirements from the Docker distribution
COPY ./dev-requirements.in dev-requirements.in
COPY ./README.md README.md

RUN pip-compile dev-requirements.in --verbose
RUN pip install --no-cache-dir -r dev-requirements.txt
RUN pip install -r dev-requirements.txt

COPY . /psynet
RUN pip install -e .
COPY ./ci/.dallingerconfig /root/.dallingerconfig
