"""
registry_migrations -- the numbered registry migrations (contract 2026-11-04-domain-split-registries).

The seam: migration N+1 is one module in this package plus one entry in ``MIGRATIONS``. A migration module
exposes ``NUMBER``, ``FROM_LAYOUT``, ``TO_LAYOUT``, ``STATES`` (the layout states it applies to) and
``build_plan(ctx) -> Plan`` / ``verify_plan(plan) -> Optional[str]`` (see ``m0001_domain_split``).

The list holds module names, not modules, so the runner imports a migration only when it needs it and can name
a missing module in its refusal.
"""

from __future__ import annotations

import importlib
from typing import Any

MIGRATIONS = ("m0001_domain_split",)


def load(name: str) -> Any:
    """Import one migration module by its name in ``MIGRATIONS``."""
    return importlib.import_module("registry_migrations." + name)


def migration_for(state: str) -> Any:
    """The first migration whose ``STATES`` include ``state``, or None."""
    for name in MIGRATIONS:
        module = load(name)
        if state in module.STATES:
            return module
    return None
