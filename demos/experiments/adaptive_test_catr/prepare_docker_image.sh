#!/bin/sh
# This script installs R and the catR package for adaptive testing.
# It will be run when preparing the Docker image for deployment.

# Update package lists
apt-get update

# Install R and required dependencies
# r-base: The R statistical computing environment
# r-base-dev: Development files for building R packages
apt-get install -y r-base r-base-dev

# Install catR package from CRAN
# This R command installs the catR package which provides methods for computerized adaptive testing
R -e "install.packages('catR', repos='https://cloud.r-project.org/')"

# Verify installation
R -e "library(catR); cat('catR version:', as.character(packageVersion('catR')), '\n')"
