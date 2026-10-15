# Project rules

## Every change to shipped plugin files bumps the plugin version

Any pull request that changes a file the plugin ships (scripts, hooks, skills, agents, templates) must raise the plugin version in the same pull request. Use a patch bump for a fix and a minor bump for a new capability.

Change all five places together, so they never disagree:

- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (two entries: the top-level version and the plugin entry)

This is enforced, not advisory. The script `.claude/scripts/check_version_bump.py` fails when shipped files changed and the version did not rise, or when the manifests disagree. The GitHub Actions workflow `.github/workflows/version-bump.yml` runs it on every pull request into `master`. Run it yourself before committing: `py -3 .claude/scripts/check_version_bump.py`. To make the check block merging, mark the `version-bump` check as required in the repository's branch protection settings. Installed copies only update when the version changes, so a fix without a bump never reaches users.

A change that touches only documentation or work-item briefs needs no bump.
