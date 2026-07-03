# Backend Operability Checklist

Use this checklist before backend design is treated as implementation-ready.

Calibrate backend operability against Google SRE service-level guidance, OpenTelemetry signals, and Twelve-Factor configuration/logging practices. Keep it product-scoped: only require operational detail that affects acceptance, reliability, debugging, or safe delivery.

## Service Levels

- Are user-visible reliability expectations expressed as SLIs and SLOs where the product depends on them?
- Are availability, latency, throughput, durability, correctness, or freshness targets tied to product acceptance or architecture quality scenarios?
- Are error budgets, alert thresholds, and escalation expectations documented when the service has production reliability commitments?

Reference: `https://sre.google/sre-book/service-level-objectives/`

## Observability Signals

- Are logs, metrics, traces, and audit events named for critical success and failure paths?
- Are trace IDs or correlation IDs propagated across API, backend modules, jobs, and external service calls?
- Are sensitive fields excluded, masked, or classified before being logged or emitted as telemetry?

Reference: `https://opentelemetry.io/docs/concepts/signals/`

## Configuration and Secrets

- Are environment-specific configuration values separated from code and documented with owners?
- Are secrets, credentials, tokens, rotation expectations, and emergency revocation paths explicit?
- Are feature flags, kill switches, runtime limits, and default values documented when they affect user-visible behavior?

Reference: `https://12factor.net/config`

## Runtime Controls

- Are timeouts, retries, backoff, circuit breakers, rate limits, quotas, and overload behavior documented for each critical dependency or expensive operation?
- Are startup, shutdown, health check, readiness check, background worker, and scheduled job behaviors explicit?
- Are cancellation, duplicate execution, replay, and partial completion outcomes documented for async or long-running work?

## Operational Logs

- Are logs treated as event streams that can be collected by the runtime environment without local file assumptions?
- Are event names, severity, product/user context, module ownership, and recovery actions documented for high-value logs?
- Are audit logs separated from debug logs when product, compliance, or security expectations require it?

Reference: `https://12factor.net/logs`

## Runbooks and Support

- Are known failure modes linked to detection signal, impact, immediate mitigation, owner, and follow-up evidence?
- Are manual repair steps, data repair steps, or customer-support actions documented only when product-safe and auditable?
- Are unresolved operational risks registered in `docs/unresolved.md` before implementation handoff?
