# Plan — Baysöz Labs ContractLattice

**Owner:** Baysöz Labs <baysozlabs@proton.me>
**Status:** v1.0.0 released after full quality-gate and tribunal validation.

## Delivered in v1.0.0

- [x] Market research grounded in live `gh search repos` and `gh search issues` evidence.
- [x] Hardened YAML/JSON loader with duplicate-key, alias-bomb, size, and path-confinement controls.
- [x] Internal and local external `$ref` resolution with cycle detection and OpenAPI 3.1 sibling merging.
- [x] Semantic canonicalization of types, enums, required fields, constraints, defaults, composition, and discriminators.
- [x] Operation, parameter, request-body, response, header, security, server, and component diffs.
- [x] Request/response context-aware severity.
- [x] Policy profiles and expiring, path-scoped waivers.
- [x] Text, JSON, and SARIF 2.1.0 renderers with stable ordering.
- [x] Adversarial test corpus and end-to-end CLI tests.
- [x] CI quality gates: `pytest`, `ruff --select E,F,W,S,B`, `semgrep --config p/default --error`.
- [x] Supreme Grand Jury Tribunal: live adversarial execution and unanimous pass.

## Next milestones

### v1.1 — Contract coverage intelligence

- Detect operations present in implementation traces but absent from the contract.
- Add `--baseline-digest` pinning to prevent silent baseline substitution in CI.
- Expand the rule corpus with header-parameter and cookie-parameter semantics.

### v1.2 — Multi-document federation

- Support `$ref` bundles with explicit allow-listed roots and digest verification.
- Add cross-document operation ID collision detection for federated gateways.

### v1.3 — CI ergonomics

- GitHub Actions composite action with inline SARIF annotations.
- Machine-readable rule catalog export for docs and policy UI generation.

## Explicitly out of scope

- Network calls, remote registries, runtime probing, local LLMs, and heavyweight services.
- Replacing `oasdiff`, Spectral, or contract test frameworks; ContractLattice is the deterministic CI *gate* that composes with them.
