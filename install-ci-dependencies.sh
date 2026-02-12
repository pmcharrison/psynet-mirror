# Chrome, ChromeDriver, and demos/requirements.txt are now installed in the Dockerfile
# Install PsyNet itself, then Playwright + its browsers for e2e tests
PSYNET_WORKSPACE=${PSYNET_WORKSPACE:-/root/workspaces/PsyNet}
uv pip install --no-cache --system --no-deps -e "$PSYNET_WORKSPACE"
npm install
npx playwright install chromium
