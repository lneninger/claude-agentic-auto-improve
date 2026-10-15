#!/usr/bin/env python3
"""
merge_direction.py -- refuse a pull request whose target is wrong for its kind, BEFORE it is
opened, retargeted or merged (contract 2026-10-07-worktree-isolation-by-default, I-9).

Usage:
  py -3 .claude/scripts/merge_direction.py [--head H] [--base B] --session-root R [--repo SPEC] [--cwd DIR]
  py -3 .claude/scripts/merge_direction.py --pr N|URL|current [--base B] --session-root R [--repo SPEC] [--cwd DIR]

Exit 0 allow, 11 refuse, 10 when an input cannot be read (``repository-unreadable``,
``default-branch-unreadable``, ``unverifiable``). The verdict is printed as one JSON object on
stdout and its reason on stderr. A caller reads any non-zero exit as a refusal.

Rules, in order:
  R-0  The target repository differs from the session repository (compared on host, owner and
       name, case-insensitively): allow only a base that is the target's default branch.
  R-1  A ``task/<slug>/<id>`` head must target the ``base:`` of the brief found at its commit.
  R-2  Any other head into the default branch is refused while a pull request into that head, or
       an OPEN sub-issue of the brief whose ``branch:`` is that head, is open.
  R-3  Everything else is allowed.

Inputs are read strictly: this script never guesses a default branch (it never calls
``default_branch()``), never treats an unreadable repository as cross-repository, and writes
nothing. It defines no brief or repository reader of its own; it imports ``pr_merged``'s.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from typing import Any, Dict, List, Optional, Tuple

import pr_merged
from pr_merged import (_owner_and_name_from_url, _run, brief_for_branch, default_branch_or_none,
                       file_at_commit, parse_brief_frontmatter, repo_view)

EXIT_ALLOW, EXIT_UNREADABLE, EXIT_REFUSE = 0, 10, 11
UNREADABLE = ("repository-unreadable", "default-branch-unreadable", "unverifiable")
DEFAULT_PARENT_LIST = "gh issue view <parent> --json subIssues"
_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")
_HOST = re.compile(r"[A-Za-z0-9.-]+(:\d+)?")


class Verdict(Exception):
    """Carries a final verdict out of a deep reader."""

    def __init__(self, allow: bool, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.allow, self.reason, self.detail = allow, reason, detail


def parse_repo_spec(text: Any) -> Optional[Tuple[str, str, str]]:
    """Parse ``OWNER/REPO``, ``HOST/OWNER/REPO`` or ``https://HOST/OWNER/REPO[.git][/]``.

    A pure text parser, not a reader: it touches no file, process or network. Returns
    ``(host, owner, name)`` lower-cased, an absent host meaning ``github.com``; ``None`` for
    anything else (empty, extra segments, whitespace, ``$``).
    """
    if not isinstance(text, str) or not text or text != text.strip() or re.search(r"\s", text):
        return None
    body = text
    if re.match(r"(?i)https://", body):
        body = body[len("https://"):]
        if body.endswith("/"):
            body = body[:-1]
        parts = body.split("/")
        if len(parts) != 3:
            return None
    else:
        parts = body.split("/")
        if len(parts) == 2:
            parts = ["github.com"] + parts
        elif len(parts) != 3:
            return None
    host, owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    if not _HOST.fullmatch(host) or not _SEGMENT.fullmatch(owner) or not _SEGMENT.fullmatch(name):
        return None
    if name in (".", "..") or owner in (".", ".."):
        return None
    return host.lower(), owner.lower(), name.lower()


def _split_name(name_with_owner: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(name_with_owner, str) or name_with_owner.count("/") != 1:
        return None
    owner, name = name_with_owner.split("/")
    return (owner.lower(), name.lower()) if owner and name else None


def _gh_name(parts: Tuple[str, str, str], default_host: str) -> str:
    host, owner, name = parts
    return "%s/%s" % (owner, name) if host == default_host.lower() else "%s/%s/%s" % (host, owner, name)


def _env_without_gh_repo() -> Dict[str, str]:
    return {k: v for k, v in os.environ.items() if k != "GH_REPO"}


def _parent_list_command() -> str:
    """``issueLink.parentLink.parentListCommand`` from the work-item conventions, else its known value."""
    try:
        import _claude_paths
        data = json.loads(_claude_paths.work_item_conventions_path().read_text(encoding="utf-8"))
        command = data["issueLink"]["parentLink"]["parentListCommand"]
        return command if isinstance(command, str) and command.strip() else DEFAULT_PARENT_LIST
    except Exception:
        return DEFAULT_PARENT_LIST


def _head_commit(head: str) -> Optional[str]:
    """The head branch's commit text for ``brief_for_branch``: local first, else origin's."""
    for ref in ("refs/heads/" + head, "refs/remotes/origin/" + head):
        code, _out = _run(["git", "rev-parse", "--verify", "--quiet", ref])
        if code == 0:
            return ref
    return None


def _open_children(brief_id: str) -> List[int]:
    """Numbers of the OPEN sub-issues of issue ``brief_id`` (R-2); raises ``Verdict`` when unreadable."""
    command = shlex.split(_parent_list_command().replace("<parent>", brief_id))
    if not command or command[0] != "gh":
        raise Verdict(False, "unverifiable", "the parent-list command is not a gh command")
    code, out = _run(command)
    try:
        payload = json.loads(out) if code == 0 and out else None
    except json.JSONDecodeError:
        payload = None
    children = payload.get("subIssues") if isinstance(payload, dict) else None
    if isinstance(children, dict):  # gh 2.96 answers {"nodes": [...], "totalCount": n}; older gh a bare list
        children = children.get("nodes")
    if not isinstance(children, list):
        raise Verdict(False, "unverifiable", "the sub-issues of #%s could not be read" % brief_id)
    open_numbers: List[int] = []
    for child in children:
        state = child.get("state") if isinstance(child, dict) else None
        if not isinstance(state, str) or state.upper() not in ("OPEN", "CLOSED"):
            raise Verdict(False, "unverifiable", "a sub-issue of #%s has no readable state" % brief_id)
        if state.upper() == "OPEN" and isinstance(child.get("number"), int):
            open_numbers.append(child["number"])
    return open_numbers


def _open_prs_into(head: str) -> List[Any]:
    code, out = _run(["gh", "pr", "list", "--state", "open", "--base", head, "--json", "number", "--limit", "200"])
    try:
        payload = json.loads(out) if code == 0 and out else None
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, list):
        raise Verdict(False, "unverifiable", "the open pull requests into %s could not be read" % head)
    return payload


def check(head: Optional[str], base: Optional[str], *, session_root: str, repo_spec: Optional[str],
          pr_ref: Optional[str], cwd: str) -> Tuple[bool, str, str]:
    """``(allow, reason, detail)`` for one pull request."""
    default_host = os.environ.get("GH_HOST") or "github.com"

    # Identity: the session repository, read from its own root with GH_REPO removed (gh would
    # otherwise answer for GH_REPO).
    session_view = repo_view(None, cwd=session_root, env=_env_without_gh_repo())
    session = _split_name(session_view.get("nameWithOwner")) if session_view else None
    if session is None:
        return False, "repository-unreadable", "the session repository's identity could not be read"
    session_id = (default_host.lower(),) + session

    # The target repository: -R/--repo, else GH_REPO, else the acting directory's own repository.
    spec = repo_spec if repo_spec is not None else (os.environ.get("GH_REPO") or None)
    target_view: Optional[Dict[str, Any]] = None
    if spec is not None:
        target_id = parse_repo_spec(spec)
        if target_id is None:
            return False, "repository-unreadable", "the repository %r cannot be parsed" % (spec,)
    else:
        target_view = repo_view(None, cwd=cwd)
        parts = _split_name(target_view.get("nameWithOwner")) if target_view else None
        if parts is None:
            return False, "repository-unreadable", "the acting directory's repository could not be read"
        target_id = (default_host.lower(),) + parts
    cross = target_id != session_id

    if pr_ref is not None:
        ref: Any = pr_ref
        if pr_ref == "current":
            code, branch = _run(["git", "symbolic-ref", "--short", "-q", "HEAD"])
            if code != 0 or not branch:
                return False, "unverifiable", "HEAD is detached, so the current pull request is unknown"
            ref = branch
        elif pr_ref.isdigit():
            ref = int(pr_ref)
            if repo_spec is not None:
                ref = "https://%s/%s/%s/pull/%s" % (target_id[0], target_id[1], target_id[2], pr_ref)
        pr = pr_merged.gh_pr(ref)
        if not pr:
            return False, "unverifiable", "pull request %s could not be read" % (pr_ref,)
        head = head or pr.get("headRefName")
        base = base or pr.get("baseRefName")
    if head is None:
        code, current = _run(["git", "symbolic-ref", "--short", "-q", "HEAD"])
        if code != 0 or not current:
            return False, "unverifiable", "HEAD is detached, so the head branch is unknown (pass --head)"
        head = current
    if not head:
        return False, "unverifiable", "the head branch is unknown"

    # The default branch: strict reads only.
    default: Optional[str]
    if cross:
        view = target_view if target_view is not None else repo_view(_gh_name(target_id, default_host))
        default = view.get("defaultBranchRef") if view else None
    else:
        default = default_branch_or_none(cwd=cwd)
        if not default:
            view = target_view if target_view is not None else (
                repo_view(_gh_name(target_id, default_host)) if spec is not None else repo_view(None, cwd=cwd))
            default = view.get("defaultBranchRef") if view else None
    if not default:
        return False, "default-branch-unreadable", "the default branch could not be read"
    if base is None:
        base = default  # a bare `gh pr create` targets the default branch

    # R-0
    if cross:
        if base == default:
            return True, "allowed", "cross-repository pull request into that repository's default branch"
        return False, "cross-repo-base-not-default", "a cross-repository pull request must target %s, not %s" % (default, base)

    # R-1
    if re.match(r"^task/[^/]+/.+", head):
        commit = _head_commit(head)
        try:
            brief = brief_for_branch(head, commit) if commit else None
        except pr_merged.AmbiguousBrief as exc:
            return False, "unverifiable", str(exc)
        declared = (brief or {}).get("base", "").strip().strip("'\"") if brief else ""
        if not declared or declared.lower() in ("none", "unknown"):
            return False, "base-not-declared", "no brief at %s declares a base for %s" % (commit or head, head)
        if base == declared:
            return True, "allowed", "%s targets its declared base %s" % (head, declared)
        if base == default:
            return False, "sub-task-targets-default", "%s declares base %s, so it must not target %s" % (head, declared, default)
        return False, "base-differs-from-declared", "%s declares base %s, not %s" % (head, declared, base)

    # R-2
    if base == default:
        try:
            if _open_prs_into(head):
                return False, "parent-opened-early", "a pull request into %s is still open" % head
            commit = _head_commit(head)
            try:
                brief = brief_for_branch(head, commit) if commit else None
            except pr_merged.AmbiguousBrief as exc:
                return False, "unverifiable", str(exc)
            digits = re.fullmatch(r"#?(\d+)", str((brief or {}).get("id") or "").strip())
            if digits:
                open_children = _open_children(digits.group(1))
                if open_children:
                    return False, "parent-opened-early", "sub-issue(s) still open: %s" % ", ".join("#%d" % n for n in open_children)
        except Verdict as verdict:
            return verdict.allow, verdict.reason, verdict.detail
    return True, "allowed", "no merge-direction rule applies"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Check a pull request's merge direction.")
    ap.add_argument("--head")
    ap.add_argument("--base")
    ap.add_argument("--pr", help="a pull request number, link, branch, or `current`")
    ap.add_argument("--repo", help="the target repository (-R/--repo spelling)")
    ap.add_argument("--session-root", required=True, help="the session repository's main checkout root")
    ap.add_argument("--cwd", help="the acting directory (default: the process folder)")
    args = ap.parse_args(argv)
    cwd = args.cwd or os.getcwd()
    try:
        # No --head and no --pr: the head is the acting directory's current branch (a detached
        # HEAD is `unverifiable`); no --base: the target's default branch (a bare `gh pr create`).
        allow, reason, detail = check(args.head, args.base, session_root=args.session_root,
                                      repo_spec=args.repo, pr_ref=args.pr, cwd=cwd)
    except Exception as exc:  # a check that cannot finish must refuse, never allow
        allow, reason, detail = False, "unverifiable", "%s: %s" % (type(exc).__name__, exc)
    verdict = {"verdict": "allow" if allow else "refuse", "reason": reason, "detail": detail}
    print(json.dumps(verdict))
    if not allow:
        sys.stderr.write("MERGE DIRECTION %s: %s\n" % (reason, detail))
    return EXIT_ALLOW if allow else (EXIT_UNREADABLE if reason in UNREADABLE else EXIT_REFUSE)


if __name__ == "__main__":
    sys.exit(main())
