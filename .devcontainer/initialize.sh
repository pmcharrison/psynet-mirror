# This script runs before the container is created.
# It ensures the .dallinger directory and .dallingerconfig file exist to avoid mount errors.

mkdir -p ~/.dallinger
[ -d ~/.dallingerconfig ] && rm -rf ~/.dallingerconfig
touch ~/.dallingerconfig
