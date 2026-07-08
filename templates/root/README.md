# Project Name

One-sentence project summary.

## Start Here

- Project overview: `SPEC.md`
- Product source: `docs/product/core/PRD.md`
- Documentation index: `docs/README.md`
- Governance rules: `AGENTS.md`
- Open questions: `docs/unresolved.md`

## Development

- `make verify-governance` - run governance verification and update verification state.
- `make verify-check` - run read-only JSON verification without updating state.
- `make governance-status` - print workflow state as JSON.
- `make workflow-plan` - print current workflow route plus active queue and skill summaries as JSON.
- `make implementation-plan` - print Ready implementation task execution plan as JSON.
- `make check-env` - inventory local governance tools as JSON.
- `make repair-env-check` - preview environment repair without writing files.
