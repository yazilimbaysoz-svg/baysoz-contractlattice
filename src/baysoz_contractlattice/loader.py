"""Hardened OpenAPI loader for Baysöz Labs ContractLattice.

Maintained by Baysöz Labs <baysozlabs@proton.me>.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_NODES = 200_000
MAX_EXTERNAL_FILES = 32
MAX_POINTER_DEPTH = 100


class SpecError(Exception):
    """Raised for malformed, hostile, or unsupported specifications."""


def _mapping_size(node: Any, cache: dict[int, int], depth: int = 0) -> int:
    if depth > MAX_POINTER_DEPTH:
        raise SpecError("specification nesting exceeds the safety limit")
    if id(node) in cache:
        return cache[id(node)]
    if isinstance(node, yaml.MappingNode):
        total = 1
        seen: set[str] = set()
        for key_node, value_node in node.value:
            label = getattr(key_node, "value", "<complex>")
            if not isinstance(label, str):
                raise SpecError("mapping keys must be scalar strings")
            if label in seen:
                raise SpecError(f"duplicate mapping key: {label}")
            seen.add(label)
            total += _mapping_size(value_node, cache, depth + 1)
    elif isinstance(node, yaml.SequenceNode):
        total = 1 + sum(_mapping_size(item, cache, depth + 1) for item in node.value)
    else:
        total = 1
    cache[id(node)] = total
    return total


def _validate_text(text: str, label: str) -> None:
    if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise SpecError(f"{label}: document exceeds {MAX_DOCUMENT_BYTES} bytes")
    try:
        composed = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise SpecError(f"{label}: invalid YAML/JSON: {exc}") from exc
    if composed is None:
        raise SpecError(f"{label}: empty document")
    if _mapping_size(composed, {}) > MAX_EXPANDED_NODES:
        raise SpecError(f"{label}: alias expansion exceeds {MAX_EXPANDED_NODES} nodes")


def read_document(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SpecError(f"{label}: cannot read document: {exc}") from exc
    _validate_text(text, label)
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError(f"{label}: invalid YAML/JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise SpecError(f"{label}: root must be a mapping")
    version = document.get("openapi")
    if not isinstance(version, str) or not (version.startswith("3.0") or version.startswith("3.1")):
        raise SpecError(f"{label}: only OpenAPI 3.0.x and 3.1.x are supported")
    return document


def resolve_pointer(document: Any, pointer: str, label: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise SpecError(f"{label}: invalid JSON pointer: {pointer}")
    current = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise SpecError(f"{label}: unresolved reference: {pointer}")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise SpecError(f"{label}: unresolved index in reference: {pointer}")
            current = current[int(token)]
        else:
            raise SpecError(f"{label}: reference descends into a scalar: {pointer}")
    return current


def contained_path(root: Path, candidate: Path, label: str) -> Path:
    resolved = candidate.resolve()
    boundary = root.parent if root.is_file() else root
    try:
        resolved.relative_to(boundary)
    except ValueError as exc:
        raise SpecError(f"{label}: reference escapes the specification root directory") from exc
    return resolved
