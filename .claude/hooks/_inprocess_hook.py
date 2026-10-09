#!/usr/bin/env python3
"""
_inprocess_hook.py -- run a hook script inside the CURRENT process (INV-O4).

WHY THIS EXISTS
---------------
Every hook Claude Code launches costs one interpreter start. The four post-edit checks are small and
independent, so the post-edit dispatcher runs them one after another in a single process and uses
this helper to do it as if each were launched on its own.

THE CONTRACT
------------
    run_script(script: Path, data: bytes) -> tuple[int, bytes, bytes]

  * ``script`` is run the way ``python script`` would run it: as ``__main__``, with ``__file__`` set
    to its path and ``sys.argv`` holding just that path.
  * ``data`` is exactly what the script would have read from its standard input.
  * The result is ``(exit_code, output_bytes, error_bytes)``. Output and error text are UTF-8; a
    caller that decodes them should replace what it cannot read.
  * ``SystemExit`` gives its code (``None`` is 0; an integer is itself; anything else is printed to
    the error stream and is 1, which is what Python itself does). Any other exception gives exit
    code 1 and its traceback on the error stream. Nothing raised by the script leaves this function.
  * The streams, ``sys.argv`` and the working directory-independent module state are restored on the
    way out, whatever happened.

Standard library only. This module is a helper and is never registered as a hook.
"""

from __future__ import annotations

import io
import runpy
import sys
import traceback
from pathlib import Path


def _exit_code(exc: SystemExit, err: io.TextIOBase) -> int:
    """The process exit code Python itself would report for this SystemExit."""
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    try:
        err.write(str(code) + "\n")
    except Exception:
        pass
    return 1


def run_script(script: Path, data: bytes) -> tuple[int, bytes, bytes]:
    """Run ``script`` as ``__main__`` with ``data`` on stdin; return (exit code, stdout, stderr)."""
    out_raw = io.BytesIO()
    err_raw = io.BytesIO()
    stdin = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace")
    stdout = io.TextIOWrapper(out_raw, encoding="utf-8", errors="replace", write_through=True)
    stderr = io.TextIOWrapper(err_raw, encoding="utf-8", errors="replace", write_through=True)

    saved = (sys.stdin, sys.stdout, sys.stderr, sys.argv)
    sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
    sys.argv = [str(script)]
    code = 0
    try:
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:
            code = _exit_code(exc, stderr)
        except BaseException:  # a hook that raises must not take the dispatcher down with it
            code = 1
            try:
                stderr.write(traceback.format_exc())
            except Exception:
                pass
    finally:
        try:
            stdout.flush()
            stderr.flush()
        except Exception:
            pass
        sys.stdin, sys.stdout, sys.stderr, sys.argv = saved
    return code, out_raw.getvalue(), err_raw.getvalue()
