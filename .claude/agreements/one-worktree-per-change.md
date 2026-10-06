# One Worktree Per Change

A session that will change files starts from the task intake command (the plugin's /task skill). That command can create an isolated worktree on a fresh branch. Choose that option.

Never edit in the shared main checkout. Other sessions may be using it, and their changes would collide with yours.

A change is finished only when it is shipped as a pull request. Implementing and stopping is not finished.

Read-only work needs no worktree. Answering a question, an audit or an investigation can run anywhere.

Facts in the brief were gathered somewhere else. Read them again inside the worktree before you rely on them, because the code there may differ.
