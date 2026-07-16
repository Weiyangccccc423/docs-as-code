# Implementation Execution Checklist

Use this checklist when an implementation agent starts, updates, verifies, or completes one `TASK-NNN` item that is `Ready` or already claimed as `In Progress`.

Calibrate execution against DORA small-batch integration and test automation, Google Engineering Practices code-review discipline, SLSA build-integrity expectations, and OpenSSF dependency-risk signals. Keep execution local and evidence-based: every behavior change should be traceable to repository Markdown, code, tests, or a recorded blocker.

## Task Intake

- Is exactly one `Ready` or `In Progress` `TASK-NNN` selected from `docs/development/02-task-board.md`?
- Before first code edit, was exactly one `Ready` `TASK-NNN` claimed as `In Progress`?
- If the task was `Ready`, did the agent run `implementation start --task TASK-NNN --json` and apply only the returned safe `In Progress` status update before editing code?
- Does the task link existing local Product, Design, API, Acceptance, and Verification sources before any code is edited?
- Is the matching `A-NNN` acceptance criterion defined in a product acceptance chapter and mapped in `docs/tests/02-acceptance-matrix.md`?
- Has the agent read the target-local `docs/agent-workflow/task-handoff.md` when present?

Reference: `https://google.github.io/eng-practices/review/developer/`

## Scope Control

- Are modified files limited to the task goal, allowed modules, tests, docs, and generated artifacts named by the handoff or source docs?
- Are product, design, API, data, and security assumptions taken from local Markdown instead of invented during coding?
- Are missing requirements, conflicting sources, unavailable credentials, or unsafe dependency changes registered in `docs/unresolved.md` instead of silently guessed?
- Is unrelated cleanup deferred unless it is required to make the selected task pass verification?

Reference: `https://google.github.io/eng-practices/review/developer/small-cls.html`

## Implementation Loop

- Has the agent inspected existing code, tests, build files, and local conventions before changing implementation?
- Are changes made in small coherent steps with tests or checks run close to the changed surface?
- Are generated clients, schemas, migrations, fixtures, snapshots, or lockfiles changed only when the task scope and repo tooling require them?
- Are compatibility notes, migration ordering, rollback expectations, and operational behavior updated when the code changes those contracts?

Reference: `https://dora.dev/capabilities/trunk-based-development/`

## Verification Execution

- Is each task verification command registered with structured `Argv` and `Cwd` in `docs/agent-workflow/command-contract.md`?
- Are exact task commands selected by preferring target-local `local_commands[].argv` when a machine-readable payload already provides them?
- Was `implementation verify --task TASK-NNN --command command-name --check --json` run before execution, with no registered task-command execution or evidence writes during preflight?
- Does `environment_readiness.ok` prove the exact `Argv[0]` is available and executable, with repository-relative paths resolved from `Cwd` and confined to the repository?
- Does the command `Environment` reference `docs/agent-workflow/project-environment.json`, and do `required_tools[]` prove every allowlisted version probe passed and each observed numeric version satisfies its constraint?
- Was each project runtime tool previewed and applied through `project-env register` from a reviewed architecture or ADR source, without guessed versions, packages, or repair instructions?
- For a missing or incompatible tool, was the returned strategy-specific preflight followed: `env --repair --check` for `governance-env`, reviewed instructions for `manual`, or `project-env repair --check` plus explicit approval for `reviewed-command`?
- Before an approved project repair, were exact argv, cwd, source, local review evidence, write scope, timeout, and output bounds inspected, and did `.governance/project-environment-repairs.json` finish without a pending record?
- Was the returned structured command executed without a shell string, with a bounded timeout and bounded stdout/stderr capture?
- Was best-effort output redaction applied, while secret-bearing command arguments and intentionally printed credentials remained prohibited?
- Were command-contract rows with `Approval Required` set to `true` refused and routed to explicit external authorization?
- Did every `Writes State: true` command receive explicit `--allow-writes` authorization before execution?
- Are unit, integration, contract, end-to-end, accessibility, performance, security, or manual checks selected from the acceptance matrix and risk-bearing design docs?
- Are skipped, flaky, unavailable, or failed checks recorded honestly with command, result, date, and follow-up owner?
- Is `bin/governance verify . --check --json` or the target-local equivalent rerun when docs, workflow state, or handoff evidence changes?

Reference: `https://dora.dev/capabilities/test-automation/`

## Evidence and Status

- Does `docs/development/04-implementation-evidence.md` preserve every execution while `docs/development/03-verification-log.md` contains exactly one current summary row per `(Task, Command)`?
- When a command is rerun, was its current summary replaced without deleting the prior evidence-ledger run?
- Does any `Done` task link local Markdown evidence instead of relying on chat transcript memory?
- Are roadmap and task board statuses synchronized after implementation, verification, or blocking findings?
- Does the final handoff name changed files, commands run, failures, deferred follow-ups, and remaining risks?

Reference: `https://scrumguides.org/scrum-guide.html`

## Security and Supply Chain

- Are secrets, credentials, tokens, private keys, and production endpoints kept out of source, logs, test fixtures, and evidence files?
- Are dependency additions, version bumps, generated artifacts, and package-manager changes explicit in the task scope or represented as `Approval Required` commands before execution?
- Are build, release, provenance, integrity, or artifact-publishing steps recorded when the task creates deployable outputs?
- Are dependency and repository-risk findings from available target-local tools treated as blockers when they affect the task's changed surface?

Reference: `https://slsa.dev/spec/v1.2/about`
Reference: `https://openssf.org/projects/scorecard/`

## Completion Gate

- Does the task satisfy `references/implementation-readiness-checklist.md` plus this execution checklist before being marked `Done`?
- Does `implementation closeout` report `evidence_summary.all_verification_results_passing: true`, proving every current command result passes rather than only one?
- Are failing checks, unresolved questions, or out-of-scope discoveries reflected as `Blocked`, `Deferred`, or follow-up tasks instead of hidden in prose?
- Are all source-of-truth docs, implementation files, tests, and evidence committed as one coherent change when the repository uses Git?
