# Agent instructions

Start by following `psynet/resources/experiment_scripts/AGENTS.md`.

Then act on the following PsyNet developer instructions:

## Dallinger repo

### Summary

When developing PsyNet, keep a local checkout of Dallinger at `~/Dallinger`.
If a change is needed in Dallinger, make it there and submit a PR .

### Dallinger repo instructions

Cloud Agents push to a Dallinger fork at `DALLINGER_FORK_URL` using the PAT `DALLINGER_GH_TOKEN`.
If these environment variables are not present, tell the user to follow these user instructions:

#### User instructions

1. Create a fine-grained GitHub PAT via the GitHub website.
   - Scope it to the agent's fork of Dallinger only, with the following permissions:
      - Contents: Read and write
      - Pull requests: Read and write
   - Set an expiry of 1 year or less (required for interacting with Dallinger organization).
2. Save this token as a Cloud Agent secret named `DALLINGER_GH_TOKEN` via the Cursor website.
3. Create a Dallinger fork on the GitHub website (e.g., `https://github.com/<your-username>/Dallinger`).
4. Save the fork URL as a Cloud Agent secret named `DALLINGER_FORK_URL` via the Cursor website.

#### Cloud Agent instructions

Clone the fork at `DALLINGER_FORK_URL` to `~/Dallinger`.
If `~/Dallinger` already exists, remove it or reuse that checkout.

Authenticate GitHub CLI + git using the token (avoid printing the token):

- `printf "%s" "$DALLINGER_GH_TOKEN" | gh auth login --hostname github.com --git-protocol https --with-token`
- `gh auth setup-git`

Add the upstream remote:

- `cd ~/Dallinger`
- `git remote add upstream https://github.com/Dallinger/Dallinger.git`

Make sure it is up-to-date:

- `git fetch upstream master`
- `git merge upstream/master`

Create a feature branch:

- `git checkout -b <branch-name>`

Install it in editable mode: `uv pip install -e ~/Dallinger`.
If this fails with `pg_config executable not found`, install PostgreSQL
development headers (e.g. `libpq-dev`) and retry.

Make changes and commit locally.

Push: `git push -u origin <branch-name>`

Open a PR to upstream: `gh pr create --base master --head <your-username>:<branch-name>`

If your PsyNet PR depends on this new unmerged change to Dallinger,
specify your fork in `pyproject.toml` (use a literal URL; environment
variables are not expanded in `pyproject.toml`):

```toml
# In [project].dependencies
"dallinger[docker] @ git+https://github.com/<your-username>/Dallinger.git@<branch-name>",
```

Use the GitHub CLI to find and read Dallinger job logs.
Use the token `DALLINGER_GH_TOKEN` for all these commands (either via
`gh auth login --with-token` above or by setting `GH_TOKEN` in the command).

1. List recent runs:
   - `gh run list --repo "$DALLINGER_FORK_URL" --limit 10`
2. View logs for a specific run:
   - `gh run view <run-id> --repo "$DALLINGER_FORK_URL" --log-failed`
3. If the run is against upstream, use the canonical repo:
   - `gh run list --repo https://github.com/Dallinger/Dallinger --limit 10`
   - `gh run view <run-id> --repo https://github.com/Dallinger/Dallinger --log-failed`

Local agents use a similar approach, but `~/Dallinger` should be created already by the user,
and it may be a clone of the original repository, not a fork.

## CI status checks (GitLab)

When you need to check CI status for PsyNet, use the GitLab API with the
`GITLAB_TOKEN` environment variable (project access token). This token should
be provided automatically if you are working with the team's Cursor Cloud Agent
setup. If not, tell the user to create a token via
https://gitlab.com/PsyNetDev/PsyNet/-/settings/access_tokens
and add it as a secret in the Cloud Agent dashboard
(https://cursor.com/dashboard?tab=cloud-agents)

Fetch the latest pipeline with:

```
GET https://gitlab.com/api/v4/projects/PsyNetDev%2FPsyNet/pipelines?per_page=1
```

Then list jobs for that pipeline and, if needed, fetch job logs via the trace
endpoint:

```
GET https://gitlab.com/api/v4/projects/<project_id>/pipelines/<pipeline_id>/jobs
GET https://gitlab.com/api/v4/projects/<project_id>/jobs/<job_id>/trace
```

This is the preferred approach for agents when verifying CI status or logs.

## Finishing up changes

When you make changes to the PsyNet codebase:

1. **Update the CHANGELOG**: Pull requests should include corresponding changes to `CHANGELOG.md` in the "Unreleased" section. Format: `- Description (author: [Name])` where `[Name]` is the person who invoked the agent (typically found in user context or Slack messages). These should summarize the overall changes made by the PR rather than the incremental process of building the PR.

2. **Run pre-commit**: Before committing, run pre-commit to ensure code formatting is correct:

   ```bash
   export PATH="/home/ubuntu/.local/bin:$PATH"
   pre-commit run --all-files
   ```

   If pre-commit is not installed, install it first with `pip3 install pre-commit`.

3. **Commit and push**: Commit all changes including CHANGELOG updates and any pre-commit formatting fixes.
