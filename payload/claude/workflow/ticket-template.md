# Task ticket body

`/tickets` writes every task in this shape, and `/batch-implement` parses it. Keep the headings exactly.

```markdown
## Goal
One sentence: what a user of the code can do after this task that they couldn't before.

## Outcomes
- [O1] Given <state>, when <action>, then <observable result>. (level: unit | integration | <resource tag>)
- [O2] ...

## Files
Likely touched, one per line. Tasks in the same wave must not share a file.
- `path/to/module.py`
- `tests/test_module.py`

## Interfaces
- Consumes: exact names and signatures this task uses from earlier tasks.
- Produces: exact names and signatures later tasks rely on.

## Blocked by
Task keys, or "none".

## Out of scope
What a reasonable implementer might add but must not.

## Spec
Path to the spec (and to its decision record, if one exists).
```

Sizing: one implementer session. As a rule of thumb, at most 3 outcomes and about 5 files.
Split anything larger along its outcomes, not along technical layers.
