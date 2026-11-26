"""Policy and waiver tests for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from baysoz_contractlattice.loader import SpecError
from baysoz_contractlattice.model import Finding
from baysoz_contractlattice.policy import (
    apply_waivers,
    failing_findings,
    load_waivers,
    summarize,
)

from .conftest import check

FINDING = Finding("OAS-S003", "error", "required property added", "email",
                  "/components/schemas/Widget")


def test_waiver_suppresses_matching_finding(tmp_path: Path) -> None:
    path = tmp_path / "waivers.json"
    path.write_text(
        '[{"rule":"OAS-S003","pointer":"/components/schemas/Widget",'
        '"expires":"2099-01-01","reason":"planned rollout"}]',
        encoding="utf-8",
    )
    waivers = load_waivers(path)
    check(not apply_waivers([FINDING], waivers, date(2026, 11, 26)), "waiver did not apply")


def test_expired_waiver_becomes_error(tmp_path: Path) -> None:
    path = tmp_path / "waivers.json"
    path.write_text(
        '[{"rule":"OAS-S003","pointer":"/components/schemas/Widget",'
        '"expires":"2026-01-01","reason":"expired"}]',
        encoding="utf-8",
    )
    waivers = load_waivers(path)
    result = apply_waivers([FINDING], waivers, date(2026, 11, 26))
    check([item.rule_id for item in result] == ["OAS-G002"], "expiry not enforced")


def test_unused_waiver_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "waivers.json"
    path.write_text(
        '[{"rule":"OAS-B999","pointer":"/paths","reason":"unused"}]',
        encoding="utf-8",
    )
    result = apply_waivers([FINDING], load_waivers(path), date(2026, 11, 26))
    check(any(item.rule_id == "OAS-G003" for item in result), "unused waiver not reported")


def test_invalid_waiver_rejected(tmp_path: Path) -> None:
    path = tmp_path / "waivers.json"
    path.write_text('[{"rule":"x"}]', encoding="utf-8")
    with pytest.raises(SpecError, match="pointer are required"):
        load_waivers(path)


def test_profiles_and_summary() -> None:
    warning = Finding("OAS-W005", "warning", "property added", "x", "/x")
    note = Finding("OAS-G003", "note", "unused waiver", "x", "/x")
    findings = [FINDING, warning, note]
    check(len(failing_findings(findings, "strict")) == 2, "strict profile must fail warnings")
    check(len(failing_findings(findings, "balanced")) == 1, "balanced profile must fail errors")
    check(not failing_findings(findings, "advisory"), "advisory profile must not fail")
    check(summarize(findings) == {"errors": 1, "warnings": 1, "notes": 1},
          "summary counters are wrong")
