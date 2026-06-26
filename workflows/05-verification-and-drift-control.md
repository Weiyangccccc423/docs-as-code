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

2. Run environment check:

   ```bash
   bin/governance env --strict --repair --target <target>
   ```

3. If the target project has a Makefile, run its verification entry:

   ```bash
   make verify-governance
   ```

4. Before implementation starts, confirm:
   - no unregistered docs directories
   - no stale reserved markers
   - no blocking unresolved items
   - product, API, architecture, backend, frontend, tests, and development docs link to each other
   - task board items have product/design/API/acceptance reverse links

## Output

A verification report and a list of fixes, or a clean governance baseline.

## Stop Conditions

- Verification fails on source-of-truth conflicts.
- The task board claims completion without evidence.
- Roadmap status conflicts with task board status.
- A generated document is not indexed by its parent README.
