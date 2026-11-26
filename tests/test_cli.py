"""End-to-end CLI tests for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from baysoz_contractlattice.cli import main

from .conftest import check

FIXTURES = Path(__file__).parent / "fixtures"
BASE = FIXTURES / "base.yaml"
SAFE = FIXTURES / "safe.yaml"
BREAKING = FIXTURES / "breaking.yaml"


def run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def test_version_output_has_attribution() -> None:
    with pytest.raises(SystemExit) as exc:
        with redirect_stdout(io.StringIO()) as stdout:
            main(["--version"])
    check(exc.value.code == 0, "version should exit successfully")
    check("Baysöz Labs <baysozlabs@proton.me>" in stdout.getvalue(), "attribution missing")


def test_help_output_has_attribution() -> None:
    with pytest.raises(SystemExit) as exc:
        with redirect_stdout(io.StringIO()) as stdout:
            main(["--help"])
    check(exc.value.code == 0, "help should exit successfully")
    check("Baysöz Labs <baysozlabs@proton.me>" in stdout.getvalue(), "attribution missing")


def test_text_report_passes_on_equivalent_specs() -> None:
    code, output, error = run([str(BASE), str(SAFE)])
    check(code == 0 and not error, f"unexpected failure: {error}")
    check("result: PASS" in output, "PASS missing from output")
    check("Baysöz Labs <baysozlabs@proton.me>" in output, "attribution missing")


def test_text_report_fails_on_breaking_specs() -> None:
    code, output, _ = run([str(BASE), str(BREAKING)])
    check(code == 1, "breaking spec must fail")
    check("OAS-B001" in output, "removed operation rule missing")
    check("result: FAIL" in output, "FAIL missing from output")


def test_json_report_is_machine_readable() -> None:
    code, output, _ = run([str(BASE), str(BREAKING), "--format", "json"])
    check(code == 1, "breaking spec must fail in JSON mode")
    report = json.loads(output)
    check(report["result"] == "FAIL", "wrong JSON verdict")
    check(report["attribution"] == "Baysöz Labs <baysozlabs@proton.me>", "attribution missing")
    check(report["summary"]["errors"] > 0, "no errors reported")


def test_sarif_report_and_out_file(tmp_path: Path) -> None:
    target = tmp_path / "report.sarif"
    code, output, _ = run([str(BASE), str(BREAKING), "--format", "sarif", "--out", str(target)])
    check(code == 1 and not output, "explicit output file should suppress stdout")
    report = json.loads(target.read_text(encoding="utf-8"))
    check(report["version"] == "2.1.0", "wrong SARIF version")
    check(len(report["runs"][0]["results"]) > 0, "SARIF has no results")


def test_advisory_profile_never_fails() -> None:
    code, output, _ = run([str(BASE), str(BREAKING), "--profile", "advisory"])
    check(code == 0, "advisory profile must exit zero")
    check("result: PASS" in output, "advisory verdict wrong")


def test_waivers_can_suppress_findings(tmp_path: Path) -> None:
    waivers = tmp_path / "waivers.json"
    waivers.write_text(
        json.dumps([{"rule": "OAS-B001", "pointer": "/paths/~1v1~1widgets~1{id}/get",
                     "reason": "deprecated endpoint"}]),
        encoding="utf-8",
    )
    code, output, _ = run([str(BASE), str(BREAKING), "--waivers", str(waivers)])
    check(code == 1, "other breaking changes still fail")
    check("OAS-B001" not in output, "waived finding still present")


def test_missing_file_is_input_error() -> None:
    code, _, error = run([str(BASE), "/nonexistent/spec.yaml"])
    check(code == 2, "missing file must be an input error")
    check("Baysöz Labs <baysozlabs@proton.me>" in error, "attribution missing from error")
