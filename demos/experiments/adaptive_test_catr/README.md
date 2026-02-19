# Adaptive Testing with catR Demo

This experiment demonstrates how to use the **catR** R package for computerized adaptive testing (CAT) in a PsyNet experiment via **rpy2**.

## Overview

The catR package provides sophisticated psychometric methods for adaptive testing, including:
- Various item selection algorithms (Maximum Fisher Information, etc.)
- Multiple ability estimation procedures (Maximum Likelihood, Bayesian, etc.)
- Stopping rules and test control mechanisms

This demo shows how to integrate R packages into your PsyNet experiments using the `prepare_docker_image.sh` mechanism.

## Key Files

- `prepare_docker_image.sh`: Installs R and the catR package in the Docker image
- `requirements.txt`: Includes rpy2 for Python-R interfacing
- `experiment.py`: Demonstrates using catR functions from Python

## Running Locally

For local testing, you'll need to install R and catR on your system:

```bash
# Install R (varies by OS)
# Ubuntu/Debian:
sudo apt-get install r-base r-base-dev

# macOS:
brew install r

# Install catR package
R -e "install.packages('catR', repos='https://cloud.r-project.org/')"

# Install Python dependencies
pip install rpy2
```

Then run the experiment:

```bash
psynet debug local
```

## Deploying with Docker

When you deploy this experiment using PsyNet's Docker mode (default for SSH deployment), the `prepare_docker_image.sh` script will automatically install R and catR in the Docker container. No additional configuration is needed!

## Further Information

This experiment is implemented using *PsyNet*, a framework for running behavioral experiments
in-person and over the internet. For comprehensive guidance on running PsyNet experiments,
please visit [PsyNet's documentation website](https://psynetdev.gitlab.io/PsyNet/).
