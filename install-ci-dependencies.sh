# Chrome and ChromeDriver come from the Docker image.
# Install PsyNet from the mounted workspace plus the demo-only dependency
# needed by static_audio in CI.
PSYNET_WORKSPACE=${PSYNET_WORKSPACE:-/root/workspaces/PsyNet}
uv pip install --no-cache --system --no-deps -e "$PSYNET_WORKSPACE"
uv pip install --no-cache --system praat-parselmouth
