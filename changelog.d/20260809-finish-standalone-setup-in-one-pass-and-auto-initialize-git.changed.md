Changed ``psynet setup`` so that choosing a dedicated ``.venv`` completes in a
single invocation: setup creates the environment, installs the same PsyNet into
it, and finishes there so every experiment file and lockfile is produced by the
PsyNet the experiment will use. Setup now also initializes a Git repository
automatically when the directory is not already inside one (reporting what it
did), and prints a "Useful commands" section for activating the environment and
launching the experiment.
