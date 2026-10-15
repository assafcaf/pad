# Tracker adapter: Jira

Through the `atlassian` MCP server. Every call takes `cloudId` from `config.md`. Bodies are
Markdown (`contentFormat: markdown` / `responseContentFormat: markdown`). If the tools are not
available in the session, say so and stop; do not fall back to another tracker. The tracker agent
holds only the Jira tools this table names (`setup-workflow/tracker-agent-template.md`); a tool
added to a row here is added to the template too.

| Operation | How |
|---|---|
| Read one | `getJiraIssue` with `fields: [summary, description, status, issuetype, parent, issuelinks, labels]` |
| List an epic's tasks | `searchJiraIssuesUsingJql`, `jql: parent = <EPIC> ORDER BY created ASC` |
| Find existing by label | `jql: project = <PROJECT> AND labels = <label> AND summary ~ "<text>"` |
| Create epic | `createJiraIssue` with `projectKey`, `issueTypeName: <epic type>`, `summary`, `description`, `contentFormat: markdown`, `additional_fields: {"labels": [<label>]}` |
| Create task | same, with `issueTypeName: <task type>`, `parent: <EPIC>` and the ticket body as `description`. In a team-managed project `parent` takes the epic key for a Task; a company-managed one may use an Epic Link field instead — `/setup-workflow` checks which |
| Blocked-by edge | `createIssueLink`, `type: Blocks`, **`inwardIssue`: the blocker**, **`outwardIssue`: the blocked task** |
| Read blocked-by | in `issuelinks`, entries of type `Blocks` that carry an `inwardIssue` are this task's blockers |
| Update a ticket | `editJiraIssue` with `fields: {"description": <BODY>}` (and `summary` when the request carries one), `contentFormat: markdown` |
| Move status | `getTransitionsForJiraIssue`, then `transitionJiraIssue` with the id whose `to.name` is the configured status |
| Comment | `addCommentToJiraIssue` with `commentBody` and `contentFormat: markdown` |

## Status writes from scripts

`bin/ledger.sh` moves statuses and adds comments without an agent, through the Jira REST API, so
a merge records itself (`merge-task.sh --run`). It reads the site and status names from
`config.md` and its credentials from `.work/secrets/jira.env` in the main checkout (gitignored
with `.work/`), which each person creates:

```
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=<an Atlassian API token>
```

| Operation | Request |
|---|---|
| Move status | `GET /rest/api/3/issue/<KEY>/transitions`, then `POST` the same path with the id whose `to.name` is the configured status. Already in that status is OK |
| Comment | `POST /rest/api/3/issue/<KEY>/comment`, the text as one ADF paragraph |

The token goes to curl on stdin, never on its command line, and is never printed. A missing
file, an HTTP error or no matching transition prints `LEDGER FAIL <KEY>: <why>`.

The ticket body's `## Blocked by` section and the `Blocks` links must agree. If they don't, the
links win; record the mismatch as a ruling.
