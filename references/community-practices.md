# Community Practice References

Use these as calibration sources, not rigid templates.

| Practice | Use in this workflow |
| --- | --- |
| GitHub community health files | root collaboration and safety files |
| Diataxis | reader-oriented navigation and doc purpose separation |
| Backstage TechDocs | docs-as-code operating model |
| OpenAPI Specification | machine-readable API contracts |
| PostgreSQL DDL constraints and transactions | relational integrity, concurrency, and schema semantics |
| Evolutionary Database Design | backward-compatible schema evolution and expand-contract migration planning |
| C4 Model | architecture view layering; see `references/architecture-methods.md` |
| arc42 | architecture completeness checklist; see `references/architecture-methods.md` |
| ADR / MADR | decision records |
| OpenSSF Best Practices | quality and security baseline thinking |
| SLSA provenance | explicit source identity, immutable revision, and integrity evidence for external authority skills |
| NIST Secure Software Development Framework (SP 800-218) | reviewed third-party component provenance and controlled acquisition |
| OWASP ASVS | application security verification calibration |
| OWASP API Security Top 10 | API abuse-case and authorization calibration |
| Google SRE Book and Workbook | source-backed SLIs/SLOs, error-budget policy, and multi-window burn-rate calibration; see `references/backend-operability-checklist.md` |
| OpenTelemetry | logs, metrics, and traces for operability evidence |

Authority skill source-lock calibration:

- SLSA provenance: `https://slsa.dev/spec/v1.2/provenance`
- NIST SP 800-218 SSDF: `https://csrc.nist.gov/pubs/sp/800/218/final`
- OpenSSF Scorecard pinned dependencies: `https://github.com/ossf/scorecard/blob/main/docs/checks.md#pinned-dependencies`
