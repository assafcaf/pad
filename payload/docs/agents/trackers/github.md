# Issue tracker: GitHub Issues

Issues and specs for this repo live in **GitHub Issues**, reached through the `gh` CLI.

## Where

| | |
|---|---|
| Repository | `<owner>/<repo>` |
| Issue keys | `#12`. A skill that writes `PROJ-12` means `#12` here — translate it. |
| Labels | the five triage roles, plus `wayfinder:*` for `/wayfinder` |

`gh` must be authenticated (`gh auth status`) with the `repo` scope. Every command below
assumes the repo's own directory, or pass `--repo <owner>/<repo>`.

## How

| Operation | Command |
|---|---|
| Create an issue | `gh issue create --title T --body B [--label L]` |
| Read an issue | `gh issue view <n> --comments` |
| Find issues | `gh issue list --search '<query>' --state open --json number,title,labels` |
| Comment | `gh issue comment <n> --body B` |
| Edit fields, incl. labels | `gh issue edit <n> --add-label L --remove-label M` |
| Close | `gh issue close <n> --comment "why"` |
| Reopen | `gh issue reopen <n>` |
| Link two issues | a comment naming the other issue — see "Blocking" below |
| Resolve a person | `gh api users/<login> --jq .login` |

Prefer `--json` on anything you are going to parse. Scraping `gh`'s human output is how a
run starts acting on a title it misread.

## When a skill says "publish to the issue tracker"

`gh issue create`. GitHub has no issue types, so carry the distinction in labels — add
`type:bug`, `type:task`, `type:feature` or `type:epic` as the first label. Create them once
with `gh label create` if they do not exist; `gh issue create` fails on an unknown label
rather than inventing it.

## When a skill says "fetch the relevant ticket"

`gh issue view <n> --comments`. Read the comments, not just the body: they carry the
negotiation that led to the issue's current shape, and are usually where the real
constraints are.

## Closing

`gh issue close <n> --comment "why"`. One command, unlike Jira's transitions — but say why
in the comment before or with the close, never after.

A commit or PR body containing `Closes #12` closes the issue on merge. Use it deliberately:
it is convenient in a PR, and a surprise in a stray commit message.

## Pull requests

**PRs as a request surface: no.** PRs are code review, not an intake queue. Nothing in
triage reads them. `gh pr create`, `gh pr view <n> --comments` and `gh pr diff <n>` are for
review work only.

## Wayfinding operations

Used by `/wayfinder`. GitHub has no parent/child hierarchy on issues, so the **map** is one
issue and the tickets point back at it.

- **Map**: an issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog
  body. Its number is the map key.
- **Child ticket**: an issue labelled `wayfinder:<type>` (`research` / `prototype` /
  `grilling` / `task`) whose body's first line is `Map: #<map>`. Also add it to the map's
  body as a task-list item (`- [ ] #<n>`) — GitHub renders those with live state, which is
  the closest thing to native hierarchy available. Once claimed, set the assignee.
- **Blocking**: a line `Blocked by: #<n>` in the issue body — one per blocker, so it can be
  parsed. GitHub's own "linked issues" only relate PRs to issues, not issues to each other.
- **Frontier query**: the map's open children with no assignee and no open blocker.
  `gh issue list --label wayfinder:map` finds the map; then
  `gh issue list --search 'no:assignee state:open "Map: #<map>"' --json number,body`, and
  drop any whose `Blocked by:` lines name an issue that is still open. First in map-body
  order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`. This is the session's first write.
- **Resolve**: comment the answer, `gh issue close <n>`, then append a context pointer to
  the map's Decisions-so-far section with `gh issue edit <map> --body`.
