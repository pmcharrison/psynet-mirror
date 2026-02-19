# Using R Packages in PsyNet with prepare_docker_image.sh

This guide explains how to use R packages (like catR) in PsyNet experiments via rpy2, addressing Tim Schäfer's question about integrating the catR R package for adaptive testing.

## Overview

PsyNet provides a mechanism called `prepare_docker_image.sh` that allows you to install arbitrary system dependencies (including R and R packages) into your Docker image. This works seamlessly with both Docker-based deployments and local development.

## How It Works

When you deploy a PsyNet experiment using Docker (which is the default for SSH deployment to custom servers), PsyNet looks for a file called `prepare_docker_image.sh` in your experiment directory. If found, this shell script is executed during the Docker image build process, allowing you to install any system dependencies you need.

The relevant line in the Dockerfile is:

```dockerfile
COPY *prepare_docker_image.sh prepare_docker_image.sh
RUN if test -f prepare_docker_image.sh ; then bash prepare_docker_image.sh ; fi
```

## Step-by-Step Instructions

### 1. Add rpy2 to requirements.txt

First, add the `rpy2` package to your experiment's `requirements.txt`:

```text
psynet@git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet
rpy2
```

### 2. Create prepare_docker_image.sh

Create a file called `prepare_docker_image.sh` in your experiment directory with the following content:

```bash
#!/bin/sh
# Install R and required R packages for adaptive testing

# Update package lists
apt-get update

# Install R and development files
apt-get install -y r-base r-base-dev

# Install the catR package from CRAN
R -e "install.packages('catR', repos='https://cloud.r-project.org/')"

# Optional: Verify installation
R -e "library(catR); cat('catR version:', as.character(packageVersion('catR')), '\n')"
```

Make sure the script is executable:

```bash
chmod +x prepare_docker_image.sh
```

### 3. Use R packages in your experiment code

Now you can use catR functions in your Python experiment code via rpy2:

```python
from rpy2.robjects.packages import importr
import rpy2.robjects as robjects

# Import the catR package
catr = importr('catR')

# Example: Estimate ability using Maximum Likelihood
def estimate_ability(responses, item_params):
    r_responses = robjects.IntVector(responses)
    r_item_bank = robjects.r.matrix(
        robjects.FloatVector([param for item in item_params for param in item]),
        nrow=len(item_params),
        ncol=4,
        byrow=True
    )
    
    result = catr.thetaEst(r_item_bank, r_responses, method="ML")
    theta = result[0][0]
    return float(theta)

# Example: Select next item using Maximum Fisher Information
def select_next_item(current_theta, item_bank):
    r_item_bank = robjects.r.matrix(
        robjects.FloatVector([param for item in item_bank for param in item]),
        nrow=len(item_bank),
        ncol=4,
        byrow=True
    )
    
    result = catr.nextItem(itemBank=r_item_bank, theta=current_theta, criterion="MFI")
    selected_idx = int(result[0]) - 1  # R uses 1-based indexing
    return selected_idx
```

## Deployment Scenarios

### Docker Deployment (psynet deploy)

When you run `psynet deploy` with Docker mode (default for SSH deployment):

1. PsyNet builds a Docker image for your experiment
2. During the build, it copies `prepare_docker_image.sh` into the image
3. It executes the script, installing R and catR
4. Your experiment runs with R and catR available

**No additional configuration needed!** The `prepare_docker_image.sh` mechanism handles everything automatically.

### Local Development (psynet debug local)

For local testing, you need to install R and catR on your development machine:

**Ubuntu/Debian:**
```bash
sudo apt-get install r-base r-base-dev
R -e "install.packages('catR', repos='https://cloud.r-project.org/')"
```

**macOS:**
```bash
brew install r
R -e "install.packages('catR', repos='https://cloud.r-project.org/')"
```

**Windows:**
Download and install R from https://cran.r-project.org/, then run:
```r
install.packages('catR')
```

Then install Python dependencies:
```bash
pip install rpy2
```

### Non-Docker Deployment

If you deploy without Docker (less common), you would need to manually install R and catR on your server before deploying the experiment.

## Complete Working Example

A complete working demo is available in the PsyNet repository at:

```
demos/experiments/adaptive_test_catr/
```

This demo includes:
- `prepare_docker_image.sh` - Installs R and catR
- `requirements.txt` - Includes rpy2
- `experiment.py` - Demonstrates using catR for adaptive testing
- `README.md` - Additional documentation

## Additional R Packages

You can install multiple R packages by adding more lines to `prepare_docker_image.sh`:

```bash
#!/bin/sh
apt-get update
apt-get install -y r-base r-base-dev

# Install multiple packages
R -e "install.packages(c('catR', 'ltm', 'mirt'), repos='https://cloud.r-project.org/')"
```

## Installing from GitHub/Bioconductor

For R packages not on CRAN:

```bash
# Install devtools first
R -e "install.packages('devtools', repos='https://cloud.r-project.org/')"

# Install from GitHub
R -e "devtools::install_github('username/package')"

# Install from Bioconductor
R -e "install.packages('BiocManager', repos='https://cloud.r-project.org/')"
R -e "BiocManager::install('package_name')"
```

## Troubleshooting

### rpy2 can't find R

Make sure R is properly installed and in your PATH. You may need to set the `R_HOME` environment variable:

```python
import os
os.environ['R_HOME'] = '/usr/lib/R'  # Adjust path as needed
```

### Package installation fails in Docker

Some R packages require additional system libraries. Add them to `prepare_docker_image.sh`:

```bash
apt-get install -y libcurl4-openssl-dev libssl-dev libxml2-dev
```

### Local vs Docker differences

Remember that `psynet debug local` mounts your local experiment directory over the Docker container's directory. Any files created by `prepare_docker_image.sh` in the experiment directory won't be accessible locally. Store generated files elsewhere in the container if needed.

## Summary

The `prepare_docker_image.sh` mechanism provides a clean, straightforward way to integrate R packages into PsyNet experiments:

1. ✅ Works seamlessly with Docker deployment
2. ✅ No special configuration needed beyond the script itself
3. ✅ Can install any R packages from CRAN, GitHub, or Bioconductor
4. ✅ Supports full rpy2 functionality for Python-R interoperability

For Tim's use case with catR for adaptive testing, this approach provides everything needed to run sophisticated computerized adaptive tests within PsyNet experiments.
