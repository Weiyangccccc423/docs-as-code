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
   - no non-template Markdown files missing from their same-directory README
   - no explicit local Markdown link pointing to a missing file
   - product, API, architecture, backend, frontend, tests, and development docs link to each other
   - task board items have `ID`, `Status`, `Task`, `Product`, `Design`, `API`, `Acceptance`, and `Verification`
   - task board item IDs are unique
   - task board `Product`, `Design`, `API`, and `Acceptance` fields point to existing local Markdown files
   - at least one task board item is `Ready` before implementation starts

## Output

A verification report and a list of fixes, or a clean governance baseline.

## Stop Conditions

- Verification fails on source-of-truth conflicts.
- The task board claims completion without evidence.
- Roadmap status conflicts with task board status.
- A generated document is not indexed by its parent README.
