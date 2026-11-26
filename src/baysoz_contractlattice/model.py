"""Finding model for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from dataclasses import dataclass

SEVERITIES = ("error", "warning", "note")


@dataclass(frozen=True, order=True)
class Finding:
    rule_id: str
    severity: str
    title: str
    detail: str
    pointer: str
    source: str = "openapi"

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity: {self.severity}")

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "pointer": self.pointer,
            "source": self.source,
        }
