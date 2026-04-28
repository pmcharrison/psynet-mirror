# `announce_release.py`

Post a PsyNet release announcement to the `#psynet-support` Slack
channel. RC vs final flavour is auto-detected from the version string
(`(rc|a|b)\d+$` → release-candidate template).

The output is Slack `mrkdwn` — single-asterisk bold, single-backtick
inline code, and `<URL|label>` for clickable links.

## One-time setup

1. **Create a Slack app** at <https://api.slack.com/apps> → *Create New
   App* → *From scratch*. Pick the workspace that owns
   `#psynet-support`. A descriptive name (e.g. `PsyNet Releases`)
   helps recipients recognise the bot.
2. **Add the bot scope.** In *OAuth & Permissions* → *Bot Token
   Scopes*, add `chat:write`. Optionally also add `chat:write.public`
   so the bot can post without being explicitly invited.
3. **Install to the workspace** from the top of *OAuth & Permissions*.
   Workspace admin approval may be required.
4. **Invite the bot to the channel** (skip if you added
   `chat:write.public`):

   ```text
   /invite @PsyNet Releases
   ```

5. **Copy the bot token** (`xoxb-…`) from *OAuth & Permissions*. Treat
   it like a password — it grants posting rights to anyone who has it.

## Token storage

`.env` at the repo root is gitignored, so it's a safe place:

```bash
# /home/<you>/projects/PsyNet/.env
SLACK_BOT_TOKEN=xoxb-...
```

Or export it from `~/.zshrc` if you'd rather have it available
everywhere. Or pass it inline for one-shot use:

```bash
SLACK_BOT_TOKEN=xoxb-... python docs/scripts/announce_release.py 13.2.0
```

## Usage

```bash
# Preview the message without posting (always do this first)
python docs/scripts/announce_release.py 13.2.0rc0 --dry-run
python docs/scripts/announce_release.py 13.2.0    --dry-run

# Actually post
python docs/scripts/announce_release.py 13.2.0rc0
python docs/scripts/announce_release.py 13.2.0

# Override channel (default: psynet-support)
python docs/scripts/announce_release.py 13.2.0 --channel some-other-channel
```

The script exits non-zero on Slack API errors or missing dependencies,
so it can be wired into release scripts safely.

## Dependencies

The script requires `slack_sdk`, which is provided by PsyNet's
`[slack]` extra:

```bash
uv pip install -e '.[dev,slack]'
```

This is already part of the prerequisites listed in `RELEASE_MINOR.md`
and `RELEASE_PATCH.md`.

## Where this fits in the release flow

See the **Announce the release on Slack** step in:

- `RELEASE_MINOR.md` — step 12 (final) and RC sub-step 7.
- `RELEASE_PATCH.md` — when patch releases also adopt the step.

The step is gated by an explicit human checkpoint: the message body
must be approved (via `--dry-run`) before any real post.
