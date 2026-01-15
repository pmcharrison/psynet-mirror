# Agent instructions for PsyNet

## Virtual environment

The project uses a Python virtual environment located at `.venv/`. Activate it before running any commands:

```bash
source .venv/bin/activate
```

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

This will:
- Start a Flask development server at http://127.0.0.1:5000
- Open the experiment dashboard at http://127.0.0.1:5000/dashboard
- Open a participant ad page at http://127.0.0.1:5000/ad?generate_tokens=true&recruiter=hotair

Dashboard credentials:
- Username: `admin`
- Password: `helmholtz440`

### Shell permissions

When running `psynet debug local` via the Shell tool, use `required_permissions: ["all"]` to disable sandboxing. The command needs to write to temp directories outside the workspace.

Run as a background command and wait approximately 7.5 seconds for the server to start before interacting with it via browser automation.

## Database access

PsyNet uses PostgreSQL. Connect using:

```bash
psql -h localhost -U dallinger -d dallinger
```

When connecting via the Shell tool, use `required_permissions: ["network"]` to allow database connections.

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

## Browser automation testing

Cursor's browser extension can be used to interact with experiments programmatically:
1. Navigate to the ad page URL
2. Click "Begin Experiment"
3. Progress through consent and experiment pages
4. Form inputs can be filled and buttons clicked automatically

This is useful for automated testing of experiment flows.
