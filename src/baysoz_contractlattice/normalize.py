"""Reference resolution and semantic canonicalization for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import (
    MAX_EXTERNAL_FILES,
    MAX_POINTER_DEPTH,
    SpecError,
    contained_path,
    read_document,
    resolve_pointer,
)

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
ANNOTATIONS = {"title", "description", "example", "examples", "externalDocs", "$schema", "xml"}
HANDLED_KEYS = {
    "type",
    "nullable",
    "enum",
    "const",
    "properties",
    "required",
    "items",
    "prefixItems",
    "additionalProperties",
    "patternProperties",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "format",
    "default",
    "readOnly",
    "writeOnly",
    "deprecated",
    "discriminator",
    "__contract_ref__",
    "minLength",
    "maxLength",
    "pattern",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    *ANNOTATIONS,
}
LOWER_IS_TIGHTER = ("maxLength", "maxItems", "maxProperties", "maximum", "exclusiveMaximum")
HIGHER_IS_TIGHTER = ("minLength", "minItems", "minProperties", "minimum", "exclusiveMinimum")
FORMAT_RANK = {
    "int32": 0,
    "int64": 1,
    "date": 0,
    "date-time": 1,
}


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def flatten_all_of(schema: Any, depth: int = 0) -> Any:
    if depth > MAX_POINTER_DEPTH:
        raise SpecError("allOf nesting exceeds the safety limit")
    if not isinstance(schema, dict) or "allOf" not in schema:
        return schema
    members = schema.get("allOf")
    if not isinstance(members, list):
        raise SpecError("allOf must be an array")
    flattened = [flatten_all_of(member, depth + 1) for member in members]
    merged: dict[str, Any] = {}
    conflicts: set[str] = set()
    for member in flattened:
        if not isinstance(member, dict):
            return {**{k: v for k, v in schema.items() if k != "allOf"}, "allOf": flattened}
        for key, value in member.items():
            if key in ("properties", "required"):
                if key not in merged:
                    merged[key] = {} if key == "properties" else []
                if key == "properties":
                    if not isinstance(value, dict):
                        conflicts.add(key)
                        continue
                    for name, prop in value.items():
                        if name in merged[key]:
                            conflicts.add(f"property:{name}")
                        else:
                            merged[key][name] = prop
                else:
                    if not isinstance(value, list):
                        conflicts.add(key)
                        continue
                    merged[key] = sorted({*merged[key], *value})
            elif key in merged and stable(merged[key]) != stable(value):
                conflicts.add(key)
            else:
                merged[key] = value
    if conflicts:
        residual = {k: v for k, v in merged.items() if k == "properties" or k == "required"}
        residual["allOf"] = flattened
        return residual
    return merged


def canonical_schema(schema: Any, depth: int = 0) -> Any:
    if depth > MAX_POINTER_DEPTH:
        raise SpecError("schema nesting exceeds the safety limit")
    if isinstance(schema, bool):
        return {"boolean_schema": schema}
    if not isinstance(schema, dict):
        return {"literal": stable(schema)}
    if isinstance(schema.get("__contract_ref__"), str):
        return {"component_ref": schema["__contract_ref__"]}
    schema = flatten_all_of(schema)
    if not isinstance(schema, dict):
        return canonical_schema(schema, depth + 1)
    result: dict[str, Any] = {}
    declared = schema.get("type")
    if isinstance(declared, str):
        types = [declared]
    elif isinstance(declared, list) and all(isinstance(item, str) for item in declared):
        types = list(declared)
    else:
        types = []
    if schema.get("nullable") is True and "null" not in types:
        types.append("null")
    if types:
        result["type"] = sorted(set(types))
    if "enum" in schema:
        values = schema["enum"]
        if not isinstance(values, list):
            raise SpecError("enum must be an array")
        result["enum"] = sorted((stable(item) for item in values))
    if "const" in schema:
        result["const"] = stable(schema["const"])
    if "format" in schema:
        result["format"] = str(schema["format"]).lower()
    if "default" in schema:
        result["default"] = stable(schema["default"])
    if "properties" in schema:
        properties = schema["properties"]
        if not isinstance(properties, dict):
            raise SpecError("properties must be a mapping")
        result["properties"] = {
            key: canonical_schema(value, depth + 1) for key, value in sorted(properties.items())
        }
    if "required" in schema:
        required = schema["required"]
        if not isinstance(required, list):
            raise SpecError("required must be an array")
        result["required"] = sorted(set(required))
    for key in ("items", "not", "additionalProperties"):
        if key in schema:
            result[key] = canonical_schema(schema[key], depth + 1)
    if "prefixItems" in schema:
        items = schema["prefixItems"]
        if not isinstance(items, list):
            raise SpecError("prefixItems must be an array")
        result["prefixItems"] = [canonical_schema(item, depth + 1) for item in items]
    if "patternProperties" in schema:
        result["patternProperties"] = {
            key: canonical_schema(value, depth + 1)
            for key, value in sorted(schema["patternProperties"].items())
        }
    for key in ("oneOf", "anyOf", "allOf"):
        if key in schema:
            variants = schema[key]
            if not isinstance(variants, list):
                raise SpecError(f"{key} must be an array")
            result[key] = sorted(
                (canonical_schema(item, depth + 1) for item in variants), key=stable
            )
    for key in (
        *LOWER_IS_TIGHTER,
        *HIGHER_IS_TIGHTER,
        "multipleOf",
        "pattern",
        "uniqueItems",
        "readOnly",
        "writeOnly",
        "deprecated",
    ):
        if key in schema:
            result[key] = stable(schema[key])
    if "discriminator" in schema and isinstance(schema["discriminator"], dict):
        disc = schema["discriminator"]
        result["discriminator"] = {
            "propertyName": disc.get("propertyName"),
            "mapping": stable(disc.get("mapping", {})),
        }
    others = {
        key: stable(value)
        for key, value in sorted(schema.items())
        if key not in HANDLED_KEYS and not str(key).startswith("x-")
    }
    if others:
        result["other"] = others
    return result


class Normalizer:
    """Resolve refs and reduce a specification to comparable semantic structures."""

    def __init__(
        self,
        document: dict[str, Any],
        root: Path,
        label: str,
        cache: dict[Path, dict[str, Any]] | None = None,
    ) -> None:
        self.document = document
        self.root = root
        self.label = label
        self.cache = cache if cache is not None else {root: document}
        self.reachable: set[str] = set()

    def resolve(
        self,
        value: Any,
        document: dict[str, Any],
        source: Path,
        label: str,
        stack: frozenset[tuple[str, str]],
        depth: int = 0,
    ) -> Any:
        if depth > MAX_POINTER_DEPTH:
            raise SpecError(f"{label}: reference chain exceeds the safety limit")
        if isinstance(value, list):
            return [
                self.resolve(item, document, source, label, stack, depth + 1) for item in value
            ]
        if not isinstance(value, dict):
            return value
        ref = value.get("$ref")
        if not isinstance(ref, str):
            return {
                key: self.resolve(item, document, source, label, stack, depth + 1)
                for key, item in value.items()
            }
        if "#" in ref:
            file_part, pointer = ref.split("#", 1)
        else:
            file_part, pointer = "", ref
        if file_part:
            if "://" in file_part or file_part.startswith("/"):
                raise SpecError(f"{label}: external network or absolute references are forbidden")
            target_file = contained_path(self.root, source.parent / file_part, label)
            if target_file not in self.cache:
                if len(self.cache) >= MAX_EXTERNAL_FILES:
                    raise SpecError(f"{label}: too many external specification files")
                self.cache[target_file] = read_document(target_file, str(target_file))
            target_doc = self.cache[target_file]
            target_label = str(target_file)
        else:
            target_file = source
            target_doc = document
            target_label = label
        key = (str(target_file), pointer)
        if key in stack:
            raise SpecError(f"{label}: cyclic reference: {ref}")
        if pointer.startswith("/components/schemas/"):
            self.reachable.add(pointer[len("/components/schemas/") :])
        target = resolve_pointer(target_doc, pointer, target_label)
        resolved = self.resolve(
            target, target_doc, target_file, target_label, stack | {key}, depth + 1
        )
        if pointer.startswith("/components/schemas/") and isinstance(resolved, dict):
            resolved = {**resolved, "__contract_ref__": pointer[len("/components/schemas/") :]}
        siblings = {k: v for k, v in value.items() if k != "$ref"}
        if not siblings:
            return resolved
        if not self.document.get("openapi", "").startswith("3.1"):
            return resolved
        merged = dict(resolved) if isinstance(resolved, dict) else {}
        for name, item in siblings.items():
            value_item = self.resolve(item, document, source, label, stack, depth + 1)
            if name in merged and isinstance(merged[name], dict) and isinstance(value_item, dict):
                merged[name] = {**merged[name], **value_item}
            else:
                merged[name] = value_item
        return merged

    def normalized(self) -> dict[str, Any]:
        resolved = self.resolve(self.document, self.document, self.root, self.label, frozenset())
        paths = resolved.get("paths", {})
        if not isinstance(paths, dict):
            raise SpecError(f"{self.label}: paths must be a mapping")
        operations: dict[tuple[str, str], dict[str, Any]] = {}
        for path, path_item in sorted(paths.items()):
            if not isinstance(path_item, dict):
                raise SpecError(f"{self.label}: path item must be a mapping: {path}")
            shared_params = path_item.get("parameters", [])
            if not isinstance(shared_params, list):
                raise SpecError(f"{self.label}: parameters must be an array: {path}")
            shared_security = path_item.get("security", resolved.get("security", []))
            for method in HTTP_METHODS:
                if method not in path_item:
                    continue
                operation = path_item[method]
                if not isinstance(operation, dict):
                    raise SpecError(f"{self.label}: operation must be a mapping: {method} {path}")
                params = list(shared_params)
                overrides = {
                    (item.get("name"), item.get("in")): item
                    for item in operation.get("parameters", [])
                    if isinstance(item, dict)
                }
                params = [
                    item
                    for item in params
                    if isinstance(item, dict)
                    and (item.get("name"), item.get("in")) not in overrides
                ]
                params.extend(operation.get("parameters", []))
                operations[(path, method)] = {
                    "operation": operation,
                    "parameters": params,
                    "security": operation.get("security", shared_security),
                }
        components = resolved.get("components", {})
        if not isinstance(components, dict):
            raise SpecError(f"{self.label}: components must be a mapping")
        schemas = components.get("schemas", {})
        if not isinstance(schemas, dict):
            raise SpecError(f"{self.label}: component schemas must be a mapping")
        security_schemes = components.get("securitySchemes", {})
        if not isinstance(security_schemes, dict):
            raise SpecError(f"{self.label}: security schemes must be a mapping")
        servers = resolved.get("servers", [])
        if not isinstance(servers, list):
            raise SpecError(f"{self.label}: servers must be an array")
        return {
            "operations": operations,
            "schemas": schemas,
            "security_schemes": security_schemes,
            "security": resolved.get("security", []),
            "servers": servers,
        }
