# dispatch-skills

Two Claude Code skills for running a batch of related work across many agents, plus the four
skills they depend on and the checks they rely on.

| Skill | What it is |
|---|---|
| `/dispatch` | A manager holds a task graph, spawns a task agent per task, and rules on what reaches it. Each agent gets its own worktree; the manager writes no code. |
| `/evidence-dispatch` | The same shape, with every acceptance criterion an **executable probe, proven red before the work and green after**. A reviewer is replaced by a falsifier that must ship a failing command; a task whose diff touches no executable file skips review entirely. |

Both are user-invoked only (`disable-model-invocation`), so nothing starts a run on its own.

Evidence-dispatch came out of measuring a real dispatch run: 37% of ticket wall-clock went to
review and rework, and reviewers withdrew 21 of their own 25 findings. Its bet is that a probe
that can be run beats a reviewer's opinion that cannot.

## Install

```bash
cd my-project
npx github:assafcaf/dispatch-skills
# or
uvx --from git+https://github.com/assafcaf/dispatch-skills dispatch-skills
```

It installs the skills, the checks, and then **asks where your issues live** — because these
skills file work as issues and cite them in every ruling, and they cannot guess that.

```
1) Jira            — via the atlassian MCP server        [default]
2) GitHub Issues   — via the gh CLI
3) Obsidian vault  — markdown notes, one file per issue
4) something else  — writes a skeleton for you to fill in
```

Then a key prefix, and whatever that tracker needs (Jira site and cloud id; `owner/repo`,
defaulted from `gh`; the vault path). Every question has a flag, so an unattended install
answers them up front:

```bash
npx github:assafcaf/dispatch-skills --tracker github --key ENG --gh-repo acme/widgets
npx github:assafcaf/dispatch-skills --tracker obsidian --key NOTE --vault /home/me/vault
npx github:assafcaf/dispatch-skills --no-config          # skills only
```

`--dry-run` shows every action without taking one. Re-running is safe: identical files are
skipped, and **existing `docs/agents/*.md` are never overwritten** — they are yours once
written. Delete one to have it regenerated.

## What lands where

```
.claude/skills/dispatch/              SKILL.md + 5 role prompts
.claude/skills/evidence-dispatch/     SKILL.md + 4 role prompts
.claude/skills/implement/             \
.claude/skills/tdd/                    |  the four these depend on
.claude/skills/review-standards-spec/  |  (see NOTICE — Matt Pocock, MIT)
.claude/skills/resolving-merge-conflicts/ /
scripts/checks/                       run-checks.sh + 7 checks the runs enforce
scripts/jira-attach.sh                Jira only
docs/agents/dispatch.md               \  the configuration. Generated from your
docs/agents/evidence-dispatch.md       |  answers, then yours to edit — these are
docs/agents/issue-tracker.md          /   read by every agent in a run.
```

`docs/agents/*.md` is configuration, not documentation. A wrong one sends every agent in a run
down the wrong path, so read them before the first run.

## Dependencies, and why they ship with it

```
dispatch ──┬─ implement ──┬─ review-standards-spec
           │              └─ tdd
           ├─ review-standards-spec         worker-prompt.md
           └─ resolving-merge-conflicts     integrator-prompt.md

evidence-dispatch ── tdd                    planner + worker prompts
```

Those four are Matt Pocock's, MIT, and three carry a local modification — see
[NOTICE](NOTICE), which names each one and says exactly what was changed and why. Shipping
them together is deliberate: a dispatch run that reaches `implement/SKILL.md` and finds nothing
stops halfway through a task graph, having already made branches.

## Works with, but does not require

[herdr-claude-setup](https://github.com/assafcaf/herdr-claude-setup) makes delegated agents run
as visible terminal panes. Install both and a dispatch run's task agents become panes you can
watch and interrupt, instead of in-process subagents you cannot. Neither needs the other.

## Licence

MIT — see [LICENSE](LICENSE). Third-party attribution is in [NOTICE](NOTICE), with upstream's
licence at [vendor/mattpocock-skills/LICENSE](vendor/mattpocock-skills/LICENSE).
