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
- `make work-package` - print one evidence-selected agent work package with skill readiness as JSON.
- `make workflow-resume` - select one evidence-derived next action with a stale-snapshot guard as JSON.
- `make product-plan` - print product structuring plan as JSON.
- `make design-plan` - print design derivation plan as JSON.
- `make implementation-plan` - print Ready implementation task execution plan as JSON.
- `make implementation-run-check` - preflight the selected implementation task without claiming or executing it.
- `make check-env` - inventory local governance tools as JSON.
- `make repair-env-check` - preview environment repair without writing files.
- `make project-env-plan` - print reviewed project runtime tool registration plan as JSON.
- `bin/governance project-env repair . --tool-id <tool-id> --check --json` - preview one registered reviewed-command repair before requesting approval.
