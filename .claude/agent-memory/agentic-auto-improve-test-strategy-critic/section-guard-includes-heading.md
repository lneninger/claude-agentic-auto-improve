---
name: section-guard-includes-heading
description: Text-pin "section found" guards using _section(...).strip() pass on a heading-only passage; also rule-8-style path regexes with "/" in the lookbehind miss <repo>/-rooted paths
metadata:
  type: project
---
In test_plugin_text_scans.py, `_section(text, start, stop)` returns the heading line itself, so `assertTrue(section.strip())` never proves the body exists; negative-only scans then pass on an emptied passage (found 2026-11-13, issue 354 review).

Path-ban regexes that put `/` in the lookbehind (rule 8 `_FOLDER_PATH_RE`) never fire on `<repo>/x/y/`, `~/x/y/`, `/srv/x/`, or backslash paths, which are the plugin's own common idioms.

**Why:** both were silent passes that the planted controls didn't cover.

**How to apply:** in any genericity or text-pin review, probe the extractor with a heading-only input and the scan with `<repo>/`-rooted paths, using `py -3 -B -` on stdin (no file written). Related: [[genericity-scan-single-token-hits]], [[json-only-cli-tests-miss-text-renderer]].
