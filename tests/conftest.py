"""Shared test helpers for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from typing import Any


def check(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)
