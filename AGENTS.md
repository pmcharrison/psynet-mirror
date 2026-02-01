# Agent instructions

Read and follow `psynet/resources/experiment_scripts/AGENTS.md`.

## Finishing up changes

When you make changes to the PsyNet codebase:

0. **Root layout changes**: If you add new files or directories at the repository root, update `.gitlab-ci.yml` change allow-lists so CI triggers remain accurate.

1. **Update the CHANGELOG**: Add an entry to `CHANGELOG.md` under the appropriate section (Added, Changed, Fixed, etc.) in the "Unreleased" section. Format: `- Description (author: Cursor, reviewer: [Name])` where `[Name]` is the person who invoked the agent (typically found in user context or Slack messages).

2. **Run pre-commit**: Before committing, run pre-commit to ensure code formatting is correct:
   ```bash
   export PATH="/home/ubuntu/.local/bin:$PATH"
   pre-commit run --all-files
   ```
   If pre-commit is not installed, install it first with `pip3 install pre-commit`.

3. **Commit and push**: Commit all changes including CHANGELOG updates and any pre-commit formatting fixes.
