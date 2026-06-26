# Phase 05: Verification and Drift Control

## Input

- Generated governance repository
- Product and design documents
- Optional code directories

## Skills

Load:

- `verifying-governance-docs`

## Procedure

1. Run structural verification:

   ```bash
   bin/governance verify <target>
   ```

   For agent-controlled verification, prefer machine-readable output:

   ```bash
   bin/governance verify <target> --json
   ```

   Use `findings[].code` for automation. Keep `errors` and `warnings` for human-readable summaries.

   When already inside an initialized target repository, prefer:

   ```bash
   bin/governance verify .
   ```

2. Run environment check:

   ```bash
   bin/governance env --strict --repair --target <target>
   ```

   Agents may use `--json` and must treat `ok: false` as a stop condition. If `needs_escalation` is true, do not run the reported install command without explicit approval.

3. If the target project has a Makefile, run its verification entry:

   ```bash
   make verify-governance
   ```

4. Before implementation starts, run the implementation gate:

   ```bash
   bin/governance advance implementation <target> --json
   ```

5. Before implementation starts, confirm:
   - no unregistered docs directories
   - no stale reserved markers
   - no `governance:scaffold-placeholder` markers
   - no `docs/unresolved.md` rows with a blocking `Blocking Scope`
   - no `docs/unresolved.md` rows with missing `ID`, `Domain`, or `Description`, and no duplicate unresolved IDs
   - no `docs/glossary.md` rows with missing `Term`, `Meaning`, or `Source`, duplicate terms, or missing local Markdown sources
   - no non-template Markdown files missing from their same-directory README
   - no explicit local Markdown link pointing to a missing file
   - product chapter filenames use `NN-<slug>.md` with unique `NN` prefixes
   - a dedicated `NN-*acceptance*.md` product chapter exists before design derivation or implementation handoff
   - API endpoint contract filenames under `docs/api/endpoints/` use `NN-<slug>.md` with unique `NN` prefixes
   - API endpoint contract files include non-placeholder method/path, auth, idempotency, request, response, error, upstream link, and frontend consumer sections
   - API endpoint `Method and Path` sections contain an HTTP method and absolute path
   - API endpoint `Error Codes` sections reference `docs/api/error-codes.md`
   - API endpoint `Upstream Links` sections reference existing local source Markdown
   - API endpoint `Frontend Consumers` sections reference existing local UI or frontend API-consumption Markdown
   - product, API, architecture, backend, frontend, tests, and development docs link to each other
   - `docs/architecture/01-system-context.md` links to product scope and product acceptance criteria
   - `docs/architecture/02-containers.md` links to `docs/architecture/01-system-context.md` and product acceptance criteria
   - `docs/architecture/03-quality-attributes.md` has non-placeholder Product Links, Availability, Performance, Security, Observability, and Tradeoffs sections, and links to containers plus product acceptance criteria
   - `docs/backend/01-modules.md` links to API docs, `docs/backend/02-data-model.md`, `docs/backend/03-external-services.md`, and product acceptance criteria
   - `docs/backend/02-data-model.md` has non-placeholder Product Links, Owners, Entities, State Machines, Constraints, Indexes, and Migrations sections, and links to backend modules, API docs, and product acceptance criteria
   - `docs/backend/03-external-services.md` has non-placeholder Product Links, Dependencies, Contracts, Retries, Timeouts, Authentication, and Observability sections, and links to backend modules, API docs, and product acceptance criteria
   - `docs/frontend/01-modules.md` links to UI docs, API docs, `docs/frontend/02-api-consumption.md`, and product acceptance criteria
   - `docs/frontend/02-api-consumption.md` has non-placeholder Product Links, API Links, Consumption Map, Loading States, and Error Actions sections, and links to frontend modules, API docs, and product acceptance criteria
   - `docs/tests/01-strategy.md` links to product acceptance criteria, API docs, and architecture/backend/frontend design docs
   - `docs/tests/02-acceptance-matrix.md` uses `Acceptance`, `Design`, `API`, and `Test` columns with local Markdown links to matching source docs
   - ADRs under `docs/decisions/` include non-placeholder Context, Decision, Consequences, and References sections with local Markdown source links
   - roadmap tables with `ID` and `Status` columns agree with same-ID task board statuses
   - task board items have `ID`, `Status`, `Task`, `Product`, `Design`, `API`, `Acceptance`, and `Verification`
   - task board `Status` values are one of `Backlog`, `Ready`, `In Progress`, `Blocked`, `Done`, or `Deferred`
   - task board items marked `Blocked` cite an existing unresolved item ID and link to `docs/unresolved.md`
   - task board items marked `Done` link to existing local Markdown verification evidence
   - task board item IDs are unique
   - task board `Product`, `Design`, `API`, and `Acceptance` fields point to existing local Markdown files
   - task board `Acceptance` fields include a product acceptance chapter reference matching `docs/product/NN-*acceptance*.md`
   - at least one task board item is `Ready` before implementation starts

## Output

A verification report and a list of fixes, or a clean governance baseline.

## Stop Conditions

- Verification fails on source-of-truth conflicts.
- The task board claims completion without evidence.
- Roadmap status conflicts with task board status.
- A generated document is not indexed by its parent README.
