"""Loader hardening tests for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baysoz_contractlattice.loader import SpecError, read_document
from baysoz_contractlattice.normalize import Normalizer

from .conftest import check

FIXTURES = Path(__file__).parent / "fixtures"


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(SpecError, match="duplicate mapping key"):
        read_document(FIXTURES / "duplicate.yaml", "duplicate.yaml")


def test_swagger_2_rejected(tmp_path: Path) -> None:
    path = tmp_path / "swagger2.yaml"
    path.write_text(
        "swagger: '2.0'\ninfo:\n  title: legacy\n  version: '1'\npaths: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(SpecError, match="only OpenAPI 3"):
        read_document(path, "swagger2.yaml")


def test_external_reference_confined_to_root() -> None:
    document = read_document(FIXTURES / "traversal.yaml", "traversal.yaml")
    with pytest.raises(SpecError, match="escapes the specification root"):
        Normalizer(document, FIXTURES / "traversal.yaml", "traversal.yaml").normalized()


def test_cyclic_reference_rejected() -> None:
    document = read_document(FIXTURES / "cyclic.yaml", "cyclic.yaml")
    with pytest.raises(SpecError, match="cyclic reference"):
        Normalizer(document, FIXTURES / "cyclic.yaml", "cyclic.yaml").normalized()


def test_non_mapping_root_rejected(tmp_path: Path) -> None:
    path = tmp_path / "scalar.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(SpecError, match="root must be a mapping"):
        read_document(path, "scalar.yaml")


def test_valid_document_loads() -> None:
    document = read_document(FIXTURES / "base.yaml", "base.yaml")
    check(document["openapi"] == "3.1.0", "expected 3.1.0 document")
    check("Baysöz Labs" in document["info"]["description"], "attribution missing")
