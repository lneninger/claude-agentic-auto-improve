"""Main-checkout guard (contract 2026-10-07-worktree-isolation-by-default, I-1, I-6).

``decide(text)`` judges one PreToolUse payload (the decoded stdin text) and answers
``("allow", "")`` or ``("block", banner)``. It refuses edits, file writes and tree-changing git or
gh commands aimed at the session's main checkout. It reads the filesystem and the hook's own
environment only, with one exception: for ``gh pr create``, ``gh pr edit`` with a base option and
``gh pr merge`` it runs ``../scripts/merge_direction.py`` as a subprocess (Extension Point 2) and
blocks on any non-zero exit, a missing script or a timeout (marker ``MERGE DIRECTION``). The gate
launcher (``_gate_launch.py``) calls it before either gate is loaded and runs no subprocess itself.

The guard is not a sandbox: git spellings beyond the allow-list are ``mutating`` and blocked, a
segment the parser cannot structure blocks when it names git or gh (fail closed), and programs that
write without a recognised write target are not judged.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys

import _project_paths as pp

MARKER = "MAIN CHECKOUT"
MD_MARKER = "MERGE DIRECTION"
#: Seconds the merge-direction check may take before the pull request command is refused.
MD_TIMEOUT = 20
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
FILE_KEYS = ("file_path", "notebook_path")
OUTSIDE = pp.OUTSIDE

#: Git subcommands allowed in the main checkout (Git command class). Any other is mutating.
GIT_READ = frozenset(
    "status log diff show fetch push branch tag rev-parse rev-list ls-files ls-remote ls-tree cat-file "
    "describe shortlog blame grep merge-base for-each-ref name-rev check-ignore".split())
GIT_GLOBAL_OK = ("--no-pager", "-p", "--paginate", "-P", "--no-optional-locks")
#: Per-subcommand argument prefixes that make an allowed member mutating.
GIT_EXCLUDED = {
    "fetch": ("-u", "--update-head-ok", "--upload-pack", "--recurse-submodules"),
    "push": ("--receive-pack", "--exec"),
    "grep": ("-O", "--open-files-in-pager"),
}
#: gh ``<group> <verb>`` pairs that change the working tree (the gh command class).
GH_MUTATING = frozenset({("pr", "checkout"), ("repo", "sync"), ("repo", "clone"), ("release", "download"),
                         ("run", "download"), ("gist", "clone")})
SHELLS = ("bash", "sh", "zsh", "dash")
POWERSHELLS = ("powershell", "pwsh")
KEYWORDS = frozenset("if then elif else while until do ! { ( time env command exec nohup xargs &".split())
CLOSERS = frozenset(("}", ")", "fi", "done", "esac"))
CD_NAMES = frozenset(("cd", "pushd", "chdir", "set-location", "sl", "push-location"))
POP_NAMES = frozenset(("popd", "pop-location"))
#: write-operand commands: name -> which positional operands are write targets.
WRITERS = {"rm": "all", "rmdir": "all", "mkdir": "all", "touch": "all", "ln": "last",
           "set-content": "first", "add-content": "first", "clear-content": "first", "out-file": "first",
           "new-item": "first", "remove-item": "first", "rename-item": "first", "sc": "first", "ac": "first",
           "clc": "first", "ni": "first", "ri": "first", "del": "first", "erase": "first", "rd": "first",
           "rni": "first", "ren": "first", "copy-item": "dest", "cpi": "dest", "copy": "dest", "cp": "dest",
           "move-item": "both", "mi": "both", "move": "both", "mv": "both"}
PATH_PARAMS = ("-path", "-literalpath", "-filepath", "-destination")
SWITCHES = ("-force", "-recurse", "-append", "-nonewline", "-whatif", "-confirm", "-passthru")

REMEDY = (
    "Remedy (session): run `/task`, or `EnterWorktree` into a worktree under `{root}/.claude/worktrees/`, "
    "then retry.\n"
    "Remedy (subagent without a shell or EnterWorktree): do not retry and do not write elsewhere; end "
    "your handoff with `BLOCKED: main checkout {target}`; the calling session enters a worktree and "
    "relaunches you there.")
_WRITE_OUT = "The path cannot be resolved here: write the path out in full (no variable, substitution or tilde)."
_LEFT_BEHIND = "A directory change into the main checkout is kept by the shell: use `git -C <path>` instead of changing directory."


class Block(Exception):
    """Raised by a judge when a target must be refused."""

    def __init__(self, target: str, reason: str, hint: str = "", marker: str = MARKER) -> None:
        super().__init__(reason)
        self.target, self.reason, self.hint, self.marker = target, reason, hint, marker


class Ctx:
    """The session repository: its main checkout root, or ``any_main`` when undecidable."""

    def __init__(self, root: str | None, any_main: bool, cwd: str | None = None) -> None:
        self.root, self.any_main, self.cwd = root, any_main, cwd
        self.bash_gate = None


class State:
    """Acting directory (resolved path, ``OUTSIDE`` or ``None`` = unresolvable) with subshell scoping."""

    def __init__(self, dir_: str | None, track: bool) -> None:
        self.dir, self.track = dir_, track
        self.stack: list[str | None] = []
        self.changed = False


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _in_main(ctx: Ctx, path: str | None) -> bool:
    """True when ``path`` is a main-checkout tree that counts as the session's (or undecidable)."""
    if path is None or path == OUTSIDE:
        return False
    kind = pp.tree_kind(path)
    if kind == "undecidable":
        return True
    return kind == "main-checkout" and (ctx.any_main or _same(pp.main_checkout_root(path), ctx.root))


def _check_tree(ctx: Ctx, path: str, shown: str, what: str) -> None:
    if path == OUTSIDE:
        return
    if pp.tree_kind(path) == "undecidable":
        raise Block(shown, f"{what}: the tree of the target cannot be decided")
    if _in_main(ctx, path):
        raise Block(shown, f"{what} aims at the main checkout")


def _judge(ctx: Ctx, text: str, acting: str | None, reading: str, what: str) -> None:
    """Resolve one target text under ``reading`` (``unknown`` = both readings, the stricter wins)."""
    for one in (("bash", "windows") if reading == "unknown" else (reading,)):
        status, path = pp.resolve_target(text, acting, one)
        if status == "unresolvable":
            raise Block(text, f"{what}: the target cannot be resolved", _WRITE_OUT)
        if status == "path":
            _check_tree(ctx, path, text, what)


def _acting(text: str, reading: str) -> str | None:
    status, path = pp.resolve_target(text, None, reading)
    return path if status == "path" else (OUTSIDE if status == "outside" else None)


# ---------------------------------------------------------------------------
# Lexer: one command text -> events. Quotes are removed, substitutions become events of their own.
# ---------------------------------------------------------------------------
def _match(s: str, i: int) -> int:
    """Index of the ``)`` closing the ``(`` at ``s[i]``, or -1."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c in "'\"":
            j = s.find(c, j + 1)
            if j < 0:
                return -1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


def _strip_heredocs(text: str) -> str:
    """Drop here-document bodies (their text is data, not commands)."""
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in re.finditer(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_][\w-]*)\1", line):
            while i < len(lines) and lines[i].strip() != m.group(2):
                i += 1
            i += 1
    return "\n".join(out)


def lex(s: str, ps: bool) -> list[tuple]:
    """Events: ``seg`` (words, raw), ``sub`` (text), ``open``, ``close``, ``lbrace``, ``rbrace``, ``bad``."""
    ev: list[tuple] = []
    words: list[str] = []
    cur: list[str] = []
    state = {"in": False, "start": 0, "paren": 0, "brace": 0}
    n, i = len(s), 0

    def end_word() -> None:
        if state["in"]:
            words.append("".join(cur))
            cur.clear()
            state["in"] = False

    def end_seg(at: int) -> None:
        end_word()
        if words:
            ev.append(("seg", list(words), s[state["start"]:at]))
            words.clear()
        state["start"] = at + 1

    def sub(open_idx: int) -> int:
        k = _match(s, open_idx)
        if k < 0:
            ev.append(("bad",))
            return n
        ev.append(("sub", s[open_idx + 1:k]))
        cur.append("$(...)")
        state["in"] = True
        return k + 1

    while i < n:
        c = s[i]
        if c == "'":
            j = s.find("'", i + 1)
            if j < 0:
                return ev + [("bad",)]
            cur.append(s[i + 1:j])
            state["in"] = True
            i = j + 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n and s[j] != '"':
                d = s[j]
                if d == "\\" and not ps and j + 1 < n and s[j + 1] in '"\\$`':
                    buf.append(s[j + 1])
                    j += 2
                elif d == "`" and ps and j + 1 < n:
                    buf.append("`" + s[j + 1])
                    j += 2
                elif s[j:j + 2] == "$(":
                    k = _match(s, j + 1)
                    if k < 0:
                        return ev + [("bad",)]
                    ev.append(("sub", s[j + 2:k]))
                    buf.append("$(...)")
                    j = k + 1
                elif d == "`":
                    k = s.find("`", j + 1)
                    if k < 0:
                        return ev + [("bad",)]
                    ev.append(("sub", s[j + 1:k]))
                    buf.append("$(...)")
                    j = k + 1
                else:
                    buf.append(d)
                    j += 1
            if j >= n:
                return ev + [("bad",)]
            cur.append("".join(buf))
            state["in"] = True
            i = j + 1
        elif c == "\\" and not ps:
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt == "\n":
                i += 2
                continue
            if nxt and nxt in " \"'$`;&|<>()":
                cur.append(nxt)
                i += 2
            else:
                cur.append("\\")
                i += 1
            state["in"] = True
        elif c == "`" and ps:
            cur.append("`" + (s[i + 1] if i + 1 < n else ""))
            state["in"] = True
            i += 2
        elif c == "`":
            k = s.find("`", i + 1)
            if k < 0:
                return ev + [("bad",)]
            ev.append(("sub", s[i + 1:k]))
            cur.append("$(...)")
            state["in"] = True
            i = k + 1
        elif s[i:i + 2] == "$(":
            i = sub(i + 1)
        elif s[i:i + 2] == "${":
            k = s.find("}", i)
            if k < 0:
                return ev + [("bad",)]
            cur.append(s[i:k + 1])
            state["in"] = True
            i = k + 1
        elif c in " \t\r":
            end_word()
            i += 1
        elif c == "\n" or c == ";" or c == "|":
            end_seg(i)
            i += 1
        elif c == "&":
            prev = s[i - 1] if i else ""
            if prev == ">" or s[i + 1:i + 2] == ">":
                cur.append(c)
                state["in"] = True
            elif ps and not words and not state["in"] and s[i + 1:i + 2] != "&":
                words.append("&")
            else:
                end_seg(i)
                if s[i + 1:i + 2] == "&":
                    i += 1
                    state["start"] = i + 1
            i += 1
        elif c == "#" and not state["in"]:
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif c == "(":
            end_seg(i)
            if re.match(r"\s*\)", s[i + 1:]):
                return ev + [("bad",)]
            ev.append(("open",))
            state["paren"] += 1
            i += 1
        elif c == ")":
            end_seg(i)
            ev.append(("close",))
            state["paren"] -= 1
            i += 1
        elif c in "{}" and (ps or (not state["in"] and (i + 1 >= n or s[i + 1] in " \t\n;)") and
                                  (c == "{" or i == 0 or s[i - 1] in " \t\n;"))):
            end_seg(i)
            ev.append(("lbrace",) if c == "{" else ("rbrace",))
            state["brace"] += 1 if c == "{" else -1
            i += 1
        else:
            cur.append(c)
            state["in"] = True
            i += 1
    end_seg(n)
    if state["paren"] or state["brace"]:
        ev.append(("bad",))
    return ev


# ---------------------------------------------------------------------------
# Segment analysis.
# ---------------------------------------------------------------------------
def _basename(word: str) -> str:
    base = re.split(r"[/\\]", word.strip("'\""))[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def _names_sensitive(ctx: Ctx, text: str) -> bool:
    if re.search(r"(?i)(?<![\w-])(git|gh)(\.exe)?(?![\w-])", text):
        return True
    if ctx.root:
        flat = text.lower().replace("\\", "/")
        root = os.path.normcase(ctx.root).replace("\\", "/")
        return root in flat or root.split(":", 1)[-1] in flat
    return False


def _undecidable(ctx: Ctx, st: State, text: str, why: str) -> None:
    """Fail closed: block when the text names git or gh or the main checkout, or the folder is main."""
    if _names_sensitive(ctx, text) or st.dir is None or _in_main(ctx, st.dir):
        raise Block(text[:120], f"cannot structure this command ({why}) and it names git, gh, the main "
                                f"checkout or acts in one")


def _split_positional(args: list[str], reading: str) -> tuple[list[str], dict[str, str]]:
    pos: list[str] = []
    named: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        low = a.lower()
        if a.startswith("-") and a != "-":
            if low in PATH_PARAMS and i + 1 < len(args):
                named[low] = args[i + 1]
                i += 1
            elif reading == "windows" and low not in SWITCHES and i + 1 < len(args):
                i += 1
        else:
            pos.append(a)
        i += 1
    return pos, named


def _write_operands(ctx: Ctx, st: State, name: str, args: list[str], reading: str) -> None:
    pos, named = _split_positional(args, reading)
    mode = WRITERS[name]
    if name in ("cp", "mv", "copy", "move") and reading != "windows":
        return
    first = named.get("-path") or named.get("-literalpath") or named.get("-filepath") or (pos[0] if pos else None)
    dest = named.get("-destination") or (pos[1] if len(pos) > 1 else None)
    chosen = {"all": pos, "last": pos[-1:], "first": [first] if first else [], "dest": [dest] if dest else [],
              "both": [x for x in (first, dest) if x]}[mode]
    for target in chosen:
        _judge(ctx, target, st.dir, reading, f"`{name}` write target")


def _parse_git(args: list[str], assigns: list[str]) -> dict:
    """Split a git call into global options, subcommand and class (``mutating`` or read)."""
    mutating = any(a.startswith("GIT_") for a in assigns)
    c_dirs: list[str] = []
    extra = [a.split("=", 1)[1] for a in assigns if re.match(r"GIT_(DIR|WORK_TREE)=", a)]
    had_global = bool(assigns)
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        had_global = True
        if a == "-C" and i + 1 < len(args):
            c_dirs.append(args[i + 1])
            i += 2
            continue
        if a in GIT_GLOBAL_OK:
            i += 1
            continue
        mutating = True
        m = re.match(r"--(git-dir|work-tree)=(.*)", a)
        if m:
            extra.append(m.group(2))
        elif a in ("--git-dir", "--work-tree", "-c", "--namespace", "--exec-path") and i + 1 < len(args):
            if a in ("--git-dir", "--work-tree"):
                extra.append(args[i + 1])
            i += 1
        i += 1
    sub = args[i] if i < len(args) else ""
    rest = args[i + 1:]
    info = {"sub": sub, "rest": rest, "c_dirs": c_dirs, "extra": extra, "mutating": mutating,
            "worktree_add": None}
    if not sub:
        info["mutating"] = True
    elif sub == "worktree" and rest[:1] == ["add"]:
        pos, j = [], 1
        while j < len(rest):
            if rest[j] in ("-b", "-B", "--reason") and j + 1 < len(rest):
                j += 1
            elif not rest[j].startswith("-"):
                pos.append(rest[j])
            j += 1
        info["worktree_add"] = pos[0] if pos else ""
    elif not mutating:
        info["mutating"] = not _read_shape(sub, rest, had_global)
    return info


def _read_shape(sub: str, rest: list[str], had_global: bool) -> bool:
    """True when ``sub`` with ``rest`` is an allowed (read) shape in the main checkout."""
    if any(a == "-o" or a.startswith("--output") for a in rest):
        return False
    if sub in GIT_READ:
        if any(a.startswith(GIT_EXCLUDED.get(sub, ("\0",))) for a in rest):
            return False
        if sub == "branch":
            return not any(a in ("--force",) or re.fullmatch(r"-[A-Za-z]*[mMf][A-Za-z]*", a) for a in rest)
        return True
    if sub == "remote":
        return rest[:1] in (["-v"], ["--verbose"], ["show"], ["get-url"])
    if sub == "config":
        scoped = [a for a in rest if a not in ("--global", "--local", "--system", "--worktree")]
        return scoped[:1] in (["--get"], ["--get-all"], ["--list"], ["-l"])
    if sub == "reflog":
        return rest[:1] == ["show"]
    if sub == "stash":
        return rest[:1] in (["list"], ["show"])
    if sub == "worktree":
        return rest[:1] in (["list"], ["prune"], ["remove"])
    if sub == "merge":
        return (not had_global and len(rest) == 2 and rest[0] == "--ff-only" and not rest[1].startswith("-"))
    if sub == "pull":
        return (not had_global and 1 <= len(rest) <= 3 and rest[0] == "--ff-only"
                and not any(a.startswith("-") for a in rest[1:]))
    return False


def _git(ctx: Ctx, st: State, args: list[str], assigns: list[str], reading: str) -> None:
    info = _parse_git(args, assigns)
    tree: str | None = st.dir
    for c in info["c_dirs"]:
        status, path = pp.resolve_target(c, tree, reading)
        tree = path if status == "path" else (OUTSIDE if status == "outside" else None)
    trees = [tree]
    for extra in info["extra"]:
        status, path = pp.resolve_target(extra, st.dir, reading)
        trees.append(path if status == "path" else (OUTSIDE if status == "outside" else None))
    label = f"git {info['sub']}".strip()
    add = info["worktree_add"]
    if add is not None:
        status, path = pp.resolve_target(add, tree, reading)
        if status == "unresolvable":
            raise Block(add, f"{label}: the worktree path cannot be resolved", _WRITE_OUT)
        if status == "path":
            root = pp.main_checkout_root(tree) if tree not in (None, OUTSIDE) else None
            if root and _same(os.path.dirname(path), os.path.join(root, ".claude", "worktrees")):
                return
            if path.replace("\\", "/").lower().count("/.claude/worktrees/") >= 2:
                raise Block(add, f"{label}: a worktree inside a worktree is nested; cut it flat under "
                                 f"<main>/.claude/worktrees/")
            _check_tree(ctx, path, add, label)
        info["mutating"] = True
    if not info["mutating"]:
        return
    for t in trees:
        if t is None:
            raise Block(label, f"{label} runs in a directory that cannot be resolved", _WRITE_OUT)
        if _in_main(ctx, t):
            raise Block(label, f"{label} changes the main checkout (only the read-only git commands and "
                               f"`--ff-only` updates are allowed there)")


def _gh_mutating(args: list[str]) -> bool:
    kept, i = [], 0
    while i < len(args):
        if args[i] in ("-R", "--repo"):
            i += 2
            continue
        if not args[i].startswith("--repo="):
            kept.append(args[i])
        i += 1
    words = [a for a in kept if not a.startswith("-")]
    flags = [a for a in kept if a.startswith("-")]
    if len(words) < 2:
        return False
    pair = (words[0], words[1])
    if pair in GH_MUTATING:
        return True
    if pair == ("pr", "merge"):
        return any(f == "--delete-branch" or re.fullmatch(r"-[A-Za-z]*d[A-Za-z]*", f) for f in flags)
    if pair == ("issue", "develop"):
        return any(f == "--checkout" or re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", f) for f in flags)
    return False


# ---------------------------------------------------------------------------
# Merge direction (Extension Point 2): the only place a hook triggers the check.
# ---------------------------------------------------------------------------
#: Options of ``gh pr <action>`` that take a value (so the value is never read as the pull request).
_PR_VALUE_OPTS = {
    "create": frozenset("-t --title -b --body -F --body-file -a --assignee -l --label -m --milestone -p "
                        "--project -r --reviewer -T --template -H --head -B --base -R --repo".split()),
    "edit": frozenset("-t --title -b --body -F --body-file -m --milestone -B --base -R --repo --add-assignee "
                      "--add-label --add-project --add-reviewer --remove-assignee --remove-label "
                      "--remove-project --remove-reviewer".split()),
    "merge": frozenset("-b --body -F --body-file -t --subject -A --author-email --match-head-commit -R "
                       "--repo".split()),
}
_UNRESOLVED = re.compile(r"[$`]|%[^%\s]+%")


def _parse_gh_pr(args: list[str]) -> tuple[list[str], dict]:
    """Split ``gh`` arguments into positional words and options (value options per ``pr`` action)."""
    words: list[str] = []
    opts: dict = {}
    action: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        value_opts = _PR_VALUE_OPTS.get(action, frozenset(("-R", "--repo")))
        if a.startswith("--") and "=" in a:
            key, _, val = a.partition("=")
            opts[key] = val
        elif a.startswith("-") and a != "-":
            if a in value_opts and i + 1 < len(args):
                opts[a] = args[i + 1]
                i += 1
            elif not a.startswith("--") and len(a) > 2 and a[:2] in value_opts:
                opts[a[:2]] = a[2:]
            else:
                opts.setdefault(a, True)
        else:
            words.append(a)
            if len(words) == 2:
                action = words[1]
        i += 1
    return words, opts


def _merge_direction(ctx: Ctx, st: State, args: list[str], assigns: list[str]) -> None:
    """Run ``merge_direction.py`` for ``gh pr create``, ``gh pr edit --base`` and ``gh pr merge``."""
    words, opts = _parse_gh_pr(args)
    if words[:1] != ["pr"] or words[1:2] not in (["create"], ["edit"], ["merge"]):
        return
    action = words[1]
    base = opts.get("--base", opts.get("-B"))
    if action == "edit" and base is None:
        return
    head = opts.get("--head", opts.get("-H"))
    repo = opts.get("--repo", opts.get("-R"))
    given = [("--head", head), ("--base", base), ("--repo", repo)]
    pr = words[2] if action != "create" and len(words) > 2 else ("current" if action == "merge" else None)

    def refuse(reason: str) -> None:
        raise Block("gh pr " + action, reason, "", MD_MARKER)

    for flag, val in given + [("pull request", pr)]:
        if val is True:
            refuse("%s has no value, so the target cannot be judged" % flag)
        if isinstance(val, str) and _UNRESOLVED.search(val):
            refuse("%s holds a variable or substitution (%s): write it out in full" % (flag, val))
    here = st.dir if st.dir not in (None, OUTSIDE) else (ctx.cwd if st.dir == OUTSIDE else None)
    if not here or not os.path.isdir(here):
        refuse("the directory the command runs in cannot be resolved")
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "merge_direction.py")
    if not os.path.isfile(script):
        refuse("the check %s is missing, so no pull request can be judged" % script)
    cmd = [sys.executable, script, "--session-root", ctx.root or here, "--cwd", here]
    if head:
        cmd += ["--head", head]
    if base:
        cmd += ["--base", base]
    if repo is not None:
        cmd.append("--repo=" + repo)
    if pr:
        cmd += ["--pr", pr]
    env = dict(os.environ)
    for item in assigns:
        key, _, val = item.partition("=")
        if key == "GH_REPO":
            env[key] = val
    try:
        proc = subprocess.run(cmd, cwd=here, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=MD_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        refuse("the check could not run (%s)" % type(exc).__name__)
        return
    if proc.returncode == 0:
        return
    reason = ""
    try:
        verdict = json.loads(proc.stdout)
        reason = "%s: %s" % (verdict.get("reason"), verdict.get("detail"))
    except (ValueError, AttributeError):
        reason = (proc.stderr or proc.stdout or "exit %d" % proc.returncode).strip()[:300]
    refuse("%s (exit %d)" % (reason, proc.returncode))


def _change_dir(ctx: Ctx, st: State, name: str, args: list[str], reading: str) -> None:
    if name in POP_NAMES:
        new: str | None = None
    else:
        pos, named = _split_positional(args, reading)
        target = named.get("-path") or named.get("-literalpath") or (pos[0] if pos else ("~" if reading == "bash" else None))
        if target is None:
            return
        new = None
        if target != "-":
            status, path = pp.resolve_target(target, st.dir, reading)
            new = path if status == "path" else (OUTSIDE if status == "outside" else None)
    st.dir = new
    if st.track and not st.stack:
        st.changed = True


def _segment(ctx: Ctx, st: State, words: list[str], raw: str, reading: str, depth: int) -> None:
    words = list(words)
    assigns: list[str] = []
    while words:
        low = words[0].lower()
        if low in KEYWORDS:
            words.pop(0)
        elif re.match(r"^[A-Za-z_]\w*=", words[0]):
            assigns.append(words.pop(0))
        else:
            break
    if not words or (len(words) == 1 and words[0] in CLOSERS):
        return
    prog = _basename(words[0])
    args = words[1:]
    text = " ".join(words)
    ps = reading == "windows"
    if prog in ("case", "select", "function") or words[0] in ("[[",):
        _undecidable(ctx, st, raw, f"`{prog}`")
        return
    if re.match(r"^[$`]", words[0]) or "$(" in words[0]:
        _undecidable(ctx, st, raw, "a substitution in program position")
    elif prog in ("eval", "source", ".", "invoke-expression", "iex"):
        _undecidable(ctx, st, raw, f"`{prog}`")
    elif prog in CD_NAMES or prog in POP_NAMES:
        _change_dir(ctx, st, prog, args, reading)
    elif prog == "git":
        _git(ctx, st, args, assigns, reading)
    elif prog == "gh":
        if _gh_mutating(args) and (st.dir is None or _in_main(ctx, st.dir)):
            raise Block("gh " + " ".join(a for a in args if not a.startswith("-"))[:40],
                        "gh command that changes the working tree runs in the main checkout")
        _merge_direction(ctx, st, args, assigns)
    elif prog in SHELLS or prog in POWERSHELLS or prog == "cmd":
        _nested_shell(ctx, st, prog, args, raw, depth)
    elif prog in WRITERS:
        _write_operands(ctx, st, prog, args, reading)
    _redirects(ctx, st, raw, reading)


def _nested_shell(ctx: Ctx, st: State, prog: str, args: list[str], raw: str, depth: int) -> None:
    if any(a.startswith("<<") for a in args):
        _undecidable(ctx, st, raw, "a here-document fed to a shell")
        return
    code, reading = None, "bash"
    for i, a in enumerate(args):
        low = a.lower()
        if prog in SHELLS and re.fullmatch(r"-[a-z]*c[a-z]*", a) and i + 1 < len(args):
            code = args[i + 1]
        elif prog in POWERSHELLS and low in ("-c", "-command") and i + 1 < len(args):
            code, reading = " ".join(args[i + 1:]), "windows"
        elif prog in POWERSHELLS and low.startswith("-e"):
            _undecidable(ctx, st, raw, "an encoded command")
        elif prog == "cmd" and low in ("/c", "/k") and i + 1 < len(args):
            code, reading = " ".join(args[i + 1:]), "windows"
        if code is not None:
            break
    if code is None:
        return
    if depth >= 1:
        _undecidable(ctx, st, raw, "a shell nested twice")
        return
    analyze(ctx, _child(st), code, reading, depth + 1)


def _child(st: State) -> State:
    """A copy for a substitution or nested shell: its directory changes never leak out."""
    return State(st.dir, False)


def _redirects(ctx: Ctx, st: State, raw: str, reading: str) -> None:
    """Judge every write target ``parse_redirect_targets`` finds in one segment's text."""
    if ctx.bash_gate is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bash-gate.py")
        spec = importlib.util.spec_from_file_location("bash_gate_for_guard", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ctx.bash_gate = getattr(module, "parse_redirect_targets")
    for tool, target in ctx.bash_gate(raw):
        _judge(ctx, target, st.dir, reading, f"`{tool}` write target")


def analyze(ctx: Ctx, st: State, text: str, reading: str, depth: int = 0) -> None:
    """Judge every segment of one command text, tracking the acting directory."""
    text = _strip_heredocs(text.replace("\r", ""))
    events = lex(text, reading == "windows")
    if any(e[0] == "bad" for e in events):
        _undecidable(ctx, st, text, "unbalanced quotes, braces or parentheses, or an unsupported construct")
        return
    for ev in events:
        kind = ev[0]
        if kind == "sub":
            analyze(ctx, _child(st), ev[1], reading, depth)
        elif kind == "open":
            st.stack.append(st.dir)
        elif kind == "close":
            if not st.stack:
                _undecidable(ctx, st, text, "an unmatched closing parenthesis")
                return
            st.dir = st.stack.pop()
        elif kind == "seg":
            _segment(ctx, st, ev[1], ev[2], reading, depth)


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------
def _banner(ctx: Ctx, block: Block) -> str:
    root = (ctx.root or "<root>").replace("\\", "/")
    if block.marker == MD_MARKER:
        lines = [
            "=" * 62,
            f"[{MD_MARKER}] BLOCKED -- the pull request's target is wrong for its kind",
            "=" * 62,
            f"Target: {block.target}",
            f"Reason: {block.reason}",
            "Remedy: a sub-task's pull request targets its declared parent branch (`base:` in its brief); "
            "the parent's targets the default branch only once no sub-issue and no pull request into it "
            "is open. Pass `--base <branch>` (and `--head <branch>` from a detached HEAD) explicitly.",
        ]
        if block.hint:
            lines.append(block.hint)
        lines.append("=" * 62)
        return "\n".join(lines) + "\n"
    lines = [
        "=" * 62,
        f"[{MARKER}] BLOCKED -- the main checkout is shared by every session",
        "=" * 62,
        f"Target: {block.target}",
        f"Reason: {block.reason}",
        REMEDY.format(root=root, target=block.target),
    ]
    if block.hint:
        lines.append(block.hint)
    lines.append("=" * 62)
    return "\n".join(lines) + "\n"


def decide(text: str) -> tuple[str, str]:
    """Judge one hook payload. Returns ``("allow", "")`` or ``("block", banner)``."""
    payload = json.loads(text)
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()
    session_dir = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    session_real = os.path.realpath(session_dir)
    kind = pp.tree_kind(session_real)
    if kind == "outside-repository":
        return "allow", ""
    ctx = Ctx(pp.main_checkout_root(session_real), kind == "undecidable", cwd)
    st = State(_acting(cwd, "bash"), True)
    cwd_in_main = _in_main(ctx, st.dir)
    try:
        if tool in FILE_TOOLS:
            for key in FILE_KEYS:
                target = tool_input.get(key)
                if isinstance(target, str) and target:
                    _judge(ctx, target, st.dir, "unknown", f"{tool} target")
        elif tool in ("Bash", "PowerShell"):
            command = tool_input.get("command")
            if isinstance(command, str):
                analyze(ctx, st, command, "bash" if tool == "Bash" else "windows")
                if st.changed and not cwd_in_main and (st.dir is None or _in_main(ctx, st.dir)):
                    raise Block("directory change", "a directory change ends in the main checkout (or in a "
                                                    "folder that cannot be resolved)", _LEFT_BEHIND)
    except Block as block:
        return "block", _banner(ctx, block)
    return "allow", ""
