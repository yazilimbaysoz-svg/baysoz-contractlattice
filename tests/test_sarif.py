"""SARIF emitter tests for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from pathlib import Path

from baysoz_contractlattice.model import Finding
from baysoz_contractlattice.sarif import ATTRIBUTION, to_sarif

from .conftest import check


def test_sarif_structure_and_attribution() -> None:
    findings = [
        Finding("OAS-S003", "error", "required property added", "email", "/components/schemas/Widget"),
        Finding("OAS-W005", "warning", "property added", "note", "/paths/x"),
    ]
    report = to_sarif(findings, Path("base.yaml"), Path("candidate.yaml"))
    check(report["version"] == "2.1.0", "wrong SARIF version")
    run = report["runs"][0]
    check(run["tool"]["driver"]["name"] == "Baysöz Labs ContractLattice", "tool name missing")
    check(len(run["results"]) == 2, "wrong result count")
    check(len(run["tool"]["driver"]["rules"]) == 2, "wrong rule count")
    check(run["results"][0]["level"] == "error", "wrong level")
    check(ATTRIBUTION in run["properties"]["attribution"], "attribution missing")
    check(run["results"][0]["logicalLocations"][0]["fullyQualifiedName"]
          == "/components/schemas/Widget", "pointer missing")
