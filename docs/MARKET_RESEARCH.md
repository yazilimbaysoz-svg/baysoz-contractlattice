# Market Research — Baysöz Labs ContractLattice

**Project:** `baysoz-contractlattice`
**Owner:** Baysöz Labs <baysozlabs@proton.me>
**Research date:** 2026-11-26
**Decision:** Build a deterministic, offline, policy-driven OpenAPI 3.x semantic contract gate with SARIF CI enforcement.

## 1. Evidence from live GitHub mining

Commands executed with the authenticated `gh` CLI on 2026-11-26:

- `gh search repos "OpenAPI" --stars ">2000" --sort stars`
- `gh search repos "SBOM" --stars ">1000" --sort stars`
- `gh search issues "openapi breaking change" --limit 12`
- Local corpus inspection: `/home/runner/work/_temp/existing-repos.json` (39 prior Baysöz Labs projects).

### High-star ecosystem gravity

| Repository | Stars (live result) | Relevance |
| --- | ---: | --- |
| `fastapi/fastapi` | 105,043 | OpenAPI is the default contract surface for modern Python services; schema changes are published automatically on every deploy. |
| `OAI/OpenAPI-Specification` | 31,335 | The normative spec is large, permits many equivalent encodings, and evolves (3.0 vs 3.1 `$ref` sibling semantics). |
| `swagger-api/swagger-ui` | 29,093 | Generated client/server ecosystems consume the contract as a hard API boundary. |
| `OpenAPITools/openapi-generator` | 26,875 | SDK generation turns subtle schema changes into compile-time breakages for downstream users. |
| `Redocly/redoc` | 26,030 | Contract documents are published artifacts, not internal notes. |
| `apache/apisix`, `grpc-ecosystem/grpc-gateway` | 17,375 / 20,018 | Gateways and proxies enforce contracts at runtime, so drift between spec and deployed behavior is costly. |
| `aquasecurity/trivy`, `anchore/syft`, `ossf/cve-bin-tool` | 39,752 / 9,969 / 1,815 | The adjacent supply-chain tooling market already treats machine-readable artifacts and SARIF gates as first-class CI inputs. |

### Live pain-point signal (open and recently closed issues)

- [OAI/tools.openapis.org#282 — "Add OpenAPI Breaking Change Checker"](https://github.com/OAI/tools.openapis.org/issues/282), opened 2026-08-11, **still open**: the specification's own tooling working area still lacks a canonical breaking-change checker.
- [CandleViewer/CandleViewer#2638](https://github.com/CandleViewer/CandleViewer/issues/2638), opened 2026-10-15: teams are wiring breaking-change diffs into `ci(infra-devops)` contract jobs.
- [InstaNode-dev/api#169](https://github.com/InstaNode-dev/api/issues/169), opened 2026-05-29: a team had to **re-introduce** a deleted `oasdiff` workflow — the ad-hoc CI integration was not durable.
- [qomiralabs/drefyn#301](https://github.com/qomiralabs/drefyn/issues/301), opened 2026-11-04: "refuse breaking changes to the v1 API".
- Recent closed issues (2026-11-04 → 2026-11-22) from `LumenRoute`, `Glubiz`, `RicardoRB`, `MustacheCase`, `peczenyj`, and `MTGVim` all request the same gate, proving this is a recurring platform team need rather than a one-off.

Interpretation: the **demand** is proven, but the **integration story is fragmented** — teams bolt on diff tools that are often online, chatty, version-sensitive, or hard to make deterministic in CI.

## 2. Why the existing Baysöz Labs corpus does not cover this

The 39-repository corpus is dense in runtime and infrastructure diagnostics: `baysoz-admissioncel`, `baysoz-netpol-oracle`, `baysoz-routegate`, `baysoz-disruption-oracle`, `baysoz-composelattice`, `baysoz-provenancegate`, `baysoz-actionlock`, `baysoz-queryoracle`, `baysoz-burnlattice`, `baysoz-ssrfcanon`, `baysoz-desyncforge`, `bolaforge`, `baysoz-gqlcostgate`, and others.

Specific gaps:

- `bolaforge` generates **authorization test plans** from OpenAPI; it does not decide whether a schema or operation change breaks an existing client.
- `baysoz-provenancegate` verifies **build provenance**; it does not inspect API compatibility.
- `baysoz-admissioncel` and `baysoz-routegate` analyze **cluster policy and routing**, not contract documents.
- `envpair`/`envlens` compare configuration values, not typed interface schemas with JSON Pointer references and composition.
- No prior project implements a **JSON Schema/OpenAPI semantic differ** with `$ref` resolution, `allOf` normalization, 3.0/3.1 `nullable` handling, context-aware severity, expiring waivers, and SARIF output.

`baysoz-contractlattice` is therefore additive, not redundant.

## 3. What "deep" means here

A string or JSON-tree diff is not sufficient. Equivalent contracts can be written with different key order, different enum order, reordered `allOf` members, inline vs referenced schemas, `nullable: true` vs `type: [string, "null"]`, and OpenAPI 3.0 vs 3.1 reference-sibling rules. Conversely, a one-line change can break every generated SDK (adding a required property). ContractLattice:

1. Parses YAML/JSON safely with duplicate-key, alias-expansion, and byte-size limits.
2. Confines all `$ref` targets to the specification root directory; rejects network refs and cycles.
3. Resolves internal and local external refs, flattens composable `allOf` intersections, and canonicalizes types, enums, constraints, defaults, discriminators, and composition.
4. Runs rule-based semantic diffs with **request vs response context-aware severity**.
5. Applies expiring, path-scoped waivers so exceptions decay instead of becoming permanent debt.
6. Emits stable text/JSON/SARIF 2.1.0 reports with deterministic ordering.

## 4. Why Python 3.13 + `uv` + PyYAML

- Python 3.13 is already present in the target environment and gives modern typing without runtime cost.
- `uv` provides reproducible, fast editable installs; the project has exactly one runtime dependency (`PyYAML`).
- No Docker, databases, message queues, network calls, or local LLMs: the gate runs in a GitHub Actions job or a laptop in milliseconds.
- SARIF is the same interchange format used by mature security tooling, so results land in GitHub code scanning without a bespoke UI.

## 5. Success criteria

- Zero findings between semantically equivalent 3.0 and 3.1 documents.
- All breaking fixtures produce specific, pointer-addressed rule IDs.
- Adversarial inputs (duplicate keys, cycles, path traversal, unsupported versions) fail closed with exit code 2.
- `pytest`, `ruff --select E,F,W,S,B`, and `semgrep --config p/default --error` all report zero defects.
