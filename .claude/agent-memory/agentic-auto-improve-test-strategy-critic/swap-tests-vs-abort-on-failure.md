---
name: swap-tests-vs-abort-on-failure
description: Race/swap tests of a deleter that stops on the first failure are vacuous unless the first-processed file exists at the swapped target
metadata:
  type: feedback
---

When a deleter re-checks each file before `os.remove` and also aborts on ANY failure, a swap test (folder -> junction, file -> folder, rename) only proves the re-check if the FIRST file the loop processes would really be deleted without it. Otherwise `FileNotFoundError` / "is a directory" aborts the loop and the test passes with the re-check deleted.

**Why:** issue #259 review (2026-11-05). X-4 swapped the session folder for a junction whose target lacked `availability.json`, the first name in NTFS listdir order, so the test passed with the re-check removed. Only the privilege-gated file-symlink row caught it.

**How to apply:** for any pruner/cleanup swap test, check the loop's iteration order (NTFS is sorted, POSIX is arbitrary). Make sure the target holds every name, or that the seam fires on a file that exists at the target. Then mentally delete the re-check and confirm the row goes red.
