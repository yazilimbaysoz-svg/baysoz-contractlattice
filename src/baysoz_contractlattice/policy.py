"""Policy profiles and expiring waivers for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .loader import SpecError
from .model import Finding

PROFILES = ("strict", "balanced", "advisory")
FAILING_SEVERITIES = {
    "strict": frozenset({"error", "warning"}),
    "balanced": frozenset({"error"}),
    "advisory": frozenset(),
}


@dataclass(frozen=True)
class Waiver:
    rule: str
    pointer: str
    expires: date | None
    reason: str


def _parse_date(value: Any, label: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SpecError(f"{label}: expires must be a YYYY-MM-DD string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SpecError(f"{label}: invalid expiry date: {value}") from exc


def load_waivers(path: Path) -> list[Waiver]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SpecError(f"cannot read waivers: {exc}") from exc
    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise SpecError(f"invalid waiver JSON: {exc}") from exc
    if not isinstance(raw, list) or len(raw) > 1000:
        raise SpecError("waivers file must be an array with at most 1000 entries")
    waivers: list[Waiver] = []
    for index, item in enumerate(raw):
        label = f"waiver[{index}]"
        if not isinstance(item, dict):
            raise SpecError(f"{label}: must be an object")
        rule = item.get("rule")
        pointer = item.get("pointer")
        reason = item.get("reason", "")
        if not isinstance(rule, str) or not rule or not isinstance(pointer, str) or not pointer:
            raise SpecError(f"{label}: rule and pointer are required strings")
        if not isinstance(reason, str):
            raise SpecError(f"{label}: reason must be a string")
        waivers.append(
            Waiver(rule=rule, pointer=pointer, expires=_parse_date(item.get("expires"), label),
                   reason=reason)
        )
    return waivers


def _matches(waiver: Waiver, finding: Finding) -> bool:
    if waiver.rule not in ("*", finding.rule_id):
        return False
    return finding.pointer == waiver.pointer or finding.pointer.startswith(waiver.pointer + "/")


def apply_waivers(
    findings: list[Finding],
    waivers: list[Waiver],
    today: date | None = None,
) -> list[Finding]:
    current = today or datetime.now(timezone.utc).date()
    result: list[Finding] = []
    used: set[int] = set()
    for finding in findings:
        matching = [index for index, waiver in enumerate(waivers) if _matches(waiver, finding)]
        valid = [index for index in matching if waivers[index].expires is None
                 or waivers[index].expires >= current]
        if valid:
            used.update(valid)
            continue
        if matching:
            result.append(Finding(
                "OAS-G002", "error", "waiver expired",
                f"waiver for {finding.rule_id} at {finding.pointer} is no longer valid",
                finding.pointer,
            ))
        else:
            result.append(finding)
    for index, waiver in enumerate(waivers):
        if index not in used and (waiver.expires is None or waiver.expires >= current):
            result.append(Finding(
                "OAS-G003", "note", "unused waiver",
                f"no finding matched {waiver.rule} at {waiver.pointer}", waiver.pointer,
            ))
    return sorted(result, key=lambda item: (item.pointer, item.rule_id, item.title))


def failing_findings(findings: list[Finding], profile: str) -> list[Finding]:
    if profile not in FAILING_SEVERITIES:
        raise SpecError(f"unknown profile: {profile}")
    severities = FAILING_SEVERITIES[profile]
    return [finding for finding in findings if finding.severity in severities]


def summarize(findings: list[Finding]) -> dict[str, int]:
    return {
        "errors": sum(1 for item in findings if item.severity == "error"),
        "warnings": sum(1 for item in findings if item.severity == "warning"),
        "notes": sum(1 for item in findings if item.severity == "note"),
    }
