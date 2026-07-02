"""
research/diagnostics/registry.py — Diagnostic registration and lookup.

Usage
-----
    @register_diagnostic
    class D01SessionPersistence(BaseDiagnostic):
        id   = "d01"
        tags = ["sessions", "direction"]
        ...

    # Runner
    from research.diagnostics.registry import get_by_tag, all_diagnostics
    for cls in get_by_tag("sessions"):
        cls().run(data, config)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research.diagnostics.base import BaseDiagnostic

_REGISTRY: dict[str, type["BaseDiagnostic"]] = {}


def register_diagnostic(cls: type) -> type:
    """Class decorator. Registers cls under cls.id."""
    if not hasattr(cls, "id") or not cls.id:
        raise AttributeError(f"{cls.__name__} must define a non-empty class attribute 'id'")
    _REGISTRY[cls.id] = cls
    return cls


def get_diagnostic(id: str) -> type["BaseDiagnostic"]:
    if id not in _REGISTRY:
        raise KeyError(
            f"Unknown diagnostic '{id}'. "
            f"Registered: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[id]


def get_by_tag(tag: str) -> list[type["BaseDiagnostic"]]:
    return [cls for cls in _REGISTRY.values()
            if tag in getattr(cls, "tags", [])]


def all_diagnostics() -> list[type["BaseDiagnostic"]]:
    return list(_REGISTRY.values())


def list_diagnostics() -> None:
    """Pretty-print all registered diagnostics."""
    print(f"  {'ID':<6}  {'Tags':<35}  Hypothesis")
    print("  " + "-" * 80)
    for did, cls in sorted(_REGISTRY.items()):
        tags = ", ".join(getattr(cls, "tags", []))
        hyp  = getattr(cls, "hypothesis", "")[:50]
        print(f"  {did:<6}  {tags:<35}  {hyp}")
