#!/usr/bin/env python3
"""
test_memory_common.py -- Layer 2 reliability: the memory hooks are tested code.

Plain runnable script (matches the house style of
test_db_destructive_guard.py): no pytest dependency, prints a pass/fail
summary, exits non-zero on any failure.

    py -3 ~/.claude/hooks/tests/test_memory_common.py

Covers the pure logic that the pager + health audit depend on:
    - token estimation
    - over/under/missing budget classification
    - markdown link extraction + dead-link (divergence) detection
    - staging dedupe (idempotent pressure proposals)
    - pager fail-open on malformed input
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS_DIR))

import _memory_common as mc  # noqa: E402


_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {name}")
    else:
        _FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def test_token_estimation():
    check("tokens = chars//4", mc.estimate_tokens_from_text("a" * 400) == 100)
    check("empty text = 0 tokens", mc.estimate_tokens_from_text("") == 0)


def test_estimate_tokens_missing_file():
    missing = Path(tempfile.gettempdir()) / "definitely-not-here-xyz.md"
    check("missing file = 0 tokens (fail-soft)", mc.estimate_tokens(missing) == 0)


def test_budget_classification(tmp: Path):
    big = _write(tmp / "big.md", "x" * 8000)      # 2000 tok
    small = _write(tmp / "small.md", "x" * 400)   # 100 tok
    surfaces = [
        {"id": "over", "label": "o", "path": str(big), "budget_tokens": 1000},
        {"id": "under", "label": "u", "path": str(small), "budget_tokens": 1000},
        {"id": "gone", "label": "g", "path": str(tmp / "nope.md"), "budget_tokens": 1000},
    ]
    rows = {r["id"]: r for r in mc.check_budgets(surfaces)}
    check("over-budget detected", rows["over"]["status"] == "OVER", str(rows["over"]))
    check("over_by computed", rows["over"]["over_by"] == 1000, str(rows["over"]["over_by"]))
    check("under-budget OK", rows["under"]["status"] == "OK", str(rows["under"]))
    check("missing surface flagged", rows["gone"]["status"] == "MISSING")
    check("missing not counted as over", rows["gone"]["over_by"] == 0)


def test_link_extraction_filters():
    text = (
        "[a](foo.md) [b](http://x.com/y.md) [c](bar.md#anchor) "
        "[d](#local) [e](mailto:x@y.md) [f](sub/baz.md)"
    )
    targets = set(mc.extract_md_link_targets(text))
    check("local .md kept", "foo.md" in targets)
    check("anchor stripped + kept", "bar.md" in targets)
    check("subdir .md kept", "sub/baz.md" in targets)
    check("http excluded", not any("http" in t for t in targets))
    check("mailto excluded", not any("mailto" in t for t in targets))
    check("pure anchor excluded", "#local" not in targets and "local" not in targets)


def test_dead_link_detection(tmp: Path):
    real = _write(tmp / "real.md", "hi")
    index = _write(
        tmp / "index.md",
        f"see [ok]({real.name}) and [bad](ghost.md) and [ext](https://x.com/a.md)",
    )
    dead = mc.check_links(index)
    deadset = {d["target"] for d in dead}
    check("dead link detected", "ghost.md" in deadset, str(deadset))
    check("live link not flagged", real.name not in deadset)
    check("external link not flagged", not any("http" in t for t in deadset))


def test_staging_dedupe(tmp: Path):
    staging = tmp / "proposals.md"
    over = [{
        "id": "blockX", "label": "Block X", "path": "/p/x.md",
        "tokens": 9000, "budget": 7000, "over_by": 2000,
    }]
    entries = mc.build_pressure_entries(over)
    check("entry key carries today", entries[0]["key"].endswith(date.today().isoformat()))

    seen: dict = {}
    n1, seen = mc.append_staging(staging, entries, seen)
    check("first append writes 1", n1 == 1, str(n1))
    check("staging file created", staging.exists())

    # Same state again -> idempotent no-op.
    n2, seen = mc.append_staging(staging, entries, seen)
    check("second append is no-op (dedupe)", n2 == 0, str(n2))

    body = staging.read_text(encoding="utf-8")
    check("staging mentions over-by", "over by ~2000" in body, body[:200])
    check("staging has single entry", body.count("memory pressure:") == 1)


def test_pager_fail_open_on_config_error():
    """The pager must exit 0 (and cause NO side effects) when config load blows
    up. Isolated: load_config is monkeypatched to raise, so this never touches
    the real config or the real staging file."""
    pager_path = _HOOKS_DIR / "memory-pager.py"
    spec = importlib.util.spec_from_file_location("memory_pager_under_test", pager_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import io

    def _boom(*_a, **_k):
        raise RuntimeError("boom")

    old_stdin = sys.stdin
    orig_load = mod.mc.load_config
    try:
        mod.mc.load_config = _boom          # config error -> fail-open branch
        sys.stdin = io.StringIO("{}")
        rc = mod.run()
    finally:
        mod.mc.load_config = orig_load
        sys.stdin = old_stdin
    check("pager fail-open returns 0 on config error", rc == 0, f"rc={rc}")


def test_expand_handles_home_and_slashes():
    p = mc.expand("~/.claude/x.md")
    check("~ expanded", "~" not in str(p))
    check("forward-slash path preserved", mc.expand("d:/Dev/x.md").name == "x.md")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        print("test_memory_common")
        test_token_estimation()
        test_estimate_tokens_missing_file()
        test_budget_classification(tmp)
        test_link_extraction_filters()
        test_dead_link_detection(tmp)
        test_staging_dedupe(tmp)
        test_pager_fail_open_on_config_error()
        test_expand_handles_home_and_slashes()

    print("-" * 50)
    print(f" {_PASS} passed, {_FAIL} failed")
    print("-" * 50)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
