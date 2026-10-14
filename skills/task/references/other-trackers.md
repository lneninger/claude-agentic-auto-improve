### 1c. Other trackers (Jira / Azure DevOps)

Only if the argument is clearly Jira- or ADO-shaped (this project does not normally use them). Look for `mcp__*atlassian*__*` / `mcp__*jira*__*`, or `mcp__*azure*devops*__*` / `mcp__*ado*__*` tools, and pull summary, description, acceptance criteria, state, parent/epic link, and labels. If the matching MCP is not installed, go to Step 1d.

### 1d. Free text / unreachable tracker

Treat the argument as the task statement. Set `Source: free-text` (or `Source: <tracker> (unreachable)`) in the brief. Every field the tracker would have supplied becomes `UNKNOWN` and is resolved in Step 3.

This is a fully supported mode, not a degraded one — a well-clarified free-text brief beats a badly-parsed ticket.
