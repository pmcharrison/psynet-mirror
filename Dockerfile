FROM ghcr.io/dallinger/dallinger:10.0.1
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
RUN curl https://cli-assets.heroku.com/install.sh | sh
RUN CHROME_VERSION=$(curl https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | jq .channels.Stable.version | tr -d '"') && \
    echo Installing Chrome $CHROME_VERSION && \
    wget -O chrome.deb https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome.deb -d /opt/ && \
    ln -s /opt/chrome-linux64/chrome /usr/local/bin/chrome && \
    echo "Successfully installed Chrome $(chrome --version)" && \
    echo Installing ChromeDriver $CHROME_VERSION && \
    wget -O chrome-driver.zip https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chrome-driver.zip -d /usr/local/bin/ && \
    ln -s /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    echo "Successfully installed ChromeDriver $(chromedriver --version)"

# TODO - Remove melody package and demo from PsyNet
RUN pip install --upgrade pip
RUN pip install "git+https://gitlab+deploy-token-478431:98jnkW1yq_AYWLYpRNtN@gitlab.com/computational-audition-lab/melody/melody-experiments@master#egg=melody_experiments[extract]"
RUN pip install "git+https://repp:tvKi4cirMxgnuf9s4Vma@gitlab.com/computational-audition/repp@master#egg=repp"
RUN pip install "git+https://reppextension:s_Ux2u-2emzHPK4kVq6g@gitlab.com/computational-audition-lab/repp-technology/reppextension#egg=reppextension"
RUN pip install pytest-test-groups
RUN export HEADLESS=TRUE

# Ultimately we might want to decouple dev requirements from the Docker distribution
COPY ./dev-requirements.in dev-requirements.in
# For some reason you need a README before you can run pip-compile...?
RUN touch README.md

COPY psynet/version.py psynet/version.py

RUN pip install pip-tools --upgrade
RUN pip-compile dev-requirements.in /dallinger/requirements.txt --verbose --output-file dev-requirements.txt
RUN pip install --no-cache-dir -r dev-requirements.txt

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
