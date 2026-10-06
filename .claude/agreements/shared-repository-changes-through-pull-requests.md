# Shared Repository Changes Go Through Pull Requests

A change to a shared toolkit or plugin repository goes through a branch and a draft pull request. Never push straight to its main branch, even when nobody else works there.

Create the branch before the first commit. A commit made on the main branch first is hard to undo cleanly.

A change that spans two repositories opens two linked draft pull requests. Name each one in the other's description, and merge them together.

The user merges. You open the draft and leave it for review.
