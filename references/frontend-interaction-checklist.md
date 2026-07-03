# Frontend Interaction Checklist

Use this checklist before UI interaction models or frontend module designs are treated as implementation-ready.

Calibrate frontend design against WCAG, WAI-ARIA Authoring Practices, semantic HTML, and Core Web Vitals. Prefer product-backed interaction behavior over visual guesses; use this checklist to make user-visible behavior, state ownership, accessibility, and performance expectations implementable.

## Interaction Model

- Are primary flows, actors, triggers, success paths, exits, cancellations, permissions, and irreversible actions documented?
- Are screens tied to product purpose, entry points, exit paths, empty states, and acceptance criteria?
- Are user-visible labels, copy needs, confirmation steps, and recovery paths explicit for high-risk actions?

## Accessibility and Semantics

- Are keyboard operation, focus order, visible focus, labels, names, roles, contrast, status messages, and screen-reader expectations documented for primary flows?
- Are native semantic elements preferred before custom ARIA behavior?
- Are WCAG success criteria referenced when accessibility behavior affects acceptance or implementation tasks?

Reference: `https://www.w3.org/TR/WCAG22/`
Reference: `https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA`

## Component Behavior

- Are custom widgets mapped to expected role, state, property, keyboard interaction, and focus-management behavior?
- Are modal, menu, tab, combobox, disclosure, toast/status, drag/drop, and data-table behaviors documented when used?
- Are loading, disabled, read-only, validation, pending, optimistic, stale, retrying, success, and error states explicit per component or flow?

Reference: `https://www.w3.org/WAI/ARIA/apg/`

## API Consumption and Error UX

- Does each server-derived state link to a concrete endpoint contract and response owner?
- Are API error codes mapped to user-visible copy, recovery action, retry behavior, telemetry, and acceptance criteria?
- Are cancellation, duplicate submission, stale data, conflict, offline, timeout, and partial failure outcomes documented when relevant?

## State and Routing

- Are local, shared, server-derived, cached, optimistic, persisted, and URL/route state owners explicit?
- Are route access rules, deep links, redirects, guarded states, and back/forward behavior documented?
- Are cache invalidation, synchronization, pagination, filtering, sorting, and mutation side effects traceable to API and product sources?

## Performance and Responsiveness

- Are Core Web Vitals expectations considered for product-critical screens and flows?
- Are loading strategies, skeletons, progressive rendering, asset budgets, and expensive interaction constraints documented when they affect acceptance?
- Are interaction responsiveness risks mapped to test strategy or implementation handoff evidence?

Reference: `https://web.dev/articles/vitals`

## Evidence and Handoff

- Are UI and frontend decisions linked to product, acceptance, API, backend, test, and unresolved sources?
- Are accessibility, performance, and user-visible error checks represented in `docs/tests/01-strategy.md` or `docs/development/02-task-board.md` before implementation?
- Are unresolved interaction, copy, route, state, or accessibility decisions registered in `docs/unresolved.md`?
