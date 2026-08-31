# The static directory

Put public, immutable files here (scripts, images, audio, video). A file at
`static/instrument_sounds/piano.mp3` is served as `/static/instrument_sounds/piano.mp3`
and is copied with the experiment when you deploy.

Pregenerated stimulus sets belong here. You do not need PsyNet assets for
playback; pass the `/static/...` URL to `AudioPrompt` or `MediaSpec`.
Gitignore large binaries if you like — `deploy.toml` still includes
`static/` (except generated `static/assets`).

Use the asset system for files created during the experiment, especially
participant recordings.
