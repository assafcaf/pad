# Evidence dispatch

Per-repo configuration for the `/evidence-dispatch` skill. The skill holds the process and the
reasoning; this file holds the values. Edit them here rather than in the skill.

This is the sibling of `dispatch.md`, not a replacement for it. `dispatch.md` configures the
review-based run; this file configures the evidence-based one. **Which to use** is in the
skill's opening section.

## Why this exists

Measured on the `PROJ-17` run, 2026-09-08, from its blackboard at `fcdda85^` and the 40 subagent
transcripts under that session:

| | |
|---|---|
| Wall clock, planner dispatched to last fix commit | 551 min |
| Per-ticket review and rework | 172 min — **37%** of ticket time |
| Reviewer findings raised | 25, in 12 rounds |
| Findings withdrawn in the next round | **21 of 25** |
| Lines of code and tests shipped | 2,431 |
| Lines of blackboard prose written | 5,839 — **2.4:1 against the code** |
| `PROJ-31`, an execution-only ticket | 0 lines of code, 1,039 lines of blackboard, 5 findings, all withdrawn |
| Waves whose frontier was wider than one task | **0 of 5** |

The withdrawal rate is not a malfunction. `.claude/skills/dispatch/reviewer-prompt.md:80` instructs the
reviewer not to pre-filter, `.claude/skills/dispatch/task-agent-prompt.md:53` forbids the task agent from
judging findings, and `.claude/skills/dispatch/reviewer-prompt.md:95` tells the reviewer that withdrawing is
the expected outcome. The loop produced exactly what it was specified to produce. This file
configures a different trade.

Two findings shaped the design and both are load-bearing:

- **The highest-value findings of that run came from the one gate the skill forbids.** Both
  credential exposures were caught because the manager re-ran `git log -p` and a token scan
  itself, against `.claude/skills/dispatch/SKILL.md:106`, which tells it not to read diffs. A safeguard that
  depends on an agent disobeying its prompt is luck. Here those are scripts — see **Standing
  checks**.
- **One class of defect survives every probe.** `PROJ-29`'s publisher built its path from the
  *task* name where upstream writes the *environment* name. Every test passed; the code was
  correct by coincidence, and a differently-named environment would have silently produced an
  empty dataset. It was found by reading. That is what the `judgment` track's single reading
  pass exists for, and why this skill is not "delete review".

## Vocabulary

Inherited from `dispatch.md` — **run**, **task**, **wave** — with three additions.

| Term | Is |
|---|---|
| probe | one executable check of one acceptance criterion. Exit 0 is met, non-zero is not |
| ledger | `evidence/<run-id>/ledger.jsonl` — append-only, one line per probe run |
| track | how much scrutiny one task gets, chosen from the task's own shape |

## Tracks

**The track is the dynamic part of this process.** It is chosen per task, not per run, and it
decides which agents run at all. A run mixes tracks freely.

| Track | The task | Pipeline |
|---|---|---|
| `execution` | ships no executable code — it runs something and records what happened | worker → ledger → standing checks. **No falsifier. No reading pass. No review of any kind.** |
| `mechanical` | ships code whose every criterion is machine-checkable — an image that builds, a service that answers, a file that parses | TDD worker → standing checks → falsifier |
| `judgment` | ships code that can be *silently* wrong — anything that selects, publishes, resolves a path, retries, or decides what to skip | TDD worker → standing checks → falsifier → silent-failure audit |

**The planner proposes the track** in `plan.md` with one sentence of rationale, in the same
shape as the complexity line. Then two rules override it, and both are mechanical:

1. **The diff demotes.** If a task's diff touches no file under `service/`, `scripts/`,
   `docker/` or `config/`, its track collapses to `execution` regardless of what the plan said.
   Run `scripts/checks/track-floor.sh <base> <head>` — it prints the floor.
2. **The task agent may upgrade, never downgrade.** A task that turns out to touch behaviour
   moves up a track and records why in one line. Downgrading is the manager's, on an escalation.

`PROJ-31` — a 40-episode collection run that produced zero lines of code — is the case rule 1
exists for. It received a full review cycle and returned five findings, all withdrawn.

## Knobs

| Knob | Value | What it controls |
|---|---|---|
| `max_tasks_per_wave` | **5** | Ceiling on concurrent task agents |
| `serial_below` | **2** | **If the frontier is one task wide, run serially**: no worktree, no integrator, no drift check. The task agent commits straight to the run branch |
| `falsifier_rounds` | **1** | The falsifier runs once. It ships reproductions, and a reproduction needs no round two |
| `worker_escalations` | **1** | Times a task agent may replace its worker with a fresh one a tier up |
| `ruling_rounds` | **1** | Rounds a task agent gets to apply a manager's ruling before returning `blocked` |

`serial_below` is the knob that was missing from `dispatch.md`. On `PROJ-17` the frontier was one
task wide in all five waves — one GPU box, and a dependency chain that makes the tasks serial by
physics — and the run still paid for five worktrees, six integrators and four drift checks.

## Models

Unchanged in principle from `dispatch.md`: the planner assesses, the manager decides, and
**every dispatch names a model** — an omitted one inherits the caller's, the most expensive on
the board.

| Role | Typical | Why |
|---|---|---|
| Deep planner | `opus` | Runs once. It writes the probes, and every task inherits them |
| Task agent | `sonnet` | Orchestrates and judges; writes no code. Omitted entirely when `serial_below` applies and the task is `execution` |
| Implementation worker | per `plan.md` | The one genuinely variable seat |
| Falsifier | `sonnet` | Runs commands. It needs tool fluency, not depth |
| Silent-failure audit | `opus` | One narrow question over the whole run branch, once |
| Integrator | `sonnet` | Only dispatched when a wave merged more than one task |

## The probe

One probe per acceptance criterion. It lives at `gates/<task-id>/<n>-<slug>.sh`, is executable,
takes no arguments, prints what it checked, and exits 0 or non-zero. It is committed with the
task.

A probe is **not** a unit test. Unit tests live in `tests/` and run under the suite; a probe is
the thing that answers "is criterion 3 met on this machine, right now" — it may build an image,
curl a service, count files on disk, or shell into the running stack.

**Every probe must be shown to discriminate.** The ledger requires a run of the probe at the
task's base commit with a non-zero exit, and a run at its head commit with exit 0. A probe with
no red run is not evidence, and `scripts/checks/verify-ledger.py` fails the task.

This is the same event as TDD's red step. The worker is not doing two things.

## The ledger

`evidence/<run-id>/ledger.jsonl`, committed on the run branch, append-only, one JSON object per
line. **Unlike the blackboard, it is not deleted at the end of the run** — it is the run's
manifest, and `CLAUDE.md` says this phase keeps everything.

    {"ts":"2026-09-09T14:02:11Z","run":"PROJ-40","task":"PROJ-41","claim":"3",
     "probe":"gates/PROJ-41/3-policy-answers.sh","commit":"a1b2c3d","base":"9f8e7d6",
     "phase":"green","exit":0,"host":"build-host-01","stdout_sha256":"...",
     "stdout_path":"evidence/PROJ-40/PROJ-41/3-green.log"}

| Field | Is |
|---|---|
| `claim` | the acceptance criterion's number in `plan.md`, or `suite` / `check:<name>` |
| `phase` | `red` (at base, expected non-zero) or `green` (at head, expected 0) |
| `host` | `hostname` where it ran. `CLAUDE.md`: every execution is on the box |
| `stdout_path` | the captured output, committed alongside. Never truncated in the file |

Append with `scripts/checks/ledger-append.sh` rather than by hand — it computes the hashes and
refuses a line whose `stdout_path` does not exist.

## Standing checks

The mechanical replacement for the recurring findings of `PROJ-17`. `scripts/checks/run-checks.sh`
runs all of them and is part of the integration gate.

| Check | Replaces | Script |
|---|---|---|
| Secret scan over the commit range and the tree | the manager's two hand-run `git log -p` sweeps | `no-secrets.sh` |
| Every committed script is mode `100755` | final-review finding 6 — three documented commands failed on a fresh clone | `exec-bits.sh` |
| Every `path:line` citation in committed Markdown resolves | final-review finding 1, Critical — eight durable files cited a directory the next commit deleted | `citations.py` |
| Every probe has a red run and a green run | final-review finding 4 — a test that could not fail for the flag it guarded | `verify-ledger.py` |
| `STATE.md` moved, or the commit says why | `CLAUDE.md`'s standing requirement | `state-moved.sh` |

A check that finds something is not a review finding. It is a failed gate: the task does not
merge, and there is nothing to rebut.

## The integration gate

Run on the run branch after every merge, and before any hand-over:

    timeout 420 uv run pytest -q -rs && scripts/checks/run-checks.sh <base> <head>

The `pytest` half needs `pyproject.toml` and `uv.lock`; where they are absent the gate has
nothing to run and the integrator records a ruling saying so. **A gate you did not run is never
a gate that passed.**

### Running it on the GPU box

Every execution in this repo happens on the box, per `CLAUDE.md`. `remote-dev` is the authority
on reaching it. Two things specific to a run branch, unchanged from `dispatch.md`:

- **Push a refspec, not `HEAD`** — the box's checkout stays on `develop`:

      git push box "evidence/<run-id>:refs/heads/evidence/<run-id>"

- **Gate in a worktree of its own on the box**, `~/dispatch/<run-id>`, created once and reused,
  reset hard to the pushed ref before each gate.

## Branches and paths

| Knob | Value |
|---|---|
| Run branch | `evidence/<run-id>` |
| Task branch | `<run-id>/<task-id>` — only when the wave is wider than `serial_below` |
| Worktree root | `.claude/worktrees/` — gitignored, per `CLAUDE.md` |
| Probes | `gates/<task-id>/` — committed, permanent |
| Ledger and logs | `evidence/<run-id>/` — committed, **permanent** |
| Task notes | `docs/dispatch/<run-id>/tasks/<task-id>/established.md` — committed, removed in the final commit |
| Report | `dispatch-report.md` in the manager's worktree root, uncommitted |

**Three files per task, and only three.** `report.md`, `review.md` and `verdict.md` do not
exist in this process: the ledger carries what `report.md` carried, the falsifier's
reproductions carry what `review.md` carried, and the task agent's return line carries the
verdict. On `PROJ-17` those three files were 5,748 of the blackboard's 7,939 lines.

`established.md` survives because it is the only blackboard file with a real downstream
consumer — the next task's worker reads it, and an interface left out of it is one the next
agent invents differently.

## Mechanics that have cost a run

Inherited whole from `dispatch.md:mechanics`, because the host has not changed:

- **The manager stays where it was invoked.** A manager pinned inside a worktree pins every
  agent it spawns to the same one.
- **Every dispatched agent calls `EnterWorktree` with its own path as its first tool call**,
  with a `cd`-prefix fallback.
- **Heredocs mangle backticks on this host.** Prose full of code spans goes through the Write
  and Edit tools. This applies to probe scripts too — write them with Write, not `cat <<EOF`.
- **Finished worktrees get removed, branches kept.**

## Jira

Project `PROJ`, through the `atlassian` MCP server, per `issue-tracker.md`. Cloud ID
`<your-cloud-id>`.

### The planner writes the test list into the ticket

After `plan.md` is written, the planner appends one block to each task's ticket description,
using `editJiraIssue`. **Append-only, under a stable marker.** It never rewrites a human's
text; on a re-plan it replaces only the block between its own markers.

    <!-- evidence-dispatch:tests:start -->
    ## Tests this task must produce

    Conceptual. The worker turns each into a real test at the named seam, red first.

    | # | Seam | Behaviour under test | Why it can fail today |
    |---|---|---|---|
    | 1 | `service/logging/publisher.py` | publishes nothing when the task dir is absent, and says so | nothing raises; the run reports a URI for an empty dataset |

    ## Probes this task must pass

    | Criterion | Probe | Green means |
    |---|---|---|
    | 3 | `gates/PROJ-41/3-policy-answers.sh` | `/healthz` returns 200 with the model id in the body |
    <!-- evidence-dispatch:tests:end -->

This is what makes the run's TDD honest. `.claude/skills/tdd/SKILL.md` requires seams to be
agreed before a test is written; in an autonomous run there is no user to agree with, so the
ticket is where the agreement lives. A worker that invents its own seams is doing bulk testing
under a TDD name.

### The task agent posts evidence

One comment per task, at hand-over, before the transition to `In Review`. Format is fixed so a
human can scan five of them without reading prose:

    **PROJ-41 — evidence** · track `mechanical` · commit `a1b2c3d` · host `build-host-01`

    | # | Criterion | Probe | Result |
    |---|---|---|---|
    | 1 | the image builds headless | `gates/PROJ-41/1-builds.sh` | ✅ exit 0 · 2026-09-09T14:02Z |
    | 2 | ... | ... | ❌ **not met** — see below |

    **Suite** — `uv run pytest -q` → 183 passed, 3 skipped
    **Red-then-green** — every probe above ran non-zero at `9f8e7d6` and zero at `a1b2c3d`
    **Standing checks** — secrets ✅ · exec-bits ✅ · citations ✅ · ledger ✅ · STATE ✅
    **Artifacts** — 2 attached: `1-builds.log`, `episode-000-frame.png`
    **Not verified** — one line each, or "nothing"

    Ledger: `evidence/PROJ-40/ledger.jsonl`, lines 14-31.

**Every claim in that comment is a ledger line.** The task agent copies from the ledger; it does
not describe what it believes happened.

### Attachments

The `atlassian` MCP server has **no attachment tool** — `fetch` is read-only by ARI, and
`addCommentToJiraIssue` takes only a body. Images and logs therefore go up over the REST API:

    scripts/jira-attach.sh PROJ-41 evidence/PROJ-40/PROJ-41/1-builds.log ...

It needs `JIRA_EMAIL` and `JIRA_API_TOKEN` in the environment (token from
<https://id.atlassian.com/manage-profile/security/api-tokens>). **When they are absent it exits
2 and prints so**, and the task agent falls back: the comment names each artifact's committed
path and its sha256, and says plainly that attachment was unavailable. It does not claim an
attachment it did not make.

Attach, at most: one log per failed probe, and any image the criteria actually asked for — a
rendered frame, a plot, a screenshot. A green probe's log is in the repo; attaching it too is
noise.

### Transitions

| When | To |
|---|---|
| The task agent starts work | `In Progress` |
| The task agent has posted its evidence comment | `In Review` |

**`Done` is the operator's alone.** No agent sets it, and a run finishes with its tasks in
`In Review`.
