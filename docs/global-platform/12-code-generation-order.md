# 12. Safe Code-Generation Order

This is the binding sequence for Codex changes to `work/T-food-clean`. Never generate all future models/services in one release. Each checkpoint must leave the application deployable and all existing behavior available.

## Generation Rules

1. Read current files and tests immediately before editing; do not rely only on this blueprint.
2. Use `apply_patch` for manual edits and preserve user changes.
3. One bounded change per migration; inspect generated migrations.
4. Expand, deploy, backfill, verify, contract.
5. Add tests with each behavior, then run focused and full suites.
6. Add feature flags before alternate read/write paths.
7. Never trust client prices, market, assignment or financial status.
8. Idempotency key plus database constraint protects every retryable mutation.
9. Outbox events are inserted in the same transaction as source state.
10. Do not start the next phase while current Docker services or required workers are unhealthy.

## Phase A: Sprint 1 Foundation

Detailed execution: [Sprint 1 Plan](../SPRINT_01_MARKETS_AND_EVENTS_PLAN.md).

### A1 Baseline

1. Run current backend tests, migration check and frontend build.
2. Record Docker health and migration state.
3. Add settings flags and `.env.example` values with behavior disabled.

### A2 Markets and Money

4. Generate `backend/markets` app.
5. Add Currency and Market models/admin.
6. Add reference migration for INR/GNF and active India.
7. Add Money utility and focused tests.
8. Add read-only market serializers/views/URLs.

### A3 Market Expand

9. Add nullable market to Customer, Restaurant, Offer, Order and DeliveryPartner.
10. Add nullable currency snapshot to Order.
11. Generate separate migrations in owning apps.
12. Add runtime default/dual-read helpers.
13. Modify order creation to derive market/currency from Restaurant.
14. Add additive response fields and compatibility tests.
15. Add batched backfill/verification commands and tests.

### A4 Events and Tracing

16. Generate `backend/events` app.
17. Add OutboxEvent/InboxEvent models, indexes, admin and migration.
18. Add envelope/contracts and transaction-enforcing publisher.
19. Add inbox process-once helper.
20. Add correlation context/middleware and JSON formatter.
21. Integrate order created/status signal transactionally.
22. Add Redis transport, relay algorithm and management command.
23. Add event_relay Compose process.
24. Run full tests/build, deploy expand, backfill, verify, then contract.

## Phase B: Celery and Notification Isolation

25. Add `fooddelivery/celery.py` and app initialization.
26. Add queue constants/router and idempotent task base.
27. Add TaskExecution/FailedTask only if domain idempotency cannot represent execution.
28. Add Compose workers for critical, dispatch, notifications and maintenance plus beat.
29. Move notification sending behind provider interface and notification queue.
30. Keep Notification row creation/API behavior compatible.
31. Move unpaid expiry and maintenance loops into idempotent tasks plus recovery scanner.
32. Add real-worker integration tests and broker failure smoke.

## Phase C: Merchant Structure

33. Generate `backend/merchants` app.
34. Add Organization and OrganizationMember models/RBAC tests.
35. Add Brand, Location, LocationBrand and FulfillmentNode.
36. Add nullable compatibility FKs/mapping from Restaurant.
37. Generate idempotent mapper/backfill and reconciliation command.
38. Add v2 merchant APIs and selectors/services.
39. Add merchant location switcher behind frontend feature flag.
40. Prove v1 Restaurant browse/menu/order parity before read cutover.

## Phase D: PostGIS

41. Update local/CI/PostgreSQL image to PostGIS-capable version and add GeoDjango dependencies.
42. Add extension migration and GIS test database.
43. Add nullable geography fields beside decimal coordinates.
44. Add conversion/backfill and dual-write adapter.
45. Add GiST indexes and service-zone model.
46. Implement serviceability selector and candidate query.
47. Extend partner location input with timestamp/accuracy while accepting old payload.
48. Add Redis presence projection and stale cleanup.
49. Verify query plans on production-like data; switch reads behind flag.

## Phase E: Catalog v2 and Inventory

50. Generate `catalog` app models in dependency order: Product, Variant, ModifierGroup, ModifierOption, Menu, Section, Listing.
51. Generate `inventory` app: Position, Movement, Reservation.
52. Add FoodItem-to-v2 mapping/backfill and deterministic reconciliation.
53. Add catalog selectors/services and v2 read APIs.
54. Add merchant CRUD/import APIs with ownership checks.
55. Add inventory adjustment/reserve/release/expire services with row locks/idempotency.
56. Add merchant catalog/inventory frontend behind flags.
57. Add customer v2 menu adapter and compare order totals to v1.
58. Enable by one merchant/location before broad cutover.

## Phase F: Pricing, Tax and Quote

59. Generate `pricing` app: TaxCategory, TaxRule, FeeRule, Quote, QuoteLine/Charge.
60. Implement pure Decimal/Money engine with market golden fixtures.
61. Add OrderCharge and new total snapshot fields as nullable/default-safe.
62. Add quote endpoint and cart hash/idempotency.
63. Add order-create quote acceptance while retaining v1 calculation path.
64. Add checkout breakdown frontend.
65. Shadow-compare v1/v2 totals; block cutover on differences.

## Phase G: Real-Time and Push

66. Configure ASGI/Channels and isolated Redis channel layer.
67. Add authenticated order channel authorization.
68. Add event projection from outbox/bus to channel groups.
69. Add cursor/reconnect snapshot and polling fallback.
70. Add DevicePushToken and PushDeliveryAttempt.
71. Implement push provider interface, FCM/APNs adapters and notification task.
72. Add frontend realtime provider and tracking components.
73. Run authorization, reconnect and provider outage tests.

## Phase H: Durable Dispatch

74. Add DeliveryJob, DeliveryOffer, DeliveryAssignment and RoutePlan/Stop models.
75. Add partial unique active-assignment constraints.
76. Map current Delivery records without changing public API.
77. Implement deterministic candidate/scoring policy and version record.
78. Implement durable offer creation/expiry/recovery tasks.
79. Implement atomic claim service with idempotency.
80. Adapt current partner endpoints to new services.
81. Add countdown/expiry UI and operations attempt history.
82. Load/fault-test simultaneous claims and worker loss.

## Phase I: Financial Ledger

83. Generate LedgerAccount, JournalEntry/Line, SettlementBatch/Item and reconciliation models.
84. Implement balanced posting service and immutable model/admin policy.
85. Add versioned posting templates for capture, delivery, refund and payout.
86. Backfill historical journals idempotently in shadow mode.
87. Build balance/statement projections and compare current payout fields.
88. Add reconciliation imports/provider adapters and exception UI.
89. Require finance approval before authoritative cutover.
90. Keep old payout fields read-only for a stabilization release.

## Phase J: Data, AI and Ads

91. Sink validated events to S3 with schema/data-classification checks.
92. Build warehouse transforms and experiment assignment.
93. Ship deterministic popularity, ETA and fraud-rule baselines.
94. Add registry/shadow prediction logging before online models.
95. Deploy one model at a time: ETA, demand, recommendation, fraud.
96. Add Merchant AI Assistant with read-only tools first and audited confirmations.
97. Add ads only after organic ranking, attribution and marketplace liquidity are trustworthy.

## Phase K: AWS and CI/CD

Infrastructure evolves alongside earlier phases; do not wait until the end.

98. Create Terraform/OpenTofu account/VPC/ECR/ECS/RDS/Redis/S3/CloudFront baseline.
99. Add OIDC CI role, immutable image build, SBOM/sign/scan.
100. Add PostgreSQL/PostGIS/Redis CI matrix and migration-from-snapshot job.
101. Add staging, one-off migration/backfill tasks and synthetic order smoke.
102. Add canary deployment, feature flag rollout and automatic rollback.
103. Add OpenTelemetry collector, SLO dashboards and paging policy.
104. Add backup/restore automation and quarterly DR game day.
105. Introduce MSK/search/warehouse only when event/search/data volume justifies cost.
106. Evaluate EKS only when documented triggers in the AWS plan are met.

## Per-Change File Order

Within any feature, Codex should edit in this order:

1. Domain model and invariants.
2. Migration and data migration/command.
3. Domain service and selector.
4. Event contract/publisher integration.
5. Task/consumer with idempotency.
6. Serializer and permission.
7. API view/URL.
8. Admin/operations controls.
9. Frontend API client/context/components.
10. Focused tests, integration tests and regression suite.
11. Deployment/config/runbook.

## Required Verification Commands

```powershell
cd D:\Mister T\t-food\work\T-food-clean\backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test api
python manage.py test

cd ..\frontend
npm.cmd run build

cd ..
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 100 backend
```

As lint/test tools are added, CI becomes the authoritative command list. Use a production-like PostgreSQL/PostGIS database for GIS, locking, SKIP LOCKED, constraints and concurrency tests; SQLite is insufficient for those behaviors.

## Stop Conditions

Stop rollout and repair before proceeding if:

- existing API tests regress
- migration verification has unexplained counts/nulls
- shadow totals/ledger balances differ
- duplicate assignment or financial posting occurs
- event backlog grows without recovery
- SLO/error/fraud/cancellation guardrails worsen materially
- feature cannot be disabled without data corruption

The safest global platform is built as a sequence of reversible, reconciled changes, not as a one-time rewrite.

