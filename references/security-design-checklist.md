# Security Design Checklist

Use this checklist before implementation tasks are marked Ready.

Calibrate against OWASP ASVS, OWASP API Security Top 10, and OpenSSF Best Practices without copying them as a rigid template.

## Identity and Access

- Are authentication boundaries and session assumptions explicit?
- Are authorization checks tied to resource ownership, roles, or policy rules?
- Are cross-user, admin, service-account, and public/private endpoint boundaries documented?

## API Abuse and Input

- Are object-level authorization, function-level authorization, and mass-assignment risks considered for each endpoint?
- Are input validation, output filtering, file handling, and unsafe redirect behavior documented when relevant?
- Are rate limits, quotas, pagination limits, and expensive-query constraints documented for abuse-prone paths?

## Data Protection

- Are sensitive fields, secrets, credentials, tokens, and PII identified?
- Are storage, transit, logging, masking, retention, and deletion expectations documented?
- Are audit trails and access-review expectations documented for sensitive workflows?

## Dependency and Supply Chain

- Are external services, packages, generated clients, and runtime images tied to owners and update paths?
- Are secret storage, rotation, and least-privilege access documented for dependencies?
- Are dependency failure, compromise, and version drift risks registered or linked to ADRs?

## Verification

- Are security-relevant acceptance criteria mapped to tests or manual review?
- Are auth, authorization, abuse limits, sensitive logging, and dependency failure cases covered by unit, integration, contract, or end-to-end checks?
- Are unresolved security decisions registered in `docs/unresolved.md` before implementation starts?
- Does `design threat-review` prove complete STRIDE consideration and named mitigation ownership for every DREAD >= 7 threat?

References:

- OWASP ASVS: `https://owasp.org/www-project-application-security-verification-standard/`
- OWASP API Security Top 10 2023: `https://owasp.org/API-Security/editions/2023/en/0x11-t10/`
- OpenSSF Best Practices: `https://bestpractices.coreinfrastructure.org/en`
