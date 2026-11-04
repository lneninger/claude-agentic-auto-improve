#!/usr/bin/env python3
"""
_preview_apply.py -- the preview-hash apply helpers shared by finish-install and registry_migrate.

``_plan_digest`` and ``_atomic_write`` are extracted unchanged from ``auto_improve_finish_install.py``
(which imports them back). ``stage_and_replace`` is new: it writes several files so that either every
target is replaced or none is.

Standard library only, and importing this module changes no ``sys`` state.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _plan_digest(*parts: bytes) -> str:
    """SHA-256 over the parts, each length-prefixed so neighbouring parts cannot run together."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def _atomic_write(target: Path, data: bytes) -> Optional[str]:
    """Write via a temporary file and os.replace; return an error text, or None on success."""
    tmp = target.with_name("." + target.name + ".tmp-%d" % os.getpid())
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as handle:
            handle.write(data)
        os.replace(tmp, target)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        return str(exc)
    return None


def _write_failed(message: str, path: Any) -> Dict[str, Any]:
    return {"status": "refused", "code": "write-failed", "message": message, "path": str(path)}


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _backup_relative(target: Path) -> Path:
    """The path a target is backed up under inside ``backup_dir``: its absolute path without the anchor."""
    resolved = Path(os.path.abspath(str(target)))
    return Path(*resolved.parts[1:]) if resolved.anchor else resolved


def stage_and_replace(writes: Sequence[Tuple[Path, bytes]], backup_dir: Path) -> Dict[str, Any]:
    """Replace every target with its planned bytes, or leave every target as it was.

    (a) Each planned output is written to ``.<name>.stage-<pid>`` beside its target; any failure deletes
        every stage file and returns ``write-failed`` with no target touched.
    (b) Every existing target is copied into ``backup_dir/<relative path>`` (nothing is written beside
        a target for a backup).
    (c) Each stage file is ``os.replace``d onto its target in plan order.
    (d) On a replace failure every already-replaced target is restored from ``backup_dir`` (a target that
        did not exist is deleted), the remaining stage files are deleted and ``write-failed`` is returned.

    Returns ``{"status": "applied", "written": [paths], "backup-dir": str}`` on success, otherwise the
    ``write-failed`` refusal dict ``{"status": "refused", "code": "write-failed", "message", "path"}``.
    """
    backup_dir = Path(backup_dir)
    plan: List[Tuple[Path, bytes, Path]] = []
    for target, data in writes:
        target = Path(target)
        plan.append((target, data, target.with_name("." + target.name + ".stage-%d" % os.getpid())))

    # (a) stage
    staged: List[Path] = []
    for target, data, stage in plan:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(stage, "wb") as handle:
                handle.write(data)
            staged.append(stage)
        except OSError as exc:
            _unlink_quietly(stage)
            for done in staged:
                _unlink_quietly(done)
            return _write_failed("staging %s failed, nothing was changed: %s" % (target, exc), target)

    # (b) back up the existing targets
    existed: Dict[Path, Optional[Path]] = {}
    for target, _data, stage in plan:
        if target.is_file():
            copy = backup_dir / _backup_relative(target)
            try:
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, copy)
            except OSError as exc:
                for _t, _d, leftover in plan:
                    _unlink_quietly(leftover)
                return _write_failed("backing up %s failed, nothing was changed: %s" % (target, exc), target)
            existed[target] = copy
        else:
            existed[target] = None

    # (c) replace in plan order
    replaced: List[Path] = []
    for index, (target, _data, stage) in enumerate(plan):
        try:
            os.replace(stage, target)
        except OSError as exc:
            # (d) roll back
            problems: List[str] = []
            for done in replaced:
                copy = existed[done]
                try:
                    if copy is None:
                        done.unlink()
                    else:
                        shutil.copy2(copy, done)
                except OSError as restore_exc:
                    problems.append("%s: %s" % (done, restore_exc))
            for _t, _d, leftover in plan[index:]:
                _unlink_quietly(leftover)
            message = "replacing %s failed, earlier targets were restored: %s" % (target, exc)
            if problems:
                message += " (could not restore: %s; the backups are under %s)" % ("; ".join(problems), backup_dir)
            return _write_failed(message, target)
        replaced.append(target)

    return {"status": "applied", "written": [str(t) for t, _d, _s in plan], "backup-dir": str(backup_dir)}
