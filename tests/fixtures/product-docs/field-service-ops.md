# Field Service Operations Portal

## Background

Field service coordinators currently receive installation requests through email, spreadsheets, and phone calls.
The first release should centralize intake, triage, scheduling, and technician handoff for a single operations team.

## Goals and Requirements

- Coordinators can create a service request with customer contact details, service address, priority, requested window, equipment notes, and attached context.
- Dispatchers can view a triage queue grouped by priority and age, then assign a technician and scheduled arrival window.
- Technicians can open a mobile-friendly work order summary with customer, address, scope, safety notes, and required evidence before arrival.
- Coordinators can see request status changes from intake through completion without asking dispatchers for manual updates.
- The system records audit events for request creation, scheduling, reassignment, technician check-in, completion, and cancellation.
- The first release supports one operations team and does not need billing, inventory management, or multi-tenant account administration.

## User Roles

- Coordinator: creates requests and communicates with customers.
- Dispatcher: triages requests, assigns technicians, and adjusts schedules.
- Technician: views assigned work and records field progress.
- Operations manager: reviews queue health and audit history.

## Acceptance Criteria

- A coordinator can submit a complete service request and receives a stable request ID that is visible in the queue.
- A dispatcher can assign an unassigned request to a technician with a scheduled arrival window, and the assignment is visible to both dispatcher and technician.
- A technician can mark an assigned work order as checked in, add completion evidence, and mark the job complete.
- An operations manager can view an audit timeline for a request showing who changed status, assignment, schedule, or completion evidence.

## Constraints

- Personally identifiable customer contact data must be visible only to authenticated team members.
- Status changes must be idempotent enough that repeated client submissions do not create duplicate audit entries.
- The workflow must remain usable from a phone-sized viewport for technicians in the field.

## Open Questions

- Should customer notifications be sent by email, SMS, or handled outside the first release?
- Does the operations manager need CSV export in the first release?
