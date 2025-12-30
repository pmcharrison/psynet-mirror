# TODO: Update to Python 3.13 once the tests pass with 3.12
FROM python:3.12-bookworm

RUN pip install uv

# TODO: delete some of these if we can
RUN apt update && apt -f -y install curl gettext jq libasound2 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libgbm1 libnss3 libpq-dev libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 redis-server unzip nodejs npm

# Heroku CLI is currently needed to run `psynet test local`, this should change soon
RUN curl https://cli-assets.heroku.com/install.sh | sh
RUN service redis-server start
ENV HEADLESS=TRUE

RUN mkdir /PsyNet
WORKDIR /PsyNet

COPY pyproject.toml pyproject.toml

# Generate constraints.txt
RUN curl -s https://raw.githubusercontent.com/Dallinger/Dallinger/master/dallinger/constraints.py | uv run - generate

RUN uv pip install --no-cache --system -r constraints.txt

COPY . .

RUN uv pip install --no-deps --system -e .

# RUN mkdir /psynet-data
# RUN chmod a+rwx -R /psynet-data

# RUN mkdir /.cache
# RUN chmod a+rwx -R /.cache

# RUN mkdir /.local
# RUN chmod a+rwx -R /.local

# RUN mkdir -p ~/.ssh && echo "Host *\n    StrictHostKeyChecking no" >> ~/.ssh/config
