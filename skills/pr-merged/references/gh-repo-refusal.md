## Refusal: `GH_REPO` is set in the environment

The script reads `GH_REPO` exactly once, before touching the contract, git or `gh` at all, and
only to refuse: with a non-empty `GH_REPO` set and the invocation naming `--pr` or `--dispatch`,
it prints `{"error": "gh-repo-set", ...}` and exits **8**. Nothing is read, written or closed.

`GH_REPO` retargets every `gh` call a process makes, including `gh issue close` — the exact
hazard this whole contract closes for a link. The script never sets it itself. The remedy is to
unset `GH_REPO` in that shell and run the command again; a pull request in **another** repository
is passed as its `https://` link, never through `GH_REPO`.
