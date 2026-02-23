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

# Generate PsyNet constraints.txt and install it
RUN curl -s https://raw.githubusercontent.com/Dallinger/Dallinger/master/dallinger/constraints.py | uv run - generate
RUN uv pip install --no-cache --system -r constraints.txt

# Compile and install demo requirements using Dallinger constraints
COPY demos/requirements.txt demo-requirements.txt
RUN DALLINGER_REQ=$(python3 - <<'PY'\nimport tomllib\nfrom pathlib import Path\n\ndata = tomllib.loads(Path(\"pyproject.toml\").read_text(encoding=\"utf-8\"))\nfor dep in data[\"project\"][\"dependencies\"]:\n    if dep.startswith(\"dallinger\"):\n        print(dep)\n        break\nelse:\n    raise SystemExit(\"Dallinger dependency not found in pyproject.toml\")\nPY\n) \\\n+    && mkdir -p /tmp/demo-constraints \\\n+    && cp demo-requirements.txt /tmp/demo-constraints/demo-requirements.txt \\\n+    && printf \"%s\\n-r demo-requirements.txt\\n\" \"$DALLINGER_REQ\" > /tmp/demo-constraints/requirements.txt \\\n+    && (cd /tmp/demo-constraints && curl -s https://raw.githubusercontent.com/Dallinger/Dallinger/master/dallinger/constraints.py | uv run - generate) \\\n+    && uv pip install --no-cache --system -r /tmp/demo-constraints/constraints.txt
