"""Semantic diff tests for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from baysoz_contractlattice.diff import compare_files, diff_schema
from baysoz_contractlattice.loader import SpecError

from .conftest import check

FIXTURES = Path(__file__).parent / "fixtures"
BASE = FIXTURES / "base.yaml"
SAFE = FIXTURES / "safe.yaml"
BREAKING = FIXTURES / "breaking.yaml"


def rule_ids(findings: object) -> set[str]:
    return {item.rule_id for item in findings}


def test_semantically_identical_spec_has_no_findings() -> None:
    findings = compare_files(BASE, SAFE)
    check(not findings, f"unexpected drift: {[item.to_dict() for item in findings]}")


def test_breaking_spec_is_detected() -> None:
    findings = compare_files(BASE, BREAKING)
    rules = rule_ids(findings)
    expected = {
        "OAS-B001", "OAS-B002", "OAS-B004", "OAS-B005", "OAS-B008", "OAS-B012",
        "OAS-W008", "OAS-W012", "OAS-S002", "OAS-S003", "OAS-S004", "OAS-S006",
    }
    check(expected.issubset(rules), f"missing rules: {sorted(expected - rules)}")
    check(all(item.pointer for item in findings), "finding without a pointer")


def _mutated_base(tmp_path: Path, mutate: Callable[[dict[str, Any]], None], name: str) -> Path:
    document = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    mutate(document)
    candidate = tmp_path / name
    candidate.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    return candidate


def test_removed_parameter_is_error(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["paths"]["/v1/widgets"].pop("parameters")
    candidate = _mutated_base(tmp_path, mutate, "no_param.yaml")
    findings = compare_files(BASE, candidate)
    check(any(item.rule_id == "OAS-B003" for item in findings),
          "parameter removal not reported")


def test_removed_request_body_is_error(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["paths"]["/v1/widgets"]["post"].pop("requestBody")
    candidate = _mutated_base(tmp_path, mutate, "no_body.yaml")
    findings = compare_files(BASE, candidate)
    check(any(item.rule_id == "OAS-B007" for item in findings),
          "request body removal not reported")


def test_removed_success_response_is_error(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["paths"]["/v1/widgets"]["get"]["responses"].pop("200")
    candidate = _mutated_base(tmp_path, mutate, "no_success.yaml")
    findings = compare_files(BASE, candidate)
    check(any(item.rule_id == "OAS-B009" for item in findings),
          "success response removal not reported")


def test_response_context_downgrades_constraint_tightening() -> None:
    findings = diff_schema(
        {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1}}},
        {"type": "object", "properties": {"n": {"type": "integer", "minimum": 9}}},
        "/responses/200/content/application~1json/schema",
        "response",
    )
    check(rule_ids(findings) == {"OAS-W006"}, "response tightening should be advisory")


def test_request_context_flags_constraint_tightening() -> None:
    findings = diff_schema(
        {"type": "integer", "maximum": 100},
        {"type": "integer", "maximum": 10},
        "/requestBody/schema",
        "request",
    )
    check(rule_ids(findings) == {"OAS-S005"}, "request tightening must be an error")


def test_scope_all_includes_unreferenced_schema(tmp_path: Path) -> None:
    document = yaml.safe_load(SAFE.read_text(encoding="utf-8"))
    document["components"]["schemas"]["Orphan"] = {
        "type": "string",
        "description": "Baysöz Labs <baysozlabs@proton.me>",
    }
    candidate = tmp_path / "with_orphan.yaml"
    candidate.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    api_findings = compare_files(BASE, candidate, "api")
    all_findings = compare_files(BASE, candidate, "all")
    check(not api_findings, "unreferenced schema leaked into API scope")
    check(any(item.rule_id == "OAS-W020" and item.pointer.endswith("/Orphan")
              for item in all_findings), "scope all did not report the orphan schema")


def test_invalid_scope_rejected() -> None:
    with pytest.raises(SpecError, match="scope must be"):
        compare_files(BASE, SAFE, "invalid")


def test_cyclic_spec_rejected_by_compare() -> None:
    with pytest.raises(SpecError, match="cyclic reference"):
        compare_files(BASE, FIXTURES / "cyclic.yaml")
