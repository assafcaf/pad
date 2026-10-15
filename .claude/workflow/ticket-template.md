# Ticket body

A ticket is an ownership unit: one owner takes it from start to merged. `/tickets` writes every
ticket in this shape, and `/pad-run`, `plan-check.sh` and `task-submit.sh --ticket`
parse it. Keep the headings exactly.

```markdown
## Outcome
What is true when this is done — one or two sentences, observable.

## Reference
Path or link the result is judged against: a mock crop and its viewport | spec outcome ids |
a repro test | a baseline file. A spike ticket says `spike: produces <what>`.

## Owns
- path/or/dir/            (the files this ticket may write; a directory covers everything below it)

## Touches
- shared/registry.ts      (shared files it may only add to; none when it has none)

## Protected
yes | no — yes when Owns or Touches matches the config's Protected paths. Yes forces the strict
discipline: a test-designer writes the tests, red is proven, and the tests are read-only to the owner.

## Depends on
Ticket keys that must land first because this one builds on what they produce, or "none".
Sharing a file is never a reason.

## Out of scope
What a reasonable owner might add but must not.

## Spec
Path to the scope (spec) and its decision record, if one exists.
```

When the reference is tests, add the outcomes the tests must state, after `## Reference`:

```markdown
## Outcomes
- [O1] Given <state>, when <action>, then <observable result>. (level: unit | integration | surface <name> | <resource tag>)
```

## The four tests

A ticket is valid only if it passes all four. `plan-check.sh` checks the mechanical half.

1. **Ownable.** Its `Owns` is disjoint from every other ticket's (`OVERLAPS` is a planning
   error), and its shared files are in `Touches`, append-only. A write outside
   `Owns ∪ Touches` is a request to that file's owner; `task-submit.sh --ticket` rejects it.
2. **Checkable.** It names its reference. No reference means it is a **spike**: it produces the
   reference (a mock crop, a repro, a baseline, a decision) and never product code.
3. **Finishable by one owner** in one session (about 45 minutes on the critical path). Larger
   splits by surface or module, never by concern.
4. **One owner, start to merged.** Others may advise it, answer it or ask it for changes;
   nobody else writes its files.

A transverse sweep ("all colours", "all fonts", "every button") fails 1 and 3: it touches every
file. A cross-cutting concern is a line in the run's brief, or a foundation ticket that lands
first and the others depend on, never a parallel ticket. `plan-check.sh` flags one as `SWEEPS`.
