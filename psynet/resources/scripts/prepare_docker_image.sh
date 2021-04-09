#!/bin/sh

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git
# Save space taken by the final image by removing unnecessary files
rm -rf /var/lib/apt/lists/*
