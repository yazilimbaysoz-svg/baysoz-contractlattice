# Baysöz Labs ContractLattice

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](pyproject.toml)
[![CI](https://img.shields.io/badge/CI-pytest%20%C2%B7%20ruff%20%C2%B7%20semgrep-brightgreen.svg)](.github/workflows/ci.yml)
[![SARIF 2.1.0](https://img.shields.io/badge/SARIF-2.1.0-purple.svg)](src/baysoz_contractlattice/sarif.py)
[![Baysöz Labs](https://img.shields.io/badge/Maintained%20by-Bays%C3%B6z%20Labs-orange.svg)](mailto:baysozlabs@proton.me)

**Owner:** Baysöz Labs <baysozlabs@proton.me>

Deterministic, offline OpenAPI 3.x semantic breaking-change and contract-drift gate with SARIF CI enforcement. ContractLattice decides whether a candidate API contract is still compatible with the one your SDK consumers, gateways, and clients already compiled against — without network calls, services, or local LLMs.

## Why it exists

Live GitHub mining on 2026-11-26 found recurring, unresolved pain: [OAI/tools.openapis.org#282](https://github.com/OAI/tools.openapis.org/issues/282) is still open ("Add OpenAPI Breaking Change Checker"), while teams across [CandleViewer](https://github.com/CandleViewer/CandleViewer/issues/2638), [InstaNode-dev](https://github.com/InstaNode-dev/api/issues/169), and [qomiralabs](https://github.com/qomiralabs/drefyn/issues/301) are wiring their own breaking-change gates into CI. With FastAPI (105k stars), the OpenAPI Specification (31k stars), and openapi-generator (27k stars) making contracts pervasive, a deterministic gate is infrastructure, not a toy.

See [docs/MARKET_RESEARCH.md](docs/MARKET_RESEARCH.md) for the full evidence and corpus gap analysis.

## Highlights

- **Semantic, not textual:** key order, enum order, `allOf` member order, inline vs `$ref` schemas, and OpenAPI 3.0 `nullable` vs 3.1 type unions are canonicalized — equivalent specs produce zero findings.
- **Deep rule corpus:** operations, parameters, media types, request bodies, success/error responses, response headers, security schemes, OAuth scopes, servers, and component schemas.
- **Context-aware severity:** a tightened request constraint is an error; the same tightening in a response is advisory.
- **Fail-closed input hardening:** duplicate keys, YAML alias bombs, oversized documents, cyclic refs, absolute/network refs, and directory traversal are rejected with exit code 2.
- **Governance that decays:** expiring, path-scoped waivers; expired waivers become errors and unused waivers become notes.
- **CI-native:** deterministic text, JSON, and SARIF 2.1.0 output with stable ordering and exit codes 0/1/2.

## Install

Requires Python 3.13+ and `uv`.

```bash
git clone https://github.com/yazilimbaysoz-svg/baysoz-contractlattice.git
cd baysoz-contractlattice
uv venv
uv pip install -e .
uv pip install pytest
contractlattice --version
```

Runtime dependency: `PyYAML>=6.0.2`. No Docker, database, broker, cloud service, or local model is required.

## Usage

```bash
# CI gate (fails on breaking changes)
contractlattice api-baseline.yaml pr-contract.yaml

# Strict gate: warnings also fail
contractlattice api-baseline.yaml pr-contract.yaml --profile strict --format sarif --out contract.sarif

# Machine-readable report
contractlattice api-baseline.yaml pr-contract.yaml --format json

# Compare every component schema, including unreferenced ones
contractlattice api-baseline.yaml pr-contract.yaml --scope all
```

Exit codes: `0` = pass, `1` = failing findings, `2` = input/policy error.

## Real CLI output

Version and help attribution:

```console
$ contractlattice --version
contractlattice 1.0.0 — Baysöz Labs <baysozlabs@proton.me>

$ contractlattice --help | tail -1
Built by Baysöz Labs <baysozlabs@proton.me>. Version 1.0.0.
```

Equivalent 3.0/3.1 documents (reordered keys, reordered `allOf` and enums) produce no drift:

```console
$ contractlattice tests/fixtures/base.yaml tests/fixtures/safe.yaml
Baysöz Labs ContractLattice — OpenAPI contract compatibility report
attribution: Baysöz Labs <baysozlabs@proton.me>
baseline: tests/fixtures/base.yaml
candidate: tests/fixtures/safe.yaml
profile: balanced

No semantic contract drift detected.

errors=0 warnings=0 notes=0
result: PASS
maintained by Baysöz Labs <baysozlabs@proton.me>
```

Adversarial breaking candidate (excerpt):

```console
$ contractlattice tests/fixtures/base.yaml tests/fixtures/breaking.yaml
Baysöz Labs ContractLattice — OpenAPI contract compatibility report
attribution: Baysöz Labs <baysozlabs@proton.me>
baseline: tests/fixtures/base.yaml
candidate: tests/fixtures/breaking.yaml
profile: balanced

[ERROR  ] OAS-S003 /components/schemas/Widget — required property added: newly required: ['email']
[WARNING] OAS-W005 /components/schemas/Widget/properties/email — property added: email
[ERROR  ] OAS-S006 /components/schemas/Widget/properties/id — format narrowed: uuid -> date-time
[ERROR  ] OAS-S002 /components/schemas/Widget/properties/name — enum value removed: removed values: ['"beta"', '"gamma"']
[ERROR  ] OAS-S004 /components/schemas/Widget/properties/tags — property removed: tags
[ERROR  ] OAS-B012 /components/securitySchemes/oauth — security scheme removed: oauth
...
errors=14 warnings=5 notes=0
result: FAIL
maintained by Baysöz Labs <baysozlabs@proton.me>
```

## Architecture

```
base.yaml ─┐
           ├─> loader ─> Normalizer ─> diff engine ─> policy/waivers ─> renderer ─> exit code
candidate ─┘
```

| Layer | Module | Role |
| --- | --- | --- |
| Input hardening | `loader.py` | Safe YAML/JSON, duplicate keys, size/alias caps, JSON Pointer, path confinement |
| Normalization | `normalize.py` | `$ref` resolution, `allOf` flattening, 3.1 sibling merge, canonical schemas |
| Semantics | `diff.py` | Rule-driven operation/parameter/schema/security diffs with request/response context |
| Governance | `policy.py` | Profiles, expiring waivers, summaries |
| Reporting | `sarif.py`, `cli.py` | SARIF 2.1.0, text, JSON, deterministic ordering |

Full details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [PLAN.md](PLAN.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md).

## Quality gates

```bash
uv venv && uv pip install -e . && uv pip install pytest
uv run pytest -q
ruff check --select E,F,W,S,B .
semgrep --config p/default --error .
```

All four commands report zero defects at v1.0.0.

## License

MIT — Baysöz Labs <baysozlabs@proton.me>. See [LICENSE](LICENSE).
