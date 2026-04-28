# Use linux/amd64 platform to ensure x86_64 wheels are available (faster builds)
# On Apple Silicon Macs, Docker will emulate x86_64 but pip can use pre-built wheels
# Can be overridden with: docker build --build-arg DOCKER_PLATFORM=linux/arm64
ARG DOCKER_PLATFORM=linux/amd64
FROM --platform=${DOCKER_PLATFORM} python:3.13-bookworm

RUN pip install uv

# TODO: delete some of these if we can
RUN apt-get update && apt-get install -y curl gettext jq libasound2 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libgbm1 libnss3 libpq-dev libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 redis-server unzip nodejs npm wget build-essential

# Heroku CLI is currently needed to run `psynet test local`, this should change soon
RUN curl https://cli-assets.heroku.com/install.sh | sh
RUN service redis-server start
ENV HEADLESS=TRUE

# Install Chrome and ChromeDriver
RUN CHROME_VERSION=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | jq .channels.Stable.version | tr -d '"') && \
    echo Installing Chrome $CHROME_VERSION && \
    wget -O chrome.deb https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome.deb -d /opt/ && \
    ln -s /opt/chrome-linux64/chrome /usr/local/bin/chrome && \
    echo "Successfully installed Chrome $(chrome --version)" && \
    echo Installing ChromeDriver $CHROME_VERSION && \
    wget -O chrome-driver.zip https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chrome-driver.zip -d /usr/local/bin/ && \
    ln -s /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    echo "Successfully installed ChromeDriver $(chromedriver --version)" && \
    rm -f chrome.deb chrome-driver.zip

COPY pyproject.toml pyproject.toml

# Generate PsyNet constraints.txt (PyPI deps from the [demos] extra) and install it
RUN curl -s https://raw.githubusercontent.com/Dallinger/Dallinger/master/dallinger/constraints.py | uv run - generate --extra demos
RUN uv pip install --no-cache --system -r constraints.txt

# Install private demo dependencies (repp / reppextension / sing4me).
# These cannot live in pyproject.toml's [demos] extra because PyPI
# rejects "direct URL" dependencies in published distribution metadata.
# Instead we harvest their `pkg@git+https://...` URL lines directly from
# the demo-level requirements.txt files (which remain the single source
# of truth for what each demo needs).
COPY demos/experiments/tapping_iterated/requirements.txt    /tmp/req-iterated.txt
COPY demos/experiments/tapping_memory/requirements.txt      /tmp/req-memory.txt
COPY demos/experiments/tapping_static/requirements.txt      /tmp/req-static.txt
COPY demos/experiments/repp_prescreen/requirements.txt      /tmp/req-prescreen.txt
COPY demos/features/rhythm_slider/requirements.txt          /tmp/req-rhythm.txt
COPY demos/experiments/vertical_processing/requirements.txt /tmp/req-vertical.txt
RUN grep -hE '^(repp|reppextension|sing4me)@' /tmp/req-*.txt \
    | sort -u > /tmp/private-deps.txt && \
    echo "Installing private demo deps:" && cat /tmp/private-deps.txt && \
    uv pip install --no-cache --system -r /tmp/private-deps.txt && \
    rm -f /tmp/req-*.txt /tmp/private-deps.txt
