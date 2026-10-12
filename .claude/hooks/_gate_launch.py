"""Gate launcher body (contract 2026-10-07-worktree-isolation-by-default, I-2, I-3): guard first, then the gate."""
import io
import json
import os
import runpy
import sys
import traceback
GATES = ("concept-gate.py", "bash-gate.py")
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
REMEDY = ("Remedy: run /task, or EnterWorktree into a worktree under <root>/.claude/worktrees/, then retry; a "
          "subagent without a shell does not retry and ends its handoff with `BLOCKED: main checkout <target>`.")
BAN_WORDS = ("cd", "pushd", "popd", "set-location", "sl", "push-location", "gh")
BAN_TEXT = ("-C", "--git-dir", "--work-tree", "GIT_", "..", "~", "$", "%", "`")
WT_MARK = "/.claude/worktrees/"


def _worktree(path):
    parts = os.path.normcase(os.path.realpath(path)).replace("\\", "/").split("/")
    return any(parts[i] == ".claude" and parts[i + 1] == "worktrees" and parts[i + 2] for i in range(len(parts) - 2))


def _flat_add(command):
    words = command.split()
    if words[:3] != ["git", "worktree", "add"] or len(words) < 4:
        return False
    rest = words[4:]
    rest = rest[2:] if rest[:1] == ["-b"] else rest[1:] if rest[:1] == ["--detach"] else rest
    path = words[3].replace("\\", "/")
    head, _, name = path.rpartition(WT_MARK)
    return (len(rest) <= 1 and bool(head) and bool(name) and "/" not in name and WT_MARK not in head + "/"
            and ".." not in path and not any(q in path for q in "'\"$%`~"))


def _degraded(payload):
    tool, tool_input, cwd = payload.get("tool_name"), payload.get("tool_input") or {}, payload.get("cwd") or ""
    if tool in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not isinstance(path, str) or not path or ".." in path:
            return "the file target is empty or holds `..`"
        return None if _worktree(path if os.path.isabs(path) else os.path.join(cwd, path)) else "the file target is not in a worktree"
    command = tool_input.get("command")
    if tool not in ("Bash", "PowerShell") or not isinstance(command, str) or not cwd:
        return "this call cannot be judged without the guard"
    if _flat_add(command):
        return None
    flat = command.lower()
    for ch in ";&|()\"'=":
        flat = flat.replace(ch, " ")
    words = flat.split()
    drive = any(c == ":" and 0 < i < len(command) - 1 and command[i - 1].isalpha() and command[i + 1] in "/\\"
                for i, c in enumerate(command))
    if drive or any(w[:1] in "/\\" or w in BAN_WORDS for w in words) or any(t in command for t in BAN_TEXT):
        return "the command holds a directory change, an option, a path or a variable the degraded rule cannot judge"
    return None if _worktree(cwd) else "the working folder is not in a worktree"


def _log(payload, reason, cause):
    try:  # one errors.jsonl line; a failed write never changes the verdict
        logs = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".", ".claude", "logs")
        if os.path.isdir(logs):
            with open(os.path.join(logs, "errors.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"hook": "gate-launch", "event": "block", "details": {"reason": reason, "cause": cause}}) + "\n")
    except Exception:
        pass


def _decide(gate_arg):
    raw = sys.stdin.buffer.read()
    payload = json.loads(raw.decode("utf-8"))
    here, there = (os.path.dirname(os.path.realpath(p)) for p in (__file__, gate_arg))
    if not isinstance(payload, dict):
        return raw, {}, ("block", "MAIN CHECKOUT (launcher failed): the payload is not a JSON object\n")
    if os.path.basename(gate_arg) not in GATES:
        return raw, payload, ("block", "MAIN CHECKOUT (launcher failed): %r is not a known gate\n" % (gate_arg,))
    if os.path.normcase(here) != os.path.normcase(there):
        return raw, payload, ("block", "MAIN CHECKOUT (launcher misregistered): launcher folder %s, gate folder %s. The hook "
                              "row's second argument must name the gate in the launcher's folder; re-run "
                              "auto_improve_finish_install.py from this plugin version, or set it to "
                              "${CLAUDE_PROJECT_DIR}/.claude/hooks/<gate>\n" % (here, there))
    if not os.path.isfile(gate_arg):
        return raw, payload, ("block", "MAIN CHECKOUT (launcher failed): the gate file %s is missing\n" % (gate_arg,))
    try:
        import _main_checkout_guard
        verdict = getattr(_main_checkout_guard, "decide")(raw.decode("utf-8"))
    except Exception as exc:
        cause, reason = "%s: %s" % (type(exc).__name__, exc), _degraded(payload)
        if reason is None:
            return raw, payload, ("allow", "")
        _log(payload, reason, cause)
        return raw, payload, ("block", "MAIN CHECKOUT (guard degraded): %s\nCause: %s\nModule looked for: %s\n%s\n" % (
            reason, cause, os.path.join(here, "_main_checkout_guard.py"), REMEDY))
    if not (isinstance(verdict, tuple) and len(verdict) == 2 and verdict[0] in ("allow", "block")):
        raise TypeError("the guard returned a non-verdict: %r" % (verdict,))
    return raw, payload, verdict


def main():
    gate_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        raw, payload, verdict = _decide(gate_arg)
    except (SystemExit, Exception) as exc:
        sys.stderr.write("MAIN CHECKOUT (launcher failed): %s: %s\n" % (type(exc).__name__, exc))
        sys.exit(2)
    if verdict[0] == "block":
        sys.stderr.write(verdict[1])
        sys.exit(2)
    if payload.get("tool_name") == "PowerShell":
        return  # the bash gate's own checks stay Bash-only
    sys.stdin = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
    sys.argv = [gate_arg]
    try:
        runpy.run_path(gate_arg, run_name="__main__")
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
