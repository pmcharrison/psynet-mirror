---
name: public-tunnel
description: Start an ephemeral public HTTPS tunnel to a local HTTP service for live review from a browser.
authors: [pmcharrison]
---

# Public tunnel

Use this skill when a user asks to expose an already-running local HTTP service from Cursor Cloud through a temporary public HTTPS URL.
Note that the URL is temporary and dies when the tunnel process or VM stops.

## Helper script

Use this skill's `scripts/public_tunnel.py` (relative to the active skill
directory). Locate the skill directory from the active skills tree, for example:

- PsyNet source: `.cursor/skills/experiment/public-tunnel`
- Experiment skill bundle: `.cursor/skills/psynet/public-tunnel`

The helper:

- chooses `cloudflared`, `localtunnel`, or `npx -y localtunnel`;
- downloads temporary `/tmp/cloudflared` if needed;
- starts the tunnel to `http://127.0.0.1:<port>`;
- prints `Public tunnel ready` when it detects the public URL;
- provides URL helpers for caller workflows.

## Workflow

1. Confirm the local service is already running:
   `curl -I --max-time 10 http://127.0.0.1:<port>/`
2. Start `scripts/public_tunnel.py` in its own tmux session (replace
   `<skill-dir>` with the located skill directory above):
   `tmux -f /exec-daemon/tmux.portal.conf new-session -d -s <name>-public-tunnel -- uv run python <skill-dir>/scripts/public_tunnel.py --port <port>`
3. Watch that session for `Public tunnel ready`.
4. Verify the public URL:
   `curl -I --max-time 20 <public-url>`
