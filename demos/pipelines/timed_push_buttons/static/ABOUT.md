# The static directory

Put public, immutable files here (scripts, images, audio, video). A file at
`static/global_music/clip.mp3` is served as `/static/global_music/clip.mp3`
and is copied with the experiment when you deploy.

Pregenerated stimulus sets belong here. You do not need PsyNet assets for
playback; pass the `/static/...` URL to `AudioPrompt`. Gitignore large
binaries if you like — `deploy.toml` still includes `static/` (except
generated `static/assets`).

Use the asset system for files created during the experiment, especially
participant recordings.
