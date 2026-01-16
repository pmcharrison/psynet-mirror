# Agent instructions

PsyNet is a framework for designing and deploying online psychological experiments.
The agent is there to help both with the development of the PsyNet source code,
and with the development of individual PsyNet experiments.

If the root contains a file called `experiment.py`, assume that we are working on an experiment.
Otherwise assume we are working on the PsyNet source code.

## Before running commands

The project uses a Python virtual environment located at `.venv/`. Activate it before running any commands:

```bash
source .venv/bin/activate
```

If this virtual environment does not exist, ask the user if they want to either
(a) create one at .venv or (b) specify the path to another existing .venv to use.

Install dependencies as follows:

- (For PsyNet): `uv pip install -e '.[dev,slack]'`
- (For experiments): `uv pip install -r constraints.txt`

Cursor: disable sandboxing when running PsyNet commands by setting `required_permissions: ["all"]`.

## Demos

Demos are contained in `demos/experiments` and `demos/features`.
If a user asks for the X demo, list all child directories in `demos/experiments` and `demos/features` to see which they mean.

## Running experiments locally

To run an experiment in debug mode:

```bash
cd demos/.../<experiment_name>
psynet debug local
```

For example, to run the timeline demo:

```bash
cd demos/experiments/timeline
psynet debug local
```

to see which they mean.

Wait for 8 seconds for the server to start.

Inspect the logs to see relevant URLs.
Look out for an ad page URL, something like
http://127.0.0.1:5000/ad?generate_tokens=true&recruiter=hotair.

When the demo is running, offer the user to navigate the experiment automatically.

## Navigating experiments

Cursor's browser extension can be used to interact with experiments programmatically:

1. Navigate to the ad page URL
2. Click "Begin Experiment"
3. Progress through consent and experiment pages
4. Form inputs can be filled and buttons clicked automatically

This is useful for automated testing of experiment flows.

## Database access

PsyNet uses PostgreSQL. Connect using:

```bash
psql -h localhost -U dallinger -d dallinger
```

Cursor: this needs `required_permissions: ["network"]`.

Key tables:

- `participant` - Experiment participants (id, worker_id, status, creation_time)
- `response` - Participant responses/answers
- `node` - Network nodes
- `network` - Experiment networks
- `info` - Information objects
- `experiment` - Experiment metadata
- `experiment_status` - Current experiment status

Example queries:

```sql
-- List recent participants
SELECT id, worker_id, status, creation_time FROM participant ORDER BY creation_time DESC LIMIT 5;

-- View participant responses
SELECT id, answer FROM response ORDER BY id DESC LIMIT 10;

-- List all tables
\dt
```

## Further information

If in the PsyNet repository, find further documentation in `docs`.
If in an experiment directory, find more information at https://psynetdev.gitlab.io/PsyNet/.
