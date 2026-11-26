"""Semantic OpenAPI contract differ for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import SpecError, read_document
from .model import Finding
from .normalize import (
    FORMAT_RANK,
    HIGHER_IS_TIGHTER,
    LOWER_IS_TIGHTER,
    Normalizer,
    canonical_schema,
    stable,
)

SUCCESS_PREFIX = "2"


def _escape(token: Any) -> str:
    return str(token).replace("~", "~0").replace("/", "~1")


def pointer(*tokens: Any) -> str:
    return "/" + "/".join(_escape(token) for token in tokens)


def _as_number(value: Any) -> float | None:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    if isinstance(parsed, bool) or not isinstance(parsed, (int, float)):
        return None
    return float(parsed)


def _add(
    findings: list[Finding],
    rule_id: str,
    severity: str,
    title: str,
    detail: str,
    location: str,
) -> None:
    findings.append(Finding(rule_id, severity, title, detail, location))


def diff_schema(
    before: Any,
    after: Any,
    location: str,
    context: str = "shared",
) -> list[Finding]:
    return diff_canonical(canonical_schema(before), canonical_schema(after), location, context)


def diff_canonical(
    old: dict[str, Any],
    new: dict[str, Any],
    location: str,
    context: str,
) -> list[Finding]:
    findings: list[Finding] = []
    response = context == "response"

    old_types = set(old.get("type", []))
    new_types = set(new.get("type", []))
    if old_types != new_types:
        widening = old_types.issubset(new_types)
        _add(
            findings,
            "OAS-W011" if widening else "OAS-S001",
            "warning" if widening else "error",
            "schema type widened" if widening else "schema type narrowed",
            f"type {sorted(old_types)} became {sorted(new_types)}",
            location,
        )

    old_enum = set(old.get("enum", []))
    new_enum = set(new.get("enum", []))
    removed_enum = old_enum - new_enum
    added_enum = new_enum - old_enum
    if removed_enum:
        _add(
            findings,
            "OAS-S002",
            "error",
            "enum value removed",
            f"removed values: {sorted(removed_enum)}",
            location,
        )
    if added_enum:
        _add(
            findings,
            "OAS-W004",
            "warning",
            "enum value added",
            f"added values: {sorted(added_enum)}",
            location,
        )

    if "const" in old and old["const"] != new.get("const"):
        _add(findings, "OAS-S008", "error", "constant value changed",
             f"{old['const']} became {new.get('const')}", location)

    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))
    added_required = new_required - old_required
    removed_required = old_required - new_required
    if added_required:
        _add(
            findings,
            "OAS-S003",
            "warning" if response else "error",
            "required property added",
            f"newly required: {sorted(added_required)}",
            location,
        )
    if removed_required:
        _add(
            findings,
            "OAS-W010",
            "warning",
            "required property removed",
            f"no longer required: {sorted(removed_required)}",
            location,
        )

    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    for name in sorted(set(old_props) - set(new_props)):
        _add(findings, "OAS-S004", "error", "property removed", name,
             f"{location}/properties/{_escape(name)}")
    for name in sorted(set(new_props) - set(old_props)):
        _add(findings, "OAS-W005", "warning", "property added", name,
             f"{location}/properties/{_escape(name)}")
    for name in sorted(set(old_props) & set(new_props)):
        findings.extend(
            diff_canonical(
                old_props[name],
                new_props[name],
                f"{location}/properties/{_escape(name)}",
                context,
            )
        )

    for key in HIGHER_IS_TIGHTER:
        old_value = _as_number(old.get(key))
        new_value = _as_number(new.get(key))
        if old_value is not None and new_value is not None and new_value > old_value:
            _add(findings, "OAS-W006" if response else "OAS-S005",
                 "warning" if response else "error", "constraint tightened",
                 f"{key}: {old_value} -> {new_value}", location)
        elif old_value is not None and new_value is not None and new_value < old_value:
            _add(findings, "OAS-W006", "warning", "constraint loosened",
                 f"{key}: {old_value} -> {new_value}", location)
    for key in LOWER_IS_TIGHTER:
        old_value = _as_number(old.get(key))
        new_value = _as_number(new.get(key))
        if old_value is not None and new_value is not None and new_value < old_value:
            _add(findings, "OAS-W006" if response else "OAS-S005",
                 "warning" if response else "error", "constraint tightened",
                 f"{key}: {old_value} -> {new_value}", location)
        elif old_value is not None and new_value is not None and new_value > old_value:
            _add(findings, "OAS-W006", "warning", "constraint loosened",
                 f"{key}: {old_value} -> {new_value}", location)

    old_format = old.get("format")
    new_format = new.get("format")
    if old_format != new_format:
        old_rank = FORMAT_RANK.get(old_format)
        new_rank = FORMAT_RANK.get(new_format)
        if new_format is None:
            _add(findings, "OAS-W011", "warning", "format removed",
                 f"{old_format} -> unspecified", location)
        elif old_rank is not None and new_rank is not None and new_rank >= old_rank:
            _add(findings, "OAS-W011", "warning", "format widened",
                 f"{old_format} -> {new_format}", location)
        else:
            _add(findings, "OAS-S006", "warning" if response else "error",
                 "format narrowed", f"{old_format} -> {new_format}", location)

    if "pattern" in old and old["pattern"] != new.get("pattern"):
        _add(findings, "OAS-W017" if response else "OAS-S011",
             "warning" if response else "error", "pattern changed",
             f"{old['pattern']} -> {new.get('pattern')}", location)

    old_additional = old.get("additionalProperties")
    new_additional = new.get("additionalProperties")
    if old_additional != new_additional:
        closed = new_additional == {"boolean_schema": False}
        opened = old_additional == {"boolean_schema": False} and new_additional != {"boolean_schema": False}
        if closed:
            _add(findings, "OAS-S007", "error", "additional properties closed",
                 "previously accepted unknown properties are now rejected", location)
        elif opened:
            _add(findings, "OAS-W005", "warning", "additional properties opened",
                 "unknown properties are now accepted", location)
        elif isinstance(old_additional, dict) and isinstance(new_additional, dict):
            findings.extend(diff_canonical(
                old_additional, new_additional,
                f"{location}/additionalProperties", context,
            ))

    for key in ("items", "not"):
        if key in old or key in new:
            findings.extend(diff_canonical(
                old.get(key, {}), new.get(key, {}),
                f"{location}/{key}", context,
            ))

    old_variants = set(stable(old.get(key)) for key in ("oneOf", "anyOf", "allOf") if key in old)
    new_variants = set(stable(new.get(key)) for key in ("oneOf", "anyOf", "allOf") if key in new)
    if old_variants - new_variants:
        _add(findings, "OAS-S009", "error", "composition variant removed",
             f"removed {len(old_variants - new_variants)} variant(s)", location)
    if new_variants - old_variants:
        _add(findings, "OAS-W004", "warning", "composition variant added",
             f"added {len(new_variants - old_variants)} variant(s)", location)

    for key in ("readOnly", "writeOnly"):
        if old.get(key) != new.get(key):
            _add(findings, "OAS-S010", "error", f"{key} changed",
                 f"{old.get(key)} -> {new.get(key)}", location)

    old_disc = old.get("discriminator", {})
    new_disc = new.get("discriminator", {})
    if old_disc and old_disc != new_disc:
        _add(findings, "OAS-B014", "error", "discriminator changed",
             f"{stable(old_disc)} -> {stable(new_disc)}", location)

    if "default" in old and old["default"] != new.get("default"):
        _add(findings, "OAS-W007", "warning", "default changed",
             f"{old['default']} -> {new.get('default')}", location)

    if old.get("other") != new.get("other"):
        _add(findings, "OAS-W018", "warning", "unmodelled keyword changed",
             "review the semantic impact manually", location)
    return findings


def _diff_content(before: Any, after: Any, location: str, context: str) -> list[Finding]:
    findings: list[Finding] = []
    old = before if isinstance(before, dict) else {}
    new = after if isinstance(after, dict) else {}
    for media in sorted(set(old) - set(new)):
        _add(findings, "OAS-B008", "error", "media type removed", media,
             f"{location}/{_escape(media)}")
    for media in sorted(set(new) - set(old)):
        _add(findings, "OAS-W013", "warning", "media type added", media,
             f"{location}/{_escape(media)}")
    for media in sorted(set(old) & set(new)):
        old_schema = old[media].get("schema") if isinstance(old[media], dict) else None
        new_schema = new[media].get("schema") if isinstance(new[media], dict) else None
        if old_schema is not None and new_schema is None:
            _add(findings, "OAS-B017", "error", "schema removed from media type",
                 media, f"{location}/{_escape(media)}/schema")
        elif old_schema is None and new_schema is not None:
            _add(findings, "OAS-W019", "warning", "schema added to media type",
                 media, f"{location}/{_escape(media)}/schema")
        elif old_schema is not None and new_schema is not None:
            findings.extend(diff_schema(
                old_schema, new_schema, f"{location}/{_escape(media)}/schema", context
            ))
    return findings


def _diff_parameters(before: list[Any], after: list[Any], location: str) -> list[Finding]:
    findings: list[Finding] = []
    old: dict[tuple[str, str], dict[str, Any]] = {}
    new: dict[tuple[str, str], dict[str, Any]] = {}
    for collection, target in ((before, old), (after, new)):
        for item in collection:
            if isinstance(item, dict):
                target[(str(item.get("name")), str(item.get("in")))] = item
    for key in sorted(set(old) - set(new)):
        _add(findings, "OAS-B003", "error", "parameter removed",
             f"{key[1]} parameter {key[0]}", f"{location}/{_escape(key[0])}:{_escape(key[1])}")
    for key in sorted(set(new) - set(old)):
        required = new[key].get("required") is True or key[1] == "path"
        _add(findings, "OAS-B004" if required else "OAS-W002",
             "error" if required else "warning",
             "required parameter added" if required else "optional parameter added",
             f"{key[1]} parameter {key[0]}", f"{location}/{_escape(key[0])}:{_escape(key[1])}")
    for key in sorted(set(old) & set(new)):
        previous, current = old[key], new[key]
        here = f"{location}/{_escape(key[0])}:{_escape(key[1])}"
        was_required = previous.get("required") is True or key[1] == "path"
        now_required = current.get("required") is True or key[1] == "path"
        if now_required and not was_required:
            _add(findings, "OAS-B005", "error", "parameter became required",
                 f"{key[1]} parameter {key[0]}", here)
        elif was_required and not now_required:
            _add(findings, "OAS-W010", "warning", "parameter became optional",
                 f"{key[1]} parameter {key[0]}", here)
        for keyword in ("style", "explode", "allowReserved", "allowEmptyValue"):
            if previous.get(keyword) != current.get(keyword):
                _add(findings, "OAS-B015", "error", "parameter serialization changed",
                     f"{keyword}: {previous.get(keyword)} -> {current.get(keyword)}", here)
        old_schema = previous.get("schema")
        new_schema = current.get("schema")
        if old_schema is not None and new_schema is not None:
            findings.extend(diff_schema(old_schema, new_schema, f"{here}/schema", "request"))
    return findings


def _security_sets(requirements: Any) -> set[frozenset[tuple[str, tuple[str, ...]]]]:
    if not isinstance(requirements, list):
        return set()
    result: set[frozenset[tuple[str, tuple[str, ...]]]] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        pairs = []
        for scheme, scopes in sorted(requirement.items()):
            scope_tuple = tuple(sorted(scopes)) if isinstance(scopes, list) else ()
            pairs.append((str(scheme), scope_tuple))
        result.add(frozenset(pairs))
    return result


def _requirement_text(requirement: frozenset[tuple[str, tuple[str, ...]]]) -> str:
    return stable(sorted((scheme, list(scopes)) for scheme, scopes in requirement))


def _diff_security(before: Any, after: Any, location: str) -> list[Finding]:
    findings: list[Finding] = []
    old = _security_sets(before)
    new = _security_sets(after)
    for requirement in sorted(new - old, key=_requirement_text):
        if not requirement:
            continue
        _add(findings, "OAS-B011", "error", "new security requirement",
             _requirement_text(requirement), location)
    for requirement in sorted(old - new, key=_requirement_text):
        if requirement:
            _add(findings, "OAS-W009", "warning", "security requirement removed",
                 _requirement_text(requirement), location)
    return findings


def _diff_responses(before: Any, after: Any, location: str) -> list[Finding]:
    findings: list[Finding] = []
    old = before if isinstance(before, dict) else {}
    new = after if isinstance(after, dict) else {}
    for code in sorted(set(old) - set(new)):
        severity = "error" if code.startswith(SUCCESS_PREFIX) else "warning"
        rule = "OAS-B009" if severity == "error" else "OAS-W012"
        _add(findings, rule, severity, "response removed", code, f"{location}/{_escape(code)}")
    for code in sorted(set(new) - set(old)):
        _add(findings, "OAS-W003", "warning", "response added", code,
             f"{location}/{_escape(code)}")
    for code in sorted(set(old) & set(new)):
        here = f"{location}/{_escape(code)}"
        old_response = old[code]
        new_response = new[code]
        if not isinstance(old_response, dict) or not isinstance(new_response, dict):
            continue
        findings.extend(_diff_content(old_response.get("content"), new_response.get("content"),
                                      f"{here}/content", "response"))
        old_headers = old_response.get("headers", {})
        new_headers = new_response.get("headers", {})
        if not isinstance(old_headers, dict):
            old_headers = {}
        if not isinstance(new_headers, dict):
            new_headers = {}
        for name in sorted(set(old_headers) - set(new_headers)):
            _add(findings, "OAS-B010", "error", "response header removed", name,
                 f"{here}/headers/{_escape(name)}")
        for name in sorted(set(new_headers) & set(old_headers)):
            previous = old_headers[name]
            current = new_headers[name]
            if isinstance(previous, dict) and isinstance(current, dict):
                old_schema = previous.get("schema")
                new_schema = current.get("schema")
                if old_schema is not None and new_schema is not None:
                    findings.extend(diff_schema(old_schema, new_schema,
                                                f"{here}/headers/{_escape(name)}/schema",
                                                "response"))
    return findings


def _diff_operation(before: dict[str, Any], after: dict[str, Any], location: str) -> list[Finding]:
    findings: list[Finding] = []
    old = before["operation"]
    new = after["operation"]
    old_id = old.get("operationId")
    new_id = new.get("operationId")
    if old_id != new_id:
        _add(findings, "OAS-B002", "error", "operationId changed",
             f"{old_id} -> {new_id}", f"{location}/operationId")
    findings.extend(_diff_parameters(before["parameters"], after["parameters"],
                                     f"{location}/parameters"))
    old_body = old.get("requestBody")
    new_body = new.get("requestBody")
    if old_body is not None and new_body is None:
        _add(findings, "OAS-B007", "error", "request body removed", "request body is gone",
             f"{location}/requestBody")
    elif old_body is None and new_body is not None:
        _add(findings, "OAS-W019", "warning", "request body added", "request body is new",
             f"{location}/requestBody")
    elif isinstance(old_body, dict) and isinstance(new_body, dict):
        if old_body.get("required") is not True and new_body.get("required") is True:
            _add(findings, "OAS-B016", "error", "request body became required",
                 "clients must now send a body", f"{location}/requestBody/required")
        findings.extend(_diff_content(old_body.get("content"), new_body.get("content"),
                                      f"{location}/requestBody/content", "request"))
    findings.extend(_diff_responses(old.get("responses"), new.get("responses"),
                                    f"{location}/responses"))
    findings.extend(_diff_security(before["security"], after["security"],
                                   f"{location}/security"))
    return findings


def _diff_security_schemes(before: Any, after: Any) -> list[Finding]:
    findings: list[Finding] = []
    old = before if isinstance(before, dict) else {}
    new = after if isinstance(after, dict) else {}
    for name in sorted(set(old) - set(new)):
        _add(findings, "OAS-B012", "error", "security scheme removed", name,
             pointer("components", "securitySchemes", name))
    for name in sorted(set(old) & set(new)):
        previous = old[name] if isinstance(old[name], dict) else {}
        current = new[name] if isinstance(new[name], dict) else {}
        here = pointer("components", "securitySchemes", name)
        for keyword in ("type", "scheme", "name", "in"):
            if previous.get(keyword) != current.get(keyword):
                _add(findings, "OAS-B013", "error", "security scheme definition changed",
                     f"{keyword}: {previous.get(keyword)} -> {current.get(keyword)}",
                     f"{here}/{keyword}")
        old_flows = previous.get("flows", {})
        new_flows = current.get("flows", {})
        if not isinstance(old_flows, dict):
            old_flows = {}
        if not isinstance(new_flows, dict):
            new_flows = {}
        for flow in sorted(set(old_flows) - set(new_flows)):
            _add(findings, "OAS-B012", "error", "OAuth flow removed", flow,
                 f"{here}/flows/{_escape(flow)}")
        for flow in sorted(set(old_flows) & set(new_flows)):
            old_scopes = old_flows[flow].get("scopes", {}) if isinstance(old_flows[flow], dict) else {}
            new_scopes = new_flows[flow].get("scopes", {}) if isinstance(new_flows[flow], dict) else {}
            for scope in sorted(set(old_scopes) - set(new_scopes)):
                _add(findings, "OAS-B013", "error", "OAuth scope removed",
                     f"{flow}: {scope}", f"{here}/flows/{_escape(flow)}/scopes")
    return findings


def _diff_servers(before: Any, after: Any) -> list[Finding]:
    findings: list[Finding] = []
    def urls(servers: Any) -> set[str]:
        if not isinstance(servers, list):
            return set()
        return {
            str(server.get("url")) for server in servers if isinstance(server, dict) and "url" in server
        }
    for url in sorted(urls(before) - urls(after)):
        _add(findings, "OAS-W008", "warning", "server URL removed", url,
             pointer("servers"))
    return findings


def compare_documents(
    base_document: dict[str, Any],
    candidate_document: dict[str, Any],
    base_path: Path,
    candidate_path: Path,
    scope: str = "api",
) -> list[Finding]:
    if scope not in ("api", "all"):
        raise SpecError("scope must be 'api' or 'all'")
    base_normalizer = Normalizer(base_document, base_path, str(base_path))
    candidate_normalizer = Normalizer(candidate_document, candidate_path, str(candidate_path))
    base = base_normalizer.normalized()
    candidate = candidate_normalizer.normalized()
    findings: list[Finding] = []
    base_ops = base["operations"]
    candidate_ops = candidate["operations"]
    for key in sorted(set(base_ops) | set(candidate_ops)):
        location = pointer("paths", key[0], key[1])
        if key not in candidate_ops:
            _add(findings, "OAS-B001", "error", "operation removed",
                 f"{key[1].upper()} {key[0]}", location)
        elif key not in base_ops:
            _add(findings, "OAS-W001", "warning", "operation added",
                 f"{key[1].upper()} {key[0]}", location)
        else:
            findings.extend(_diff_operation(base_ops[key], candidate_ops[key], location))

    if scope == "all":
        names = set(base["schemas"]) | set(candidate["schemas"])
    else:
        names = base_normalizer.reachable | candidate_normalizer.reachable
    for name in sorted(names):
        location = pointer("components", "schemas", name)
        if name not in candidate["schemas"]:
            _add(findings, "OAS-B018", "error", "component schema removed", name, location)
        elif name not in base["schemas"]:
            _add(findings, "OAS-W020", "warning", "component schema added", name, location)
        else:
            findings.extend(diff_schema(base["schemas"][name], candidate["schemas"][name],
                                        location, "shared"))

    findings.extend(_diff_security(base["security"], candidate["security"],
                                   pointer("security")))
    findings.extend(_diff_security_schemes(base["security_schemes"],
                                           candidate["security_schemes"]))
    findings.extend(_diff_servers(base["servers"], candidate["servers"]))
    return sorted(findings, key=lambda item: (item.pointer, item.rule_id, item.title))


def compare_files(base_path: Path, candidate_path: Path, scope: str = "api") -> list[Finding]:
    base = read_document(base_path, str(base_path))
    candidate = read_document(candidate_path, str(candidate_path))
    return compare_documents(base, candidate, base_path.resolve(), candidate_path.resolve(), scope)
