# Architecture — Baysöz Labs ContractLattice

**Owner:** Baysöz Labs <baysozlabs@proton.me>
**Version:** 1.0.0

## Purpose

ContractLattice answers one question deterministically: *does a candidate OpenAPI 3.x document remain compatible with the contract its consumers already compiled against?* It answers offline, without network access, services, or model inference.

## Pipeline

```
base.yaml ─┐
           ├─> loader ─> Normalizer ─> diff engine ─> policy/waivers ─> renderer ─> exit code
candidate ─┘
```

1. **`loader.py`** — `yaml.compose` validation (duplicate keys, alias expansion cap, byte cap) followed by `yaml.safe_load`; rejects non-3.x documents and out-of-root refs.
2. **`normalize.py`** — resolves `$ref` (internal and local external), tracks reachable component schemas, merges OpenAPI 3.1 ref siblings, flattens non-conflicting `allOf`, and produces canonical schema maps. Because canonicalization emits `{"component_ref": name}` at reference sites, changes to a shared component are reported once at its definition rather than duplicated at every usage.
3. **`diff.py`** — compares operations by `(path, method)`, parameters by `(name, in)`, media types, response codes, headers, server URLs, security requirements, security schemes, OAuth scopes, and component schemas. Schema rules are context-aware: a tightened request constraint is an error; the same tightening in a response is advisory.
4. **`policy.py`** — profiles (`strict` fails errors + warnings, `balanced` fails errors, `advisory` never fails) and expiring path-scoped waivers. Expired waivers become errors; unused waivers become notes.
5. **`sarif.py`** — stable SARIF 2.1.0 with rule metadata, logical pointer locations, and Baysöz Labs attribution.
6. **`cli.py`** — argument parsing, report rendering (`text`, `json`, `sarif`), output redirection, and exit codes.

## Module map

| Module | Responsibility |
| --- | --- |
| `src/baysoz_contractlattice/model.py` | Immutable `Finding` records and severity validation |
| `src/baysoz_contractlattice/loader.py` | Hardened document reading and JSON Pointer resolution |
| `src/baysoz_contractlattice/normalize.py` | Reference resolution and semantic canonicalization |
| `src/baysoz_contractlattice/diff.py` | Rule-driven semantic differ |
| `src/baysoz_contractlattice/policy.py` | Profiles, waivers, summaries |
| `src/baysoz_contractlattice/sarif.py` | SARIF emitter |
| `src/baysoz_contractlattice/cli.py` | Public CLI surface |

## Invariants

- **Determinism:** all sets are sorted before emission; no timestamps, hashes, or randomized iteration appear in reports.
- **Fail closed:** malformed, cyclic, escaping, or unsupported documents raise `SpecError`; the CLI exits `2`.
- **No false equivalence:** key order, enum order, `allOf` member order, and 3.0 `nullable` vs 3.1 type unions are normalized; genuinely different semantics are never silently merged.
- **No duplicated noise:** a referenced schema change is reported at the component definition, not once per endpoint.
- **Attribution:** every public artifact and all CLI output identify Baysöz Labs <baysozlabs@proton.me>.

## Rule taxonomy

| Prefix | Meaning |
| --- | --- |
| `OAS-B*` | Breaking change (removed operations, required additions, removed responses, security changes) |
| `OAS-S*` | Schema incompatibility (type narrowing, enum removal, tighter constraints, closed additional properties) |
| `OAS-W*` | Advisory drift (additions, loosenings, server changes, removed error responses) |
| `OAS-G*` | Governance (expired or unused waivers) |

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No failing findings under the selected profile |
| `1` | At least one failing finding |
| `2` | Input, policy, or configuration error |

## Threat model summary

Untrusted specs are treated as hostile input: oversized documents, YAML alias bombs, duplicate keys, deep recursion, cyclic refs, absolute/network refs, and directory traversal are rejected before semantic analysis. See `SECURITY.md`.

## Non-goals

- Runtime API testing, fuzzing, or authorization test generation (`bolaforge` covers that space).
- SBOM generation, image scanning, or cluster admission control (other Baysöz Labs projects cover those spaces).
- Automatic mutation of specifications; ContractLattice is always read-only.
