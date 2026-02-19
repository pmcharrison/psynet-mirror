#!/bin/sh
set -e

apt-get update
apt-get install -y --no-install-recommends r-base r-base-dev
R -e "install.packages('catR', repos='https://cloud.r-project.org/')"
