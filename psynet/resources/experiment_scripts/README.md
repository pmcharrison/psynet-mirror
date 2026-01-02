# README

This experiment is implemented using *PsyNet*, a framework for running behavioral experiments
in-person and over the internet. For comprehensive guidance on running PsyNet experiments,
please visit [PsyNet's documentation website](https://psynetdev.gitlab.io/PsyNet/).
Alternatively, see the quickstart guide below.

## Quickstart

This experiment is configured using [Dev Containers](https://containers.dev/),
which automates the process of installing PsyNet on your local machine.
To run the experiment, you just need to do the following:

1. Download the repository.
2. Open your IDE (we recommend VSCode, which you can download for free. Cursor also works well).
3. In your IDE, select 'Open Folder', and open the downloaded repository.
4. Follow the prompt to launch the workspace in a Dev Container (if prompted, select 'Mount', not 'Clone').
5. Wait until the automatic configuration scripts have stopped running (it should take 30-60 seconds).
6. Launch the experiment by running `psynet debug local` in the terminal.

Note that the above process should work on MacOS/Linux/Windows, although it's best tested on MacOS.

If you would like to explore alternative installation routes, please visit
[PsyNet's documentation website](https://psynetdev.gitlab.io/PsyNet/).
