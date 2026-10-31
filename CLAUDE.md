# Project rules

## Every change to shipped plugin files bumps the plugin version

Any pull request that changes a file the plugin ships (scripts, hooks, skills, agents, templates, registry seeds the doctor copies) must raise the plugin version in the same pull request. Use a patch bump for a fix and a minor bump for a new capability.

Change all five places together, so they never disagree:

- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (two entries: the top-level version and the plugin entry)

This is enforced, not advisory. The script `.claude/scripts/check_version_bump.py` fails when shipped files changed and the version did not rise, or when the manifests disagree. The GitHub Actions workflow `.github/workflows/version-bump.yml` runs it on every pull request, passing the default branch and the head ref. Run it yourself before committing: `py -3 .claude/scripts/check_version_bump.py`. To make the check block merging, mark the `version-bump` check as required in the repository's branch protection settings. Installed copies only update when the version changes, so a fix without a bump never reaches users.

**A contract delivered through a parent branch is raised once, at the landing (the Parent Branch Delivery Rule).** A sub-task pull request into a parent branch does not raise the version: `check_version_bump.py` runs in `parent` mode for a `task/<slug>/<id>` head into a non-default base and requires the head's version to equal the base's, or the version at the merge base with the default branch. The landing merges the default branch into the parent branch, then raises the version once, and the landing raise is always a minor raise: minor + 1, patch reset to 0, relative to the default branch's version (`contractLanding.versionRaise: true` in `.claude/work-item-conventions.json` turns it on). It runs `check_version_bump.py --raise` and then `--exact`. Under `landing: manual` the landing does not run, so the operator merges the default branch into the parent branch, then runs `py -3 .claude/scripts/check_version_bump.py --raise --default-branch master` and `py -3 .claude/scripts/check_version_bump.py --exact --default-branch master`. CI enforces only that the version was raised.

A change that touches only documentation or work-item briefs needs no bump, except the registry files the doctor copies (see below).

The registries the plugin doctor copies into user projects (`.claude/registries/MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md`) count as shipped files. Any pull request that touches them raises the version (at least a patch), and this rule wins over the documentation exemption above. The doctor never overwrites an existing file, so the raise refreshes the seed that new projects receive. Authors should batch registry appends (reviewer janitor entries, journal entries) with a change that already raises the version, instead of opening a registry-only pull request.
