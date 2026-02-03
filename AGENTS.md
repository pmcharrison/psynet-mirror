# Agent instructions

Read and follow `psynet/resources/experiment_scripts/AGENTS.md`.

The below instructions are specific to PsyNet developers (not just PsyNet experiment developers).

## Dallinger repo

When developing PsyNet, keep a local checkout of Dallinger at `~/Dallinger`. If a change is needed in Dallinger, make it there and submit a PR.

### Safe fork-based workflow

When operating as a Cloud Agent, we use forks for safety.
Do not push directly to the upstream Dallinger repo.

#### One-time setup (cloud agents)

1. Create a fine-grained GitHub PAT.
2. Scope it to the agent's fork of Dallinger only.
3. Permissions:
   - Contents: Read and write
   - Pull requests: Read and write
4. Export the token as `GH_TOKEN` or `GITHUB_TOKEN` in the shell. Do not store it in the repo.
5. Export the fork URL as `DALLINGER_FORK_URL` (e.g., `https://github.com/<your-username>/Dallinger`).

#### One-time setup (local)

1. Fork the upstream Dallinger repo in GitHub if you do not already have a fork.
2. Clone the fork to `~/Dallinger`:
   - `gh repo clone "$DALLINGER_FORK_URL" ~/Dallinger`
3. Add the upstream remote:
   - `cd ~/Dallinger`
   - `git remote add upstream https://github.com/Dallinger/Dallinger.git`
4. Install Dallinger in editable mode:
   - `cd ~/Dallinger`
   - `uv pip install -e .`

#### Workflow

1. Sync with upstream:
   - `git fetch upstream`
   - `git checkout master`
   - `git merge upstream/master`
2. Create a feature branch:
   - `git checkout -b <branch-name>`
3. Make changes and commit locally.
4. Push:
   - `git push -u origin <branch-name>`
5. Open a PR to upstream:
   - `gh pr create --base master --head <your-username>:<branch-name>`
6. If your PsyNet PR depends on this new unmerged change to Dallinger,
   specify your fork in `pyproject.toml`:

   ```toml
   # In [project].dependencies
   "dallinger[docker] @ git+$DALLINGER_FORK_URL.git@<branch-name>",
   ```

#### Dallinger CI logs (CLI only)

Use the GitHub CLI to find and read Dallinger job logs:

1. List recent runs:
   - `gh run list --repo "$DALLINGER_FORK_URL" --limit 10`
2. View logs for a specific run:
   - `gh run view <run-id> --repo "$DALLINGER_FORK_URL" --log-failed`
3. If the run is against upstream, use the canonical repo:
   - `gh run list --repo https://github.com/Dallinger/Dallinger --limit 10`
   - `gh run view <run-id> --repo https://github.com/Dallinger/Dallinger --log-failed`

## Finishing up changes

When you make changes to the PsyNet codebase:

1. **Update the CHANGELOG**: Add an entry to `CHANGELOG.md` under the appropriate section (Added, Changed, Fixed, etc.) in the "Unreleased" section. Format: `- Description (author: Cursor, reviewer: [Name])` where `[Name]` is the person who invoked the agent (typically found in user context or Slack messages).

2. **Run pre-commit**: Before committing, run pre-commit to ensure code formatting is correct:

   ```bash
   export PATH="/home/ubuntu/.local/bin:$PATH"
   pre-commit run --all-files
   ```

   If pre-commit is not installed, install it first with `pip3 install pre-commit`.

3. **Commit and push**: Commit all changes including CHANGELOG updates and any pre-commit formatting fixes.
