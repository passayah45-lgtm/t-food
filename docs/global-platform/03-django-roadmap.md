# 3. Ten-Sprint Django Implementation Roadmap

Cadence: two weeks per sprint. Sprint 1 has a separate day-by-day plan in [Sprint 1 Markets and Events](../SPRINT_01_MARKETS_AND_EVENTS_PLAN.md). Sprints 1-6 form the initial 90-day program with contingency; Sprints 7-10 continue the platform foundation.

## Sprint 1: Markets, Money, Events and Correlation

**Goal:** Establish multi-country identifiers and durable event publication without changing behavior.

- Backend: add `markets` and `events` apps; Money value object; market defaults; outbox/inbox; correlation middleware; JSON logging.
- Frontend: disabled-by-default MarketContext and money formatter.
- Migrations: create Currency/Market; nullable market FKs; batched backfill; later non-null contract; create event tables.
- APIs: `GET /api/v1/markets/`, additive market/currency fields.
- Celery: none; independent relay management worker first.
- Redis: durable Stream transport `tfood:domain-events`.
- Tests: money, market, migration/backfill, event atomicity, relay, inbox, headers/logging and all current tests.
- Risks: duplicate delivery, migration locks, PII in events. Mitigate with inbox, expand/backfill/contract and payload allow-lists.
- Acceptance: exact one created/status event per semantic change; rollback leaves no outbox; current APIs/tests pass.

## Sprint 2: Celery Platform and Asynchronous Notifications

**Goal:** Replace ad hoc loops and synchronous non-critical side effects with observable queues.

- Backend: configure `fooddelivery/celery.py`; task base classes; queue router; idempotency helper; notification provider interface and delivery-attempt model.
- Frontend: notification preference controls and delivery status only if product-ready; no visual redesign.
- Migrations: `NotificationDeliveryAttempt`, `TaskExecution`, optional user notification preferences.
- APIs: preferences GET/PATCH; keep existing notification list/read APIs.
- Celery: `critical`, `dispatch`, `payments`, `notifications`, `analytics`, `maintenance`, `fraud`, `ai`; initially run critical/dispatch/notifications/maintenance only.
- Redis: broker DB separate from cache and Channels; visibility timeout; result backend disabled for fire-and-forget tasks.
- Tests: eager-mode unit tests plus worker integration; retries; duplicate task idempotency; provider outage; notification creation no longer blocks order.
- Risks: lost/duplicate tasks and Redis contention. Use outbox-driven task creation, task idempotency keys and separate Redis namespaces/clusters by stage.
- Acceptance: checkout succeeds during provider outage; queued notifications retry and are traceable; current dispatch behavior remains intact.

## Sprint 3: Organization, Brand, Location and FulfillmentNode

**Goal:** Decouple legal merchant, customer brand and physical fulfillment location while preserving Restaurant APIs.

- Backend: create `merchants` app; Organization, OrganizationMember, Brand, Location, LocationBrand and FulfillmentNode; compatibility mapping from Restaurant.
- Frontend: merchant organization/location switcher behind feature flag; existing single-store dashboard remains default.
- Migrations: expand models; create one organization/brand/location/node per existing Restaurant; store legacy mapping; verify one-to-one coverage.
- APIs: new `/api/v2/merchant/organizations/`, `/brands/`, `/locations/`, `/nodes/`; v1 Restaurant serializers project from compatibility mapping.
- Celery: batched media/catalog mapping validation; organization onboarding notifications.
- Redis: cache organization/location permissions and location card projections with versioned keys.
- Tests: ownership/RBAC, migration idempotency, cloud-kitchen multi-brand, v1 parity, merchant cannot cross organizations.
- Risks: authorization leaks and dual-source confusion. Keep Restaurant authoritative during expand, then explicitly switch ownership behind a flag.
- Acceptance: every Restaurant maps to exactly one operational node; merchant can create a second branch in v2; v1 customer ordering is unchanged.

## Sprint 4: PostGIS Serviceability and Partner Presence

**Goal:** Replace decimal-coordinate scans with indexed geospatial queries and trusted location ingestion.

- Backend: enable GeoDjango/PostGIS; geography points on Location, CustomerAddress, DeliveryPartner snapshot; service-zone polygons; location ingestion service.
- Frontend: map/pin components continue sending lat/lng; partner app adds accuracy/timestamp fields and adaptive heartbeat.
- Migrations: install extension; add nullable geography fields; batch convert decimal coordinates; dual-write; verify; switch reads; retain decimal compatibility temporarily.
- APIs: serviceability quote endpoint; partner location adds accuracy, speed, heading, recorded_at.
- Celery: stale-presence cleanup, coordinate backfill, service-zone projection refresh.
- Redis: current partner presence/location TTL and candidate sets; PostgreSQL remains assignment truth.
- Tests: GiST query correctness, boundary/anti-meridian cases, stale/out-of-order pings, accuracy rejection, old payload compatibility.
- Risks: local SQLite tests cannot run GIS behavior. Add PostgreSQL/PostGIS CI service and isolate pure geometry unit tests.
- Acceptance: nearest eligible partners selected with indexed queries; no full partner table scan; current location payload still accepted.

## Sprint 5: Catalog v2 and Inventory Reservations

**Goal:** Support food, grocery, pharmacy and retail sellables from shared catalog primitives.

- Backend: `catalog` and `inventory` apps; Product, Variant, ModifierGroup/Option, Menu/Section/Listing, InventoryPosition/Movement/Reservation; FoodItem adapter.
- Frontend: merchant catalog editor, bulk CSV preview, inventory adjustment, customer variant/modifier rendering behind catalog flag.
- Migrations: create v2 tables; map FoodItem and options to Product/Variant/modifiers; no deletion of v1 rows; reconciliation command.
- APIs: `/api/v2/catalog/*`, bulk import upload/validate/apply, inventory positions/adjustments/reservations.
- Celery: bulk import parsing, catalog projection, reservation expiry, low-stock alerts.
- Redis: catalog card cache and short reservation contention hints; never inventory truth.
- Tests: mapping parity, modifier validation, concurrent reservation, idempotent release, bulk import partial errors, v1 order compatibility.
- Risks: overselling and two catalogs diverging. Use one-way v1-to-v2 migration plus feature-flagged read switch and reconciliation reports.
- Acceptance: grocery-style SKU can be reserved; existing menu still orders; two concurrent orders cannot reserve beyond stock.

## Sprint 6: Tax, Fee and Quote Snapshots

**Goal:** Produce server-authoritative, explainable commercial quotes per market.

- Backend: `pricing` app; TaxCategory, TaxRule, FeeRule, Quote and QuoteLine/Charge snapshot; pure pricing engine; quote version/idempotency.
- Frontend: checkout breakdown for tax, packaging, service and delivery fees; no client calculations.
- Migrations: add order tax/packaging/tip fields and OrderCharge; backfill historical zero/default snapshots without changing totals.
- APIs: `POST /api/v2/quotes/`; order creation accepts quote ID plus cart hash and revalidates expiration.
- Celery: rule activation, quote cleanup, price projection refresh.
- Redis: immutable short-lived quote cache keyed by quote ID; PostgreSQL stores accepted quote snapshot.
- Tests: tax inclusivity/exclusivity, rounding, GNF zero-decimal, promotion ordering, stale/tampered quote, historical order invariance.
- Risks: rounding and legal errors. Use Decimal/Money only, golden fixtures approved per market and four-eyes rule activation.
- Acceptance: accepted order total equals quote exactly; every charge references a versioned rule; existing v1 checkout remains supported.

## Sprint 7: Real-Time Tracking and Push Abstraction

**Goal:** Deliver live, resumable order and delivery state without polling.

- Backend: ASGI/Channels deployment; authenticated channel authorization; event-to-WebSocket projector; push token/provider abstractions.
- Frontend: OrderRealtimeProvider, connection/reconnect state, live timeline/location map, fallback polling.
- Migrations: DevicePushToken, PushDeliveryAttempt, optional RealTimeCursor.
- APIs: WebSocket `/ws/v1/orders/{public_id}`; push-token registration/revoke.
- Celery: push send/retry; expired token cleanup; WebSocket projection fallback.
- Redis: Channels layer, presence and short event cursor; isolate from Celery at scale.
- Tests: authorization, reconnect/resume, duplicate event, terminal-state delivery, revoked token and provider failover.
- Risks: connection leaks and missing events. Stateless gateway, heartbeat, cursor/replay from order timeline and polling fallback.
- Acceptance: status visible within two seconds p95 locally/staging; reconnect converges to authoritative state; no cross-user subscription.

## Sprint 8: Durable Delivery Offers and Redispatch

**Goal:** Make every delivery offer durable, expiring and automatically redispatched.

- Backend: DeliveryJob, DeliveryOffer, AssignmentAttempt and transition service; preserve current Delivery API adapter.
- Frontend: partner offer countdown/expiry; operations dispatch attempts; customer delay state.
- Migrations: map existing unassigned Delivery rows to jobs; create offer/attempt tables with partial unique active-assignment constraint.
- APIs: available offers, claim with idempotency key, decline/reason, operations retry/cancel.
- Celery: offer expiry, next-wave dispatch, stale assignment recovery and SLA escalation on dispatch queue.
- Redis: candidate/presence acceleration and countdown cache; DB offer row determines validity.
- Tests: simultaneous claim, expiry race, worker retry, no partner case, cancellation, current partner endpoint parity.
- Risks: duplicate assignment and timer loss. Atomic DB compare-and-set plus periodic recovery query independent of scheduled task delivery.
- Acceptance: every offer has expiry; missed task recovered; only one partner assigned; other dashboards lose claimed offer promptly.

## Sprint 9: Double-Entry Ledger and Reconciliation

**Goal:** Replace mutable payout-only totals with auditable financial postings.

- Backend: `ledger` app; accounts, journal entries/lines, settlement batches/items and posting templates; existing payout fields become projections.
- Frontend: merchant/partner statements, operations reconciliation exceptions and journal drill-down with restricted permission.
- Migrations: create ledger; backfill delivered/refunded orders into idempotent journals; reconcile projected balances against current payout fields.
- APIs: statements, settlement summaries, finance-only reconciliation; no arbitrary journal mutation endpoint.
- Celery: posting consumers, daily gateway/COD reconciliation, settlement generation and exception alerts on payments queue.
- Redis: no balance truth; short statement cache only.
- Tests: every journal balances, duplicate event posts once, reversal, partial refund, promotion sponsor split, COD and payout.
- Risks: incorrect opening balances and double posting. Shadow ledger first, reconciliation gate, finance approval and immutable reversals.
- Acceptance: 100% sampled orders reconcile; no unbalanced posted journal; current merchant/partner earnings remain unchanged until cutover.

## Sprint 10: CI/CD, Security and Operational Readiness

**Goal:** Make releases repeatable, observable, secure and rollback-capable.

- Backend: health/readiness separation, audit middleware, feature-flag registry, OpenTelemetry export and privileged RBAC hardening.
- Frontend: build metadata/error boundary; operations release/incident visibility where appropriate.
- Migrations: audit event and flag override tables only if required.
- APIs: internal readiness, build version and feature-flag diagnostics protected from public access.
- Celery: queue health probes, retention jobs, backup verification and synthetic order flow.
- Redis: health metrics, memory policy validation and key-prefix audit.
- Tests: CI matrix on PostgreSQL/PostGIS/Redis, migration from production snapshot, container health, security checks and end-to-end smoke.
- Risks: pipeline false confidence and secrets exposure. OIDC-based CI credentials, no long-lived cloud keys, signed images and environment promotion.
- Acceptance: pull request gates tests/migrations/frontend/lint/SAST/container scan; staging canary and rollback demonstrated; restore drill completed.

## Cross-Sprint Release Discipline

Every sprint follows this order:

1. Record baseline tests and metrics.
2. Add schema through expand migration.
3. Deploy write-compatible code behind a flag.
4. Backfill in resumable batches.
5. Verify invariants and shadow results.
6. Enable for internal users, one merchant/zone, then percentage/market.
7. Observe SLO and business metrics.
8. Contract schema only in a later release.
9. Update runbook, event catalog and architecture status.

