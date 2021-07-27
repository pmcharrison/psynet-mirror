#!/bin/sh
# If you need some extra requirement in your dyno's environment
# (for example the ffmpeg binary) you can add a prepare_docker_image.sh
# file to your experiment directory.
# It will be run when preparing a docker image. Anything installed
# by this script will be available to the experiment code.

# If you want to customize this image setup process in your own PsyNet experiment,
# copy this file into your experiment's working directory, and modify it as you wish.

# Note: Sometimes we have seen an issue with psycopg2 where it can't find the right binary.
# It seems that this can be solved by pinning an older version of psycopg2 in requirements.txt, as follows:
# psycopg2==2.8.6

# Here we install build tools so that the Docker image can build packages from source.
apt-get update
apt-get install build-essential -y
apt-get install python3-dev -y
