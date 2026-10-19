# Run brief template

`/pad-run` writes `.work/runs/<epic>/brief.md` from this template at the start of a run, in the
main checkout. Every owner reads it on start, with its ticket. Keep it under about 60 lines:
it **links** to the sources of truth and never paraphrases them, because every restatement is
a place for intent to drift. Fill each `<…>`; delete a section's placeholder line when the
section has nothing.

```markdown
# Brief: <epic key> — <epic title>

## Sources of truth
- Scope: `.work/runs/<epic>/scope.md` (frozen; intent, non-goals, references, protected paths)
- Decision record: `docs/decisions/<NNNN-slug>.md`
- References: <the reference dir or links the scope names, one line each>
- Definition of done: `.claude/workflow/definition-of-done.md` (by reference class)

## The system already in the code
<What an owner must reuse rather than reinvent, each with its path: design tokens, shared
components, fixtures, test harnesses, the render command. One line each.>

## Rules in force
<The output of `rules.sh for owner`, as rule names with their file paths. Don't copy bodies.>

## Gates
- Named tests: `<command>` · Typecheck: `<command>` · Lint: `<command>`
- Never the full suite: `merge-task.sh` runs it once per merge, on the merged tree.
- Test paths: `<paths>` · Dev tests: `<path>` (never committed)

## Ownership map and team
| Ticket | Owns | Touches | Protected | Owner |
|---|---|---|---|---|
| <KEY> | <paths> | <paths> | yes/no | <KEY>-owner <agent id, filled at dispatch> |

Message an owner by its agent id (the second word of its Owner cell) for anything in its files. Post interface decisions, renames
in shared files and discoveries with
`bash .claude/workflow/bin/channel.sh post <epic> <KEY> "<line>"`; read the channel on start
and before every rebase (`channel.sh read <epic>`).

## Protocol
- Report exactly one line: `READY <KEY> <head> <red>` | `FAILED <KEY> <why>` |
  `NEEDS_RULING <KEY> <question>`. Never diffs or logs.
- A write outside your Owns ∪ Touches is a request to that file's owner, not an edit.
- On `CONFLICT` or `REJECTED` from the merge: rebase onto the epic head, fix, re-gate, report
  `READY` again. A ticket that fails twice is replanned.

## Rulings
<Appended by the orchestrator as they happen: `- <date> <KEY|run>: <decision> — <why>`.>
```
