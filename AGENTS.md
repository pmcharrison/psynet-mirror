# Agent instructions

Read and follow `psynet/resources/experiment_scripts/AGENTS.md`.

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

1. **Update the CHANGELOG**: Add an entry to `CHANGELOG.md` under the appropriate section (Added, Changed, Fixed, etc.) in the "Unreleased" section. Format: `- Description (author: Cursor, reviewer: [Name])` where `[Name]` is the person who invoked the agent (typically found in user context or Slack messages).

2. **Run pre-commit**: Before committing, run pre-commit to ensure code formatting is correct:
   ```bash
   export PATH="/home/ubuntu/.local/bin:$PATH"
   pre-commit run --all-files
   ```
   If pre-commit is not installed, install it first with `pip3 install pre-commit`.

3. **Commit and push**: Commit all changes including CHANGELOG updates and any pre-commit formatting fixes.
