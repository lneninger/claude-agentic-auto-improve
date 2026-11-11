---
name: genericity-scan-single-token-hits
description: The plugin manifest's author and owner are one-word handles, so any genericity scan that filters strings by "has a space" or plants two-word fake names misses the real hazard
metadata:
  type: project
---
The plugin manifest yields a single one-word handle for both author and repository owner (seen 2026-11-11, issue 71 review). Machine paths are also usually one token.

**Why:** the issue 71 hook-text scan kept only strings holding a space and planted "Zzmadeup Quillfeather" (two words) as its control. A one-token owner constant, a space-free path, an f-string with no literal space, and bytes literals all escaped. Probed with `py -3 -B -` heredoc and made-up values.

**How to apply:** when reviewing any genericity or leak scan, plant a ONE-word made-up handle and a space-free made-up path as positive controls. Ask that regex exclusions be keyed on the call site (`re.compile`/`re.search` argument), not on string shape. Related: [[concept-gate-blocks-scratch-harness]].

Second pass (same day): call-site exclusion over-reached. Excluding EVERY argument of `re.sub`/`re.split` also drops the `repl` and `string` args, and `re.sub` repl is output text. Ask for the pattern arg only (args[0] / `pattern=`). Also ask: are split literals ("A" + "B", `%`, f-string pieces) checked, and is delivered JSON text (`working-agreements.rules.json` `dispatch_rule`) scanned at all.
