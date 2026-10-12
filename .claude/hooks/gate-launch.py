"""Gate launcher stub: every failure of the body exits 2 (contract 2026-10-07-worktree-isolation-by-default, I-3)."""
import sys, os
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _gate_launch
    _gate_launch.main()
except SystemExit:
    raise
except BaseException as exc:
    try:
        sys.stderr.write("MAIN CHECKOUT (launcher failed): %s: %s\n" % (type(exc).__name__, exc))
        sys.stderr.flush()
    finally:
        os._exit(2)
