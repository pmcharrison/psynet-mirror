# The static directory

Put public, immutable files here (scripts, images, audio, video). A file at
`static/audio/clip.mp3` is served as `/static/audio/clip.mp3` and is copied
with the experiment when you deploy.

This demo's StepTag control still expects PsyNet Asset objects. The experiment
wraps each static URL in `ExternalAsset` so playback uses `/static/...`
without uploading a second copy.
