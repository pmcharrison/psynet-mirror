# PsyNet Repository Agent Instructions

This document provides guidance for AI agents working on the PsyNet repository source code.

For guidance on working with PsyNet experiments (not the source code), see `psynet/resources/experiment_scripts/AGENTS.md`.

## Overview

PsyNet is a Python framework for designing and deploying complex online psychological experiments. It builds on [Dallinger](https://dallinger.readthedocs.io/) and provides high-level abstractions for creating sophisticated experimental paradigms.

**Key technologies:**
- Python 3.10+ (recommended: 3.13)
- Flask web framework
- PostgreSQL database
- Docker for deployments
- pytest for testing
- Sphinx for documentation

## Repository Structure

```
psynet/                    # Main package source code
  ├── __init__.py
  ├── command_line.py      # CLI entry point (psynet command)
  ├── consent.py           # Consent page implementations
  ├── dashboard/           # Lucid dashboard integration
  ├── demography/          # Demographic questionnaires
  ├── end.py               # Experiment end pages
  ├── modular_page.py      # Modular page system
  ├── page.py              # Base page classes
  ├── timeline.py          # Timeline system for sequencing pages
  ├── trial/               # Trial implementations (static, chains, adaptive, etc.)
  ├── translation/         # Multi-language support
  ├── resources/           # Static assets, experiment templates
  └── templates/           # Jinja2 HTML templates

demos/                     # Example experiments
  ├── experiments/         # Full experiment examples
  └── features/            # Feature-specific demos

tests/                     # Test suite
  ├── isolated/            # Unit tests
  ├── local_only/          # Tests requiring local environment
  └── template_experiment_tests/  # Integration tests

docs/                      # Sphinx documentation
```

## Development Setup

### Virtual Environment

The project uses a Python virtual environment at `.venv/`. Always activate it before running commands:

```bash
source .venv/bin/activate
```

If `.venv/` doesn't exist, create it:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

### Installing Dependencies

For PsyNet development:

```bash
uv pip install -e '.[dev,slack]'
```

This installs PsyNet in editable mode with development and Slack dependencies.

### Required Permissions

When running PsyNet commands in Cursor, disable sandboxing: `required_permissions: ["all"]`

For database access: `required_permissions: ["network"]`

## Coding Conventions

### Docstring Format

Use **numpydoc** format for all docstrings:

```python
def my_function(param1, param2):
    """
    Short description.

    Longer description if needed.

    Parameters
    ----------
    param1 : str
        Description of param1.
    param2 : int
        Description of param2.

    Returns
    -------
    bool
        Description of return value.
    """
```

Use sentence case for titles. Don't write docstrings for simple, self-explanatory internal functions.

### Code Style

- **Black** formatting (88 character line length)
- **Type hints** for function signatures
- Follow existing patterns in the codebase
- Fix issues at the cause, not the symptom

### Pre-commit Hooks

The repository uses pre-commit hooks. Install them:

```bash
pre-commit install
```

## Testing

### Test Framework

PsyNet uses pytest with custom plugins. Tests are organized by isolation level:

- `tests/isolated/` - Unit tests that don't require external services
- `tests/local_only/` - Tests requiring local PostgreSQL/Redis
- Demo tests - Full experiment integration tests

### Running Tests

Run all tests:

```bash
pytest
```

Run specific test file:

```bash
pytest tests/isolated/translation/test_translate_experiment.py
```

Run tests matching a pattern:

```bash
pytest -k "test_translate"
```

### Test-Driven Development

For non-trivial features:
1. Write a test first
2. Implement the feature
3. Run the test to verify it passes
4. Check for linter errors and fix them

### CI Testing

The repository has CI scripts:

```bash
./run-ci-tests.sh          # Run CI test suite
./install-ci-dependencies.sh  # Install CI dependencies
```

## Running Demos Locally

Demos are in `demos/experiments/` and `demos/features/`.

To run a demo in debug mode:

```bash
cd demos/experiments/<demo_name>
psynet debug local
```

Wait 8 seconds for the server to start, then look for the ad page URL in the logs:
```
http://127.0.0.1:5000/ad?generate_tokens=true&recruiter=hotair
```

## Database Access

PsyNet uses PostgreSQL. Connect with:

```bash
psql -h localhost -U dallinger -d dallinger
```

Key tables:
- `participant` - Experiment participants
- `response` - Participant responses
- `node` - Network nodes
- `info` - Information objects
- `experiment` - Experiment metadata

Example queries:

```sql
-- List recent participants
SELECT id, worker_id, status, creation_time 
FROM participant 
ORDER BY creation_time DESC 
LIMIT 5;

-- View participant responses
SELECT id, answer 
FROM response 
ORDER BY id DESC 
LIMIT 10;
```

## Documentation

Documentation is built with Sphinx and hosted at https://psynetdev.gitlab.io/PsyNet/

Source files are in `docs/`. The documentation uses:
- **reStructuredText** (.rst files)
- **sphinx-autodoc** for API documentation
- **Furo** theme

Build documentation locally:

```bash
cd docs
make html
```

View built docs in `docs/_build/html/index.html`.

## Common Development Tasks

### Adding a New Page Type

1. Create the class in `psynet/page.py` or `psynet/modular_page.py`
2. Add docstring with numpydoc format
3. Create a demo in `demos/features/`
4. Add tests if complex
5. Update documentation

### Adding a New Trial Type

1. Create module in `psynet/trial/`
2. Implement trial class inheriting from appropriate base
3. Add comprehensive docstring
4. Create demo experiment
5. Add integration tests
6. Document in `docs/`

### Fixing Bugs

1. Reproduce the bug
2. Write a test that fails due to the bug
3. Fix the bug at its root cause
4. Verify the test passes
5. Check for linter errors
6. Update CHANGELOG.md

## Git Workflow

### Branches

- `master` - Main development branch
- Feature branches - `cursor/new-psynet-agent-1776` or similar

### Commit Messages

Keep commit messages short and descriptive. No bullet points.

Good examples:
```
Fix indentation bug in GroupBarrier.choose_who_to_release
Add AGENTS.md to help Cursor run experiments locally
Update Dallinger dependency to v12.1.0
```

### Updating CHANGELOG

For all notable changes, add an entry to `CHANGELOG.md` under the "Unreleased" section:

```markdown
## Fixed
- Fixed incorrect property name `self.job` in `WorkerAsyncProcess.cancel` that should be `self.redis_job` (author: Your Name, reviewer: Reviewer Name)
```

## Key Classes and Modules

### Core Experiment Classes

- `psynet.experiment.Experiment` - Main experiment class
- `psynet.timeline.Timeline` - Sequence of pages/trials
- `psynet.page.Page` - Base page class
- `psynet.modular_page.ModularPage` - Composable page system
- `psynet.trial.main.Trial` - Base trial class

### Trial Types

- `StaticTrial` - Fixed stimulus set
- `ChainTrial` - Sequential chains (e.g., telephone game)
- `DenseTrial` - Dense network sampling
- `GibbsTrial` - Gibbs sampling from stimulus space
- `StaircaseTrial` - Adaptive psychophysics

### Utilities

- `psynet.asset.asset()` - Load external assets (audio, video, images)
- `psynet.consent.Consent` - Consent pages
- `psynet.demography.*` - Demographic questionnaires
- `psynet.translation.*` - Multi-language support

## Version Information

- **Current version:** 13.1.0a0 (see `pyproject.toml`)
- **Python:** 3.10+ (recommended 3.13)
- **Dallinger:** 12.1.0+

## External Resources

- **Documentation:** https://psynetdev.gitlab.io/PsyNet/
- **GitLab Repository:** https://gitlab.com/PsyNetDev/PsyNet/
- **DeepWiki:** https://deepwiki.com/pmcharrison/psynet-mirror
- **Issues:** https://gitlab.com/PsyNetDev/PsyNet/-/issues

## Agent Behavior Guidelines

1. **Read before editing** - Always read files before making changes
2. **Follow existing patterns** - Match the style of surrounding code
3. **Test changes** - Run relevant tests after changes
4. **Fix linter errors** - Use ReadLints tool after substantive edits
5. **Update documentation** - Keep docstrings and docs/ in sync with code
6. **Ask when uncertain** - For large changes, clarify intent first
7. **Small commits** - Make focused, logical commits

## Distinguishing Repository vs Experiment Work

Check if `/workspace/experiment.py` exists:
- **If yes:** Working on a PsyNet experiment (follow `psynet/resources/experiment_scripts/AGENTS.md`)
- **If no:** Working on PsyNet source code (follow this file)
