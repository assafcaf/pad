# Merge strategy format

A strategy is a pair of files in `.claude/workflow/merge-strategies/`:
`<name>.md` (what it is and when to use it) and `<name>.sh` (what it does).
`merge-strategies.sh validate` checks them; `merge-strategies.sh rehearse <name>` runs them on a
scratch repo. PAD ships `single` and `batch`; a repo adds its own, and `/pad-update` never
touches a file PAD did not ship. `dynamic` is reserved: it is a setting that lets the
orchestrator choose among the strategies, not a strategy.

## The .md file

Frontmatter between two `---` lines, then a body.

| Field | Required | Is |
|---|---|---|
| `name` | yes | the strategy's name; unique; not `dynamic` |
| `script` | yes | the script's file name, beside the `.md` |
| `description` | yes | one line |
| `options` | no | comma-separated `<opt>=<default>`; the only options a config or run line may set |

The body is the "when to use" text. `dynamic` reads it, with the signals the orchestrator
sees, to choose the strategy before each pass. Write it in those terms: the lines of
`merge.sh --status` (`QUEUE <n>`, `DRAIN running|idle`,
`LAST <strategy> merged=<n> rejected=<n> conflict=<n> gates=<n>`) and the result lines
(`MERGED`, `REJECTED`, `CONFLICT`, `ERROR`). Say when to use it and when to leave it.

## The .sh script

Called once per pass, under the drain's merge lock.

- **stdin:** the pass's queue, one `<KEY> <TASK_HEAD> <RED>` per line.
- **environment:** `PAD_RUN`, `PAD_EPIC_WORKTREE`, `PAD_EPIC_BRANCH`, `PAD_BIN` (the
  `.claude/workflow/bin` folder), `PAD_MERGE_LOCK_HELD`, and `PAD_OPT_<NAME>` for each declared
  option (upper-cased, declared default applied).
- **stdout:** one line per queued ticket: `MERGED <KEY> <sha>`, `REJECTED <KEY>: <why>`,
  `CONFLICT <KEY>: <paths>`, `ERROR <KEY>: <why>`, or `REQUEUE <KEY>` (back to the queue for the
  next pass).
- **may call only** the building blocks below and plain shell.

The engine checks after the pass that every ticket has one result, and that each new commit on
the epic branch is a merge it reported. Anything else is `ERROR` and exit 2.

## Building blocks

| Block | Call | Prints |
|---|---|---|
| `merge-candidate.sh` | `--run <id> <KEY>...` | `CANDIDATE <path>`, `PREFIX <KEY> <commit> <tree>`, `CONFLICT <KEY>: <paths>`, `REJECTED <KEY>: <why>` |
| `merge-candidate.sh` | `--remove <path>` | nothing; removes the throwaway worktree |
| `merge-gate.sh` | `--candidate <path> [--at <commit>] [--gate full\|lint\|<command>]` | output tail, then `GATE PASS` or `GATE FAIL` |
| `merge-task.sh` | as for a single ticket, plus `--expect-tree <tree>` | `MERGED`, `REJECTED`, `CONFLICT` as today |

`merge-task.sh` is the only way a ticket lands. It runs the submission, ownership,
protected-path and test-removal checks and the bookkeeping; `--expect-tree` replaces its gate
with a check that the merged tree equals the one a candidate already gated. A candidate is a
throwaway worktree at the epic head: build one, gate it, always remove it (use `trap`).

## Worked example: `gated-by-command`

Merges every queued ticket as one group, gated by a command the operator names, and on red
rejects the whole group's first conflicting or failing ticket by trying them one at a time.

`gated-by-command.md`:

```markdown
---
name: gated-by-command
description: Gate each pass's group once with a command named in the options, falling back to one ticket at a time on red.
script: gated-by-command.sh
options: gate=lint, max=4
---
Use when `QUEUE` is 2 or more and the repo has a fast command that catches most breaks
(`gate=` names it: `full`, `lint`, or a command). Use after a pass whose `LAST` line shows
`rejected=0`. Leave it for `single` after two passes in a row with `rejected` above 0: the
group is not paying for itself.
```

`gated-by-command.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
bin="$PAD_BIN"; gate="${PAD_OPT_GATE:-lint}"; max="${PAD_OPT_MAX:-4}"

mapfile -t queue < <(cat)                       # "<KEY> <TASK_HEAD> <RED>" lines
group=("${queue[@]:0:$max}"); rest=("${queue[@]:$max}")
keys=(); for l in "${group[@]}"; do keys+=("${l%% *}"); done

out="$(bash "$bin/merge-candidate.sh" --run "$PAD_RUN" "${keys[@]}")"
cand="$(sed -n 's/^CANDIDATE //p' <<<"$out")"
trap 'bash "$bin/merge-candidate.sh" --remove "$cand"' EXIT
grep -E '^(CONFLICT|REJECTED) ' <<<"$out"        # report them as the ticket's result

# One gate of the group's last commit, with the command from the option.
last="$(awk '/^PREFIX /{c=$3} END{print c}' <<<"$out")"
if bash "$bin/merge-gate.sh" --candidate "$cand" --at "$last" --gate "$gate" | tail -1 | grep -q 'GATE PASS'; then
  while read -r _ key commit tree; do
    bash "$bin/merge-task.sh" --run "$PAD_RUN" "$key" --expect-tree "$tree"   # prints MERGED/REJECTED
  done < <(grep '^PREFIX ' <<<"$out")
else
  for k in "${keys[@]}"; do echo "REQUEUE $k"; done  # the next pass runs under `single`
fi
for l in "${rest[@]}"; do echo "REQUEUE ${l%% *}"; done
```

Each `merge-task.sh` call is shown short; the shipped `batch.sh` carries the full argument list
(the ticket's heads, title and commands) and is the better model for a real strategy. Everything
the example runs is a building block, a ticket lands only through `merge-task.sh`, the gate
command is the option `gate`, and the epic's final gate is untouched.

## Check before you finish

- `merge-strategies.sh validate` prints no `STRATEGY FAIL`.
- `merge-strategies.sh rehearse <name>` prints `REHEARSAL OK`.
- The script is executable, has LF line endings, and every command it runs has an allow rule.
