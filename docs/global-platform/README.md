# T-Food Global Platform Implementation Package

Status: Architecture package v1.0  
Planning horizon: 36 months  
Architecture posture: Modular monolith first, market cells and selective extraction later

This package converts T-Food's existing Django/React marketplace into a buildable global local-commerce platform plan. It extends, rather than replaces:

- [Next-Generation Platform Blueprint](../NEXT_GENERATION_BLUEPRINT.md)
- [Sprint 1 Markets and Events Plan](../SPRINT_01_MARKETS_AND_EVENTS_PLAN.md)

## Package Index

1. [System Architecture](01-system-architecture.md)
2. [Database Architecture](02-database-architecture.md)
3. [Ten-Sprint Django Roadmap](03-django-roadmap.md)
4. [Event-Driven Platform](04-event-platform.md)
5. [Celery Architecture](05-celery-platform.md)
6. [PostGIS Dispatch Engine](06-postgis-dispatch.md)
7. [Financial Ledger](07-financial-ledger.md)
8. [AI and ML Platform](08-ai-ml-platform.md)
9. [AWS and DevOps Architecture](09-aws-devops.md)
10. [Investor-Grade Roadmap](10-investor-roadmap.md)
11. [Competitive Strategy](11-competitive-strategy.md)
12. [Safe Code-Generation Order](12-code-generation-order.md)

## Binding Decisions

- Preserve the current REST contracts while adding `/api/v2` projections only when semantics differ.
- Do not extract a service without measured load, clear ownership, an SLO and an operational runbook.
- Every market-bound aggregate carries `market_id`; every order snapshots currency, prices, taxes and fees.
- Every financial mutation is idempotent and posts to an immutable double-entry ledger.
- Every cross-domain side effect starts from a transactional outbox event.
- Redis is acceleration and ephemeral state, never the source of truth for money, orders or final delivery assignment.
- PostgreSQL remains the transactional source of truth through at least Series A scale.
- AI advises or ranks under deterministic constraints; it never directly authorizes money movement or irreversible state.

## Planning Assumptions

Cost figures are modeled ranges, not AWS quotes. Re-price with the AWS Pricing Calculator in the intended region before procurement. Competitive observations are strategic archetypes rather than claims about every current feature of another company; validate them during each annual strategy review.

