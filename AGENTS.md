# Agent instructions

Start by following `psynet/resources/experiment_scripts/AGENTS.md`.

Then act on the following PsyNet developer instructions:

## Sandbox reminder

When running PsyNet commands from Cursor, disable sandboxing by setting
`required_permissions: ["all"]` on the shell command.

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
<https://gitlab.com/PsyNetDev/PsyNet/-/settings/access_tokens>
and add it as a secret in the Cloud Agent dashboard
(<https://cursor.com/dashboard?tab=cloud-agents>)

Fetch the latest pipeline with:

```http
GET https://gitlab.com/api/v4/projects/PsyNetDev%2FPsyNet/pipelines?per_page=1
```

Then list jobs for that pipeline and, if needed, fetch job logs via the trace
endpoint:

```http
GET https://gitlab.com/api/v4/projects/<project_id>/pipelines/<pipeline_id>/jobs
GET https://gitlab.com/api/v4/projects/<project_id>/jobs/<job_id>/trace
```

This is the preferred approach for agents when verifying CI status or logs.

## Playwright flakiness guardrails

When adding or updating Playwright E2E tests, follow these rules to reduce CI flakiness:

1. **Prefer stable signals over transient text**:
   - Avoid asserting countdown text or short-lived status labels (e.g. `3`, `2`, `1`, `Uploading...`).
   - Prefer durable prompts, control visibility/enabled state, URL changes, or trial events.

2. **Avoid overly strict DOM shape assumptions**:
   - Do not rely on exact element counts/styles unless they are guaranteed by the experiment contract.
   - Prefer `at least one`, role-based selectors, IDs, and semantic assertions.

3. **Use event evidence in stable ways**:
   - Avoid live polling of `psynet.trial.eventLog` with strict timing windows in E2E tests; this is prone to CI timing variance.
   - Prefer durable submit-time evidence: assert successful `POST /response` increments after key actions.
   - If event assertions are needed, read them from submitted `metadata.event_log` payloads at submit boundaries and check coarse presence/order only.

4. **Treat auto-advance pages as optional checkpoints**:
   - If a page can auto-advance quickly, verify it only if present.
   - If already advanced, continue by advancing to the next stable prompt instead of failing.

5. **Do not use force-click unless strictly necessary**:
   - Use normal `click()` with visibility/enabled checks first.
   - Use forced clicks only for known framework overlays or non-actionability edge cases.

6. **Keep media assertions resilient**:
   - For playback, detect either active PsyNet sounds or real DOM media playback.
   - For staged blobs, assert strongly only when lifecycle guarantees availability; otherwise use best-effort checks and rely on downstream UI/event evidence.

7. **Centralize shared navigation logic in harness helpers**:
   - Reuse `psynetHarness` helpers for gateway-page clearing, next-button waits, and prompt advancement.
   - Add new shared helpers when a robust pattern appears in multiple specs.

8. **When fixing flakes, update both test comments and docs**:
   - Keep per-test section comments aligned with what is actually asserted.
   - Document new anti-flakiness patterns in dev docs/AGENTS when they become standard practice.

9. **Prefer deterministic step-by-step flows when the timeline is fixed**:
   - If experiment steps are known in advance, encode the exact sequence of expected prompts/actions.
   - Avoid heuristic navigation (`try-next`, broad fallback selectors, generic loops) for deterministic demos.
   - Treat mismatches as test failures, not as recoverable branches.

10. **Separate page-type handling explicitly**:
    - Gateway/ad pages, consent pages, and timeline pages have different DOM/state behavior.
    - Use page-specific assertions/selectors for each type; do not assume timeline containers (e.g. `#main-body`) exist everywhere.

11. **Use fail-fast synchronization tied to the expected transition**:
    - After each action, wait for the exact intended effect (expected text, expected control state, expected URL/page transition).
    - Prefer short bounded waits on deterministic invariants over long generic polls.

12. **Assert playback/recording via the actual implementation path**:
    - For `AudioPrompt`, verify PsyNet sound-state/event transitions instead of DOM `<audio>` elements.
    - For `VideoPrompt`, verify `video#prompt` playback behavior.
    - Align assertions with how that step is implemented in experiment/template code.

## Branch review command

When reviewing the current PsyNet branch against `master`, prefer the repo-local
Cursor command `/review`.

- `/review` is defined in `.cursor/commands/review.md`
- its detailed workflow lives in `.cursor/skills/branch-review/SKILL.md`

## Testing

Non-trivial code changes should be tested.
Prefer red/green test-driven development, but avoid committing overly verbose tests in the final PR.
Implement sensible unit tests where appropriate.
Verify changes end-to-end by running `psynet test local` within a relevant demo.

## Finishing up changes

When you make changes to the PsyNet codebase:

1. **Add a changelog fragment**: Pull requests should include one or more fragment files in `changelog.d/` instead of editing `CHANGELOG.md` directly. Use the filename format `changelog.d/<MR>.<category>.md` where `<category>` is one of `breaking`, `added`, `changed`, `deprecated`, `removed`, `fixed`, `updated`, or `documentation`. The fragment content should be a single changelog entry in markdown without a leading `-`, for example: `Added support for X (author: [Name])`. These entries should summarize the overall user-facing changes made by the PR rather than the incremental process of building it. Regenerate `CHANGELOG.md` with `python docs/scripts/build_changelog.py`. To cut a release, run `python docs/scripts/build_changelog.py --release <version> <date>`.

2. **Run pre-commit**: Before committing, run pre-commit to ensure code formatting is correct:

   ```bash
   export PATH="/home/ubuntu/.local/bin:$PATH"
   pre-commit run --all-files
   ```

   If pre-commit is not installed, install it first with `pip3 install pre-commit`.

3. **Commit and push**: Commit all changes including changelog fragments and any pre-commit formatting fixes.
