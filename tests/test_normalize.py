"""Normalization tests for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from pathlib import Path

from baysoz_contractlattice.loader import read_document
from baysoz_contractlattice.normalize import Normalizer, canonical_schema, flatten_all_of

from .conftest import check

FIXTURES = Path(__file__).parent / "fixtures"


def test_all_of_flattens_required_and_properties() -> None:
    schema = flatten_all_of({
        "allOf": [
            {"type": "object", "properties": {"id": {"type": "string"}}},
            {"required": ["id"]},
        ]
    })
    check(schema["required"] == ["id"], "required not merged")
    check(schema["properties"]["id"]["type"] == "string", "property not merged")


def test_all_of_conflict_is_preserved() -> None:
    schema = flatten_all_of({
        "allOf": [
            {"type": "object", "properties": {"id": {"type": "string"}}},
            {"properties": {"id": {"type": "integer"}}},
        ]
    })
    check("allOf" in schema, "conflicting allOf must remain explicit")


def test_nullable_normalizes_to_union_type() -> None:
    canonical = canonical_schema({"type": "string", "nullable": True})
    check(canonical["type"] == ["null", "string"], "nullable not normalized")


def test_enum_order_is_canonical() -> None:
    left = canonical_schema({"enum": ["a", "b", "c"]})
    right = canonical_schema({"enum": ["c", "a", "b"]})
    check(left == right, "enum ordering leaked into canonical form")


def test_external_reference_resolves_and_is_marked() -> None:
    path = FIXTURES / "external.yaml"
    document = read_document(path, "external.yaml")
    normalizer = Normalizer(document, path, "external.yaml")
    normalized = normalizer.normalized()
    operation = normalized["operations"][("/v1/shared", "get")]
    response = operation["operation"]["responses"]["200"]
    schema = response["content"]["application/json"]["schema"]
    check(schema["__contract_ref__"] == "Shared", "external ref not marked")
    check(schema["properties"]["value"]["type"] == "string", "external schema not resolved")
    check("Shared" in normalizer.reachable, "external schema not tracked as reachable")


def test_openapi_31_ref_siblings_merge() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "siblings", "version": "1"},
        "paths": {},
        "components": {
            "schemas": {
                "Thing": {"type": "object", "properties": {"a": {"type": "string"}}},
                "Extended": {
                    "$ref": "#/components/schemas/Thing",
                    "description": "Baysöz Labs <baysozlabs@proton.me>",
                    "properties": {"b": {"type": "integer"}},
                },
            }
        },
    }
    normalizer = Normalizer(document, FIXTURES / "base.yaml", "inline.yaml")
    schemas = normalizer.normalized()["schemas"]
    check("a" in schemas["Extended"]["properties"], "base properties lost")
    check("b" in schemas["Extended"]["properties"], "sibling properties lost")
    check("description" in schemas["Extended"], "sibling annotation lost")
