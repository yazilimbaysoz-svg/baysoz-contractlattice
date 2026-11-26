"""Deterministic SARIF 2.1.0 emitter for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .model import Finding

LEVELS = {"error": "error", "warning": "warning", "note": "note"}
ATTRIBUTION = "Baysöz Labs <baysozlabs@proton.me>"


def to_sarif(findings: list[Finding], base: Path, candidate: Path) -> dict[str, Any]:
    rules = []
    for rule_id in sorted({item.rule_id for item in findings}):
        example = next(item for item in findings if item.rule_id == rule_id)
        rules.append({
            "id": rule_id,
            "name": rule_id.replace("-", "_"),
            "shortDescription": {"text": example.title},
            "fullDescription": {"text": f"{example.detail} — {ATTRIBUTION}"},
            "defaultConfiguration": {"level": LEVELS[example.severity]},
        })
    results = []
    for finding in findings:
        results.append({
            "ruleId": finding.rule_id,
            "level": LEVELS[finding.severity],
            "message": {"text": f"{finding.title}: {finding.detail}"},
            "logicalLocations": [{
                "fullyQualifiedName": finding.pointer,
                "kind": "openapi-contract-location",
            }],
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": candidate.name},
                }
            }],
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Baysöz Labs ContractLattice",
                    "version": __version__,
                    "informationUri": "https://github.com/yazilimbaysoz-svg/baysoz-contractlattice",
                    "fullDescription": {"text": f"Offline OpenAPI contract gate by {ATTRIBUTION}"},
                    "rules": rules,
                }
            },
            "artifacts": [
                {"location": {"uri": base.name}},
                {"location": {"uri": candidate.name}},
            ],
            "results": results,
            "properties": {
                "attribution": ATTRIBUTION,
                "base": str(base),
                "candidate": str(candidate),
            },
        }],
    }
