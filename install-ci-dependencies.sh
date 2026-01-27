# Chrome, ChromeDriver, and demos/requirements.txt are now installed in the Dockerfile
# Only install PsyNet itself, which needs the mounted volume at runtime
PSYNET_WORKSPACE=${PSYNET_WORKSPACE:-/root/workspaces/PsyNet}
uv pip install --no-cache --system --no-deps -e "$PSYNET_WORKSPACE"
