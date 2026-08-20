---
name: create-skill
description: Create or update PsyNet Agent Skills from lessons, evaluations, or workflow improvements. Use when asked to add, revise, split, dedupe, or rewrite a skill; when fixing overlap or progressive-disclosure problems; or when turning a reusable lesson into durable agent guidance.
---

# Create or update a skill

Turn reusable lessons into durable Agent Skills. The user may describe the lesson
in prose; you decide ownership, structure, and where detail lives.

## Frontmatter vs body

**Put routing in frontmatter, procedure in the body.**

| Field | Purpose | Loaded when |
| --- | --- | --- |
| `description` | **When to use** — triggers, task phrases, scope hints | Skill discovery (often **without** opening `SKILL.md`) |
| `name` | Stable skill id; must match folder name | Discovery + validation |
| `compatibility` | Optional environment requirements (≤500 chars) | Discovery when present |

The YAML `description` is the primary **when-to-use** signal. Do **not** open the
body with a duplicate paragraph such as “Use this skill when…”. After the title,
start with **scope**, **prerequisites**, or **workflow**.

Good `description` example:

```yaml
description: Record PsyNet participant-flow evidence with Playwright and ffmpeg. Use when collecting participant.mp4, screenshot manifests, or audit video artifacts for an experiment.
```

Use `compatibility` when setup is non-obvious:

```yaml
compatibility: Requires editable PsyNet at ~/PsyNet, PostgreSQL, Redis, and ffprobe on PATH.
```

Skills do **not** carry `authors` metadata. Skill history is tracked in git.

## Folder and `name` conventions

Folder name **is** the skill `name`. Use kebab-case ASCII (`a-z`, `0-9`, hyphens).

- Prefer **verb-object** for workflows: `prepare-for-cint`, `record-participant-video`,
  `develop-experiment-front-end`.
- Topic skills may use a noun phrase: `psychophysics`, `basic-data`.
- **Do not** prefix experiment skills with `psynet-`. They already live under
  `.cursor/skills/experiment/` (copied to `.cursor/skills/psynet/` in experiments).
  Keep `psynet` in a name only when it is part of the object
  (`explore-psynet-repository`).
- Workshop skills in PsyNetSkills live under `.agents/skills/` and follow the
  same kebab-case / verb-object rules.

The PsyNetSkills workshop repository owns `.agents/skills/` (with compatibility
symlinks at `.claude/skills`, `.cursor/skills`, and `.github/skills`). Do not
copy experiment skills into PsyNetSkills.

## Progressive disclosure

Skills have four layers. **Do not collapse them into one long `SKILL.md`.**

1. **Routing** — frontmatter `description` (and optional `compatibility`).
2. **Procedure skeleton** — `SKILL.md`: numbered steps that say *what* to do and
   *which file/skill to open*; keep steps to one or two lines each.
3. **Operational detail** — `references/`: commands, field lists, platform notes,
   long checklists, code patterns, troubleshooting.
4. **Automation & templates** — `scripts/` (runnable helpers), `assets/`
   (copy/show templates, CSV/JSON examples, verbatim user scripts).

`SKILL.md` should read like a **table of contents**, not a manual.

### Size guidance

| Skill type | Aim for | Split when |
| --- | --- | --- |
| **Owner** | ≤100 lines | a section exceeds ~40 lines or the file exceeds ~150 lines |
| **Combination / hub** | ≤150 lines | a section exceeds ~40 lines or the file exceeds ~200 lines |

Additional rules:

- Move sections **>~40 lines** to `references/` with **when to read it** pointers.
- Put verbatim user-facing scripts in `assets/`, not inline in `SKILL.md`.
- Put code samples **>~15 lines** in `references/` or `scripts/`.
- No **“Misc.”** sections — use **Rules & gotchas** or reference files.
- Warn when `SKILL.md` exceeds **250 lines** (see Validation).

The [Agent Skills spec](https://agentskills.io/specification) allows up to ~500
lines; our budget is tighter because many skills may load in one session.

### Required `SKILL.md` sections

Use these headings in order (omit only when truly empty):

1. **Scope & boundaries** — what this skill owns; named skills/files to use instead.
2. **Prerequisites** — short, **conditional** pointers (`Read X when Y`); cap at ~5.
3. **Workflow** — numbered steps; pointer-heavy.
4. **Rules & gotchas** — hard constraints and environment-specific corrections.
5. **Validation** — commands/checks before handoff.

## Instruction patterns

From [Agent Skills best practices](https://agentskills.io/skill-creation/best-practices):

- **Defaults, not menus** — pick one default tool/command; mention alternatives briefly.
- **Omit what the agent already knows** — project conventions, edge cases, exact commands.
- **Templates** — short inline examples or `assets/`; long templates in `references/`.
- **Validation loops** — do the work, run validators, fix failures, repeat.

## Skill types

| Type | Role | `SKILL.md` shape |
| --- | --- | --- |
| **Owner** | Canonical home for one workflow | Thin shell + primary `references/<topic>.md` |
| **Combination** | Choreography of multiple owners | Prerequisites + domain rules only |
| **Hub** | Lifecycle across phases | Gates between phases + pointers |

Prefer **extending an owner** or a **combination router** over a new manual-sized skill.

## Ownership

| Skill kind | Canonical path |
| --- | --- |
| Experiment development | `.cursor/skills/experiment/<skill-name>/` |
| PsyNet repo meta (review, release, this skill) | `.cursor/skills/<skill-name>/` |

Experiment checkouts receive copies under `.cursor/skills/psynet/` via
`psynet scripts update`. Edit the PsyNet source tree, not generated experiment
copies.

The PsyNetSkills workshop repository owns `.agents/skills/` and adds a
workshop-specific addendum at `create-skill/SKILL.md` there. Do not copy
experiment skills into PsyNetSkills.

## Workflow

1. **Capture the lesson** — trigger, owned behavior, prerequisites, outputs,
   failure modes. Put trigger wording in `description`.
2. **Review overlap** — read existing skills in `.cursor/skills/` and
   `.cursor/skills/experiment/` (and their `references/` when cited). Classify
   each overlap: `replacement`, `extension`, `pointer`, `combination`, or `new`.
3. **Choose disposition** and tell the user every overlap found.
4. **Draft frontmatter** — `name`, `description`, optional `compatibility`.
5. **Draft `SKILL.md`** using the section template. Split early when pasting
   commands, tables, or templates.
6. **Dedupe on write** — replace duplicated text with pointers unless this skill
   is the new canonical owner.
7. **Validate** — run the validators in the Validation section.

## Rules

- Do not embed production credentials or private evaluation rubrics in skills.
- Do not make skills “self-contained” by copying other skills — use prerequisites
  and pointers.
- Future agents may see only frontmatter during routing; the body must not be
  the only place that explains when the skill applies.
- Prefer one canonical reference file per owner skill over many small duplicates.

## Validation

From the PsyNet repository root:

```bash
python scripts/validate_agent_skills.py
skills-ref validate .cursor/skills/create-skill   # example; repeat per skill or use the script
```

Install `skills-ref` (`uv pip install skills-ref`) when the CLI is not already
available. The repository script checks reference citations, line-count warnings,
and optional `skills-ref` conformance for every skill under `.cursor/skills/`.

After changing experiment skills, run `psynet scripts update` in affected
experiment checkouts so `.cursor/skills/psynet/` picks up the revision.
