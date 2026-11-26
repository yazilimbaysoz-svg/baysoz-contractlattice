"""Command-line interface for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .diff import compare_files
from .loader import SpecError
from .model import Finding
from .policy import PROFILES, apply_waivers, failing_findings, load_waivers, summarize
from .sarif import ATTRIBUTION, to_sarif

PROGRAM = "contractlattice"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description=(
            "Offline OpenAPI 3.x semantic breaking-change and contract-drift gate "
            "with deterministic SARIF CI enforcement."
        ),
        epilog=f"Built by Baysöz Labs <baysozlabs@proton.me>. Version {__version__}.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("base", type=Path, help="baseline OpenAPI 3.x YAML or JSON file")
    parser.add_argument("candidate", type=Path, help="candidate OpenAPI 3.x YAML or JSON file")
    parser.add_argument("--profile", choices=PROFILES, default="balanced",
                        help="fail-on severity profile")
    parser.add_argument("--format", choices=("text", "json", "sarif"), default="text",
                        help="report format")
    parser.add_argument("--scope", choices=("api", "all"), default="api",
                        help="compare reachable API schemas or every component schema")
    parser.add_argument("--waivers", type=Path, help="JSON waiver file with expiring entries")
    parser.add_argument("--out", type=Path, help="write the report to a file")
    parser.add_argument("--version", action="version",
                        version=f"{PROGRAM} {__version__} — {ATTRIBUTION}")
    return parser


def render_text(
    findings: list[Finding],
    report: dict[str, int],
    profile: str,
    base: Path,
    candidate: Path,
    passed: bool,
) -> str:
    lines = [
        "Baysöz Labs ContractLattice — OpenAPI contract compatibility report",
        f"attribution: {ATTRIBUTION}",
        f"baseline: {base}",
        f"candidate: {candidate}",
        f"profile: {profile}",
        "",
    ]
    if not findings:
        lines.append("No semantic contract drift detected.")
    for finding in findings:
        lines.append(
            f"[{finding.severity.upper():7}] {finding.rule_id} {finding.pointer} — "
            f"{finding.title}: {finding.detail}"
        )
    lines.extend([
        "",
        f"errors={report['errors']} warnings={report['warnings']} notes={report['notes']}",
        f"result: {'PASS' if passed else 'FAIL'}",
        f"maintained by {ATTRIBUTION}",
    ])
    return "\n".join(lines) + "\n"


def build_report(
    base: Path,
    candidate: Path,
    profile: str,
    scope: str,
    waivers_path: Path | None,
) -> tuple[list[Finding], dict[str, Any], bool]:
    findings = compare_files(base, candidate, scope)
    waivers = load_waivers(waivers_path) if waivers_path else []
    findings = apply_waivers(findings, waivers)
    report: dict[str, Any] = {
        "tool": "Baysöz Labs ContractLattice",
        "version": __version__,
        "attribution": ATTRIBUTION,
        "profile": profile,
        "scope": scope,
        "base": str(base),
        "candidate": str(candidate),
        "summary": summarize(findings),
        "findings": [item.to_dict() for item in findings],
    }
    blocking = failing_findings(findings, profile)
    report["result"] = "PASS" if not blocking else "FAIL"
    report["blocking"] = len(blocking)
    return findings, report, not blocking


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        findings, report, passed = build_report(
            args.base, args.candidate, args.profile, args.scope, args.waivers
        )
        if args.format == "text":
            output = render_text(findings, report["summary"], args.profile,
                                 args.base, args.candidate, passed)
        elif args.format == "json":
            output = json.dumps(report, indent=2, sort_keys=True) + "\n"
        else:
            output = json.dumps(to_sarif(findings, args.base, args.candidate),
                                indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.write_text(output, encoding="utf-8")
        elif output:
            sys.stdout.write(output)
    except (SpecError, OSError, ValueError) as exc:
        sys.stderr.write(f"{PROGRAM}: error: {exc} — {ATTRIBUTION}\n")
        return 2
    return 0 if passed else 1
