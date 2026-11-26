# Security Policy — Baysöz Labs ContractLattice

**Owner:** Baysöz Labs <baysozlabs@proton.me>
**Version:** 1.0.0

## Reporting

Report vulnerabilities privately to **baysozlabs@proton.me**. Include the affected version, reproduction inputs, and impact. Please do not open public issues for unpatched vulnerabilities.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.0.x | Yes |

## Trust boundaries

Input OpenAPI documents are untrusted. The CLI is often executed in CI against pull requests, so a malicious specification must not be able to read unrelated files, exhaust memory, or produce nondeterministic verdicts.

## Controls implemented

- `yaml.compose` with `yaml.SafeLoader`; no arbitrary Python object construction.
- Duplicate mapping-key detection prevents parser-differential ambiguities.
- 8 MiB per-document limit, 200,000 expanded-node cap, 100-level nesting cap, and 32-file external-reference cap.
- External `$ref` targets must resolve inside the directory of the initial specification; absolute paths and URLs containing `://` are rejected.
- Cyclic reference chains are rejected before canonicalization.
- All analysis is read-only; the tool never writes to input paths.
- Reports contain no secrets and no raw file contents; only rule IDs, logical pointers, and short messages.
- Static analysis gates (`ruff` with `E,F,W,S,B` and `semgrep --config p/default --error`) run on every change.

## Known limitations

- Only OpenAPI 3.0.x and 3.1.x are accepted; Swagger 2.0 is intentionally rejected.
- Semantic equivalence beyond the modeled rule set (for example, complex `oneOf` algebra) is conservatively reported for manual review via `OAS-W018`.
- Waivers are trusted local policy input; protect waiver files with the same review controls as source code.

## Attribution

Security contact and project ownership: Baysöz Labs <baysozlabs@proton.me>.
