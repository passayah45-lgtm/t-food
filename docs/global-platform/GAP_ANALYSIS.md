# T-Food Global Platform Gap Analysis

Date: 2026-06-23

This audit compares the current T-Food repository against the Global Platform Implementation Package. It is based on the repository code, not assumptions.

Audited code areas:

- Backend apps: `api`, `customers`, `delivery`, `notifications`, `orders`, `payments`, `restaurants`, `fooddelivery`
- Frontend app: `frontend/src`
- Runtime: `docker-compose.yml`, `backend/requirements.txt`, `backend/entrypoint.sh`
- Architecture docs: `docs/global-platform/*.md`, `docs/NEXT_GENERATION_BLUEPRINT.md`, `docs/SPRINT_01_MARKETS_AND_EVENTS_PLAN.md`

Effort scale:

- XS: less than 1 day
- S: 1-3 days
- M: 1-2 weeks
- L: 3-5 weeks
- XL: 6-12 weeks
- XXL: 12+ weeks

## Executive Findings

T-Food is currently a working modular monolith with customer, merchant, partner, operations, ordering, payments, notifications, shared delivery claiming, support, and payout workflows. The repository already has meaningful transactional locking, order idempotency, order timelines, dispatch wave logic, and 80 backend tests in the `api` app.

The largest gap is not product UX; it is platform durability. The architecture package calls for market/currency foundations, durable events, Celery queues, structured observability, PostGIS, durable dispatch offers, WebSockets, tax snapshots, and a ledger. Most of those are not yet implemented in code.

The recommended path is to keep the modular monolith, add the foundation in small backward-compatible slices, and avoid service extraction until operational pressure proves it is necessary.

## Gap Analysis Table

| Feature | Current Status | Existing Files | Missing Components | Technical Debt | Risk Level | Estimated Effort | Recommended Sprint |
|---|---|---|---|---|---|---|---|
| Modular monolith baseline | Implemented | `backend/*`, `api/urls.py`, `docker-compose.yml` | Clear package-level domain contracts | Business logic still concentrated in API views | Medium | M | Sprint 0 hardening |
| Domain boundaries | Partially implemented | `orders/models.py`, `delivery/services.py`, `restaurants/models.py`, `payments/models.py` | `markets`, `events`, `catalog`, `pricing`, `ledger`, `organizations` apps | Cross-domain imports are direct and will get harder to maintain | Medium | M | Sprints 1-3 |
| API gateway/BFF | Partially implemented | `frontend/nginx.conf`, `api/urls.py` | Gateway auth policy, request IDs, rate-limit observability, version policy | Frontend calls many REST endpoints directly with no API contract manifest | Medium | M | Sprint 10 |
| Global control plane | Missing | None | Market registry, country rollout controls, global admin config | Single-market assumptions in currency, fees, time zone, and operations | High | L | Phase C |
| Market-cell architecture | Missing | `docker-compose.yml` | Per-market routing, tenant/market isolation, data residency rules | Database rows have no market ownership | High | XL | Phase D |
| Disaster recovery | Partially implemented | `docker-compose.yml` volumes | Backup verification, restore runbooks, RPO/RTO drills | Local volumes only; no automated restore proof | High | M | Sprint 10 |
| Market model | Missing | None | `markets.Market`, country, time zone, default currency, active flags | Hard-coded single market behavior | High | S | Sprint 1 |
| Currency model | Missing | None | `markets.Currency`, minor units, symbol, Money utility | Frontend hard-codes `Rs.`; backend decimals lack currency context | High | S | Sprint 1 |
| Money utility | Missing | None | Decimal-safe money object/helpers, serializer fields, rounding policy | Amount math is scattered across serializers/views | High | S | Sprint 1 |
| `market_id` on key tables | Missing | `orders/models.py`, `restaurants/models.py`, `customers/models.py`, `delivery/models.py` | Nullable FK migrations, backfill, indexes, later non-null constraints | Retrofitting later will be harder as rows grow | High | M | Sprint 1 |
| Merchant organization model | Missing | `restaurants/models.py` has `MerchantProfile` and `Restaurant` | `Organization`, `Brand`, `Location`, `FulfillmentNode` | Merchant equals user/profile; restaurant mixes brand, legal, location, fulfillment | High | L | Sprint 3 |
| Merchant approval | Implemented | `restaurants/models.py`, `api/operations_views.py`, `RegisterPage.jsx`, `OperationsDashboardPage.jsx` | Approval audit log, reason codes, market-scoped approvals | State is boolean-only and not fully auditable | Medium | S | Sprint 3 |
| Customer profile | Partially implemented | `customers/models.py`, `api/user_views.py` | Market, locale, consent, device/session model | Customer data tied directly to Django user | Medium | M | Sprint 2-3 |
| Partner profile | Partially implemented | `delivery/models.py`, `api/delivery_views.py` | Market, service zones, vehicle capabilities, compliance docs | Availability and current GPS live on profile row | High | M | Sprint 4 |
| Catalog v1 | Implemented | `restaurants/models.py`, `api/merchant_views.py`, `RestaurantPage.jsx` | Product/variant/modifier/inventory separation | `FoodItem` and option groups are restaurant-specific v1 concepts | Medium | M | Sprint 5 |
| Product variants | Partially implemented | `FoodOptionGroup`, `FoodOption`, `OrderItem.selected_options` | ProductVariant, price books, SKU, variant inventory | Modifiers are nested under food item, not reusable | Medium | M | Sprint 5 |
| Inventory | Missing | None | Stock item, reservation, release, depletion tasks | Availability is a boolean only | Medium | L | Sprint 5 |
| Order lifecycle | Implemented | `orders/models.py`, `orders/signals.py`, `api/order_views.py`, `api/merchant_views.py`, `api/delivery_views.py` | Formal state-machine service and transition table | Status changes are made in several views/services | High | M | Sprint 1-2 |
| Order idempotency | Implemented | `orders/models.py`, `api/test_order_idempotency.py` | Idempotency for all financial/status transitions | `client_order_id` covers checkout only | Medium | S | Sprint 1-2 |
| Order timeline | Implemented | `OrderStatusEvent`, `orders/signals.py`, `api/test_order_timeline.py` | Event outbox publishing and correlation ID capture | Timeline is local DB only; no async consumers | Medium | S | Sprint 1 |
| Pricing and fee calculation | Partially implemented | `api/serializers.py`, `orders/models.py`, `restaurants/models.py` | Quote model, immutable fee/tax snapshots, pricing version | Amount fields exist but no quote/audit object | High | L | Sprint 6 |
| Tax model | Missing | None | Tax region, tax rule, tax line snapshot, invoice fields | No tax readiness for multi-country operation | High | L | Sprint 6 |
| Promotions and loyalty | Partially implemented | `Offer`, `Customer.loyalty_points`, retention tests | Campaign rules, budget, promo liability, abuse controls | Offer model is simple percent discount | Medium | M | Sprint 6 or Phase B |
| Payments | Partially implemented | `payments/models.py`, `api/payment_views.py`, `PaymentWebhookEvent` | Provider abstraction, payment attempts, refunds, reconciliation jobs | Payment status is simple; provider fields are Razorpay-shaped | High | M | Sprint 9 |
| Payment webhook inbox | Partially implemented | `PaymentWebhookEvent` | Generic transactional inbox with consumer idempotency | Webhook inbox is payment-specific | Medium | S | Sprint 1 |
| Merchant payouts | Partially implemented | `Order.merchant_payout*`, `api/operations_views.py` | Ledger entries, payout batch, reconciliation, bank rails | Payout state is stored on order row | High | L | Sprint 9 |
| Partner payouts | Partially implemented | `Delivery.partner_fee`, `payout_status`, `api/operations_views.py` | Ledger entries, payout batch, COD offset | Payout state is stored on delivery row | High | L | Sprint 9 |
| Double-entry ledger | Missing | None | Account, journal entry, journal line, balance checks | Financial truth is spread across order/payment/delivery rows | High | XL | Sprint 9 |
| Transactional outbox | Missing | None | `OutboxEvent`, publisher helper, relay command/worker | Signals create timeline rows but no durable integration events | High | M | Sprint 1 |
| Transactional inbox | Missing | `payments/models.py` has payment-specific webhook event | `InboxEvent`, processed/failed states, consumer keys | Idempotency pattern is not reusable | High | M | Sprint 1 |
| Event envelope/contracts | Missing | None | Event schema, name/version, aggregate keys, correlation ID | Events cannot be replayed or audited globally | High | S | Sprint 1 |
| Event relay worker | Missing | `dispatch_worker` pattern exists | Management command or Celery task to publish and mark outbox rows | No relay, no DLQ, no retry policy | High | M | Sprint 1 |
| Event replay/DLQ | Missing | None | Replay command, dead-letter states, ops visibility | Failures would be invisible until features depend on events | High | M | Sprint 2 |
| Celery app/config | Missing | `requirements.txt` includes Celery | `fooddelivery/celery.py`, queue config, Docker workers, beat | Celery is installed but unused | High | S | Sprint 2 |
| Celery queues | Missing | None | `critical`, `dispatch`, `notifications`, `maintenance`, `default` | Current worker is a custom infinite loop | High | M | Sprint 2 |
| Maintenance jobs | Partially implemented | `orders/services.py`, `dispatch_worker.py` | Celery beat tasks for expiry, cleanup, outbox relay | Expiry runs inside dispatch worker loop | Medium | S | Sprint 2 |
| Notification isolation | Missing | `notifications/services.py` | Async notification tasks, provider abstraction, retry | Notification writes happen inside request transactions | Medium | M | Sprint 2 |
| Redis cache/rate limits | Partially implemented | `settings.py`, throttling tests, `docker-compose.yml` | Separate Redis DBs for cache, celery, channels, presence | One Redis URL namespace for everything | Medium | S | Sprint 2 |
| Structured logging | Missing | `settings.py` | JSON logging, correlation fields, request metadata | Logs are default Django/Gunicorn style | Medium | S | Sprint 1 |
| Correlation ID middleware | Missing | `settings.py` middleware list | Middleware, contextvar, response header, tests | No cross-request traceability | Medium | S | Sprint 1 |
| OpenTelemetry | Missing | None | OTEL SDK, Django/DB/Redis instrumentation, collector config | Incidents will rely on logs only | Medium | M | Sprint 2 or 10 |
| PostGIS database | Missing | `docker-compose.yml` uses `postgres:16-alpine` | PostGIS image/extension, GeoDjango config, migration plan | Decimal lat/lng fields limit serviceability/scoring | High | M | Sprint 4 |
| Restaurant coordinates | Partially implemented | `Restaurant.pickup_latitude`, `pickup_longitude` | `PointField`, geography indexes, backfill migration | Haversine math is app-side | High | M | Sprint 4 |
| Customer coordinates | Partially implemented | `Order.latitude`, `Order.longitude`, `DeliveryAddress.latitude`, `longitude` | Address `PointField`, geocoding confidence, service zone relation | No geocoding/provider abstraction | Medium | M | Sprint 4 |
| Partner presence | Partially implemented | `DeliveryPartner.current_latitude`, `current_longitude`, `location_updated_at` | Presence stream/cache, location history, anti-fraud checks | Hot writes hit partner table | High | M | Sprint 4 |
| Candidate generation | Partially implemented | `delivery/services.py` | PostGIS radius query, scoring table, capacity rules | Iterates Python-side over partners | High | M | Sprint 4 |
| Shared delivery offers | Partially implemented | `delivery/services.py`, `PartnerDashboardPage.jsx`, `Notification` | Durable `DeliveryOffer` rows, expiry, accepted/rejected states | Notification rows are used as offer visibility | High | L | Sprint 8 |
| Atomic assignment | Partially implemented | `claim_pending_delivery`, `select_for_update` | Idempotency key, offer-state validation, conflict metrics | Works for basic claim, but offer audit is missing | Medium | S | Sprint 8 |
| Offer expiry and redispatch | Partially implemented | `offer_radius_km`, `dispatch_worker.py` | Durable expiry timestamps, retry waves, redispatch after rejection/timeout | Infinite loop has no job state | High | M | Sprint 8 |
| Live delivery tracking | Partially implemented | `updateDeliveryLocation`, `OrderTrackingPage.jsx`, partner location button | WebSocket/SSE channels, customer live subscription, presence TTL | Tracking likely depends on polling/API refresh | Medium | M | Sprint 7 |
| Channels/WebSockets | Missing | `requirements.txt` includes channels, `asgi.py` default | ASGI routing, consumers, auth, channel layers, Docker ASGI server | Running Gunicorn WSGI only | Medium | M | Sprint 7 |
| Push notifications | Missing | `Notification` DB model | Provider interface, device tokens, web push/FCM adapters | In-app notifications only | Medium | L | Sprint 7 |
| Batch/stacked delivery | Missing | None | Delivery route, stop sequence, capacity scoring | Current model assumes one order per delivery | Medium | XL | Phase C |
| ETA prediction | Partially implemented | `Order.estimated_delivery_at`, serviceability tests | ETA model/service, travel time source, prediction feedback | ETA is simple deterministic estimate | Medium | L | Phase C |
| GPS fraud resistance | Missing | None | Speed checks, impossible jumps, device trust, partner risk score | Location updates are trusted | Medium | M | Phase B/C |
| AI/ML platform | Missing | None | Event dataset, feature store, model registry, recommendation service | No analytics event stream yet | Low now, High later | XL | Phase D |
| Personalized home feed | Missing | `HomePage.jsx`, `SearchPage.jsx` static/filter browsing | Ranking service, user features, market-aware feed | Current browse is simple and explainable | Low | L | Phase C |
| Demand forecasting | Missing | None | Historical order features, forecast jobs, merchant insights | No data mart | Low | XL | Phase C/D |
| Merchant AI assistant | Missing | None | AI provider abstraction, content safety, merchant data tools | Not needed before merchant workflows stabilize | Low | L | Phase D |
| AWS production architecture | Missing | Docker local stack only | ECS/RDS/ElastiCache/S3/CloudFront/TLS/IAM | Deployment is local Docker Compose | High for launch | XL | Sprint 10/Phase B |
| Nginx/Gunicorn runtime | Implemented locally | `docker-compose.yml`, backend/frontend Dockerfiles | Production TLS, static/media storage, blue-green deploy | Media is a local volume | Medium | M | Sprint 10 |
| CI pipeline | Missing | No workflow files found | Backend tests, migrations, frontend build, lint, container scan | Verification is manual | High | M | Sprint 10, earlier as Phase A guardrail |
| Security/RBAC/audit | Partially implemented | JWT auth, role checks, operations views | Permission classes, audit log, admin action history, object-level policy | Role checks are hand-coded in views | High | M | Sprint 10 |
| Investor KPI tree | Partially implemented | `OperationsDashboardPage.jsx`, `api/operations_views.py` | KPI snapshots, cohort metrics, unit economics dashboard | Ops summary is live aggregate only | Medium | L | Phase B |
| Unit economics | Partially implemented | fee/payout fields | Contribution margin model, promo cost, COD loss tracking | No ledger or accounting views | High | L | Sprint 9/Phase B |
| Merchant operating system | Partially implemented | Merchant dashboard, item/hours/orders | Inventory, analytics, prep SLAs, self-service promotions | Merchant dashboard is operational but early | Medium | L | Phase B |
| Cross-vertical commerce | Missing | Food-specific models and copy | Category-agnostic catalog, fulfillment types, grocery/parcel rules | `FoodItem` naming embeds food domain | Medium | XL | Phase C |
| Competitive dispatch intelligence | Partially implemented | shared claim, waves, partner location | Scored dispatch, reliable offers, batching, real-time tracking | Current dispatch is useful but not yet defensible | High | XL | Sprints 4, 7, 8 |
| Safe code-generation process | Partially implemented | Tests exist, docs exist | CI enforcement, feature flags, migration checklist in PRs | Discipline depends on manual execution | Medium | S | Sprint 10 plus immediate guardrails |

## Phase Plan

### Phase A: Build Immediately

These protect the platform before more product complexity is added.

1. Baseline verification: backend tests, migrations check, frontend build.
2. Sprint 1 foundation: `Market`, `Currency`, Money utility, nullable `market_id` fields, transactional outbox/inbox, event relay, `order.created`, `order.status_changed`.
3. Correlation ID middleware and structured JSON logs.
4. Celery foundation with separate queues for critical, dispatch, notifications, and maintenance.
5. Move unpaid order expiry, outbox relay, and notification sending into idempotent background tasks.
6. Add CI checks early, even before full Sprint 10, so every later sprint is protected.
7. Add feature flags for market scoping, event publishing, Celery notifications, WebSockets, and catalog v2.

### Phase B: Wait Until Product-Market Fit

These improve merchant/customer/partner depth once the first operating zone proves demand.

1. Organization, Brand, Location, FulfillmentNode.
2. Catalog v2 with products, variants, modifiers, and inventory reservations.
3. Tax and fee quote snapshots.
4. Durable delivery offers, expiry, reject/timeout/redispatch.
5. WebSocket tracking and push notification provider abstraction.
6. Ledger shadow mode, then payout reconciliation.
7. Merchant analytics, service-quality metrics, prep-time controls.
8. GPS quality checks and simple fraud rules.

### Phase C: Wait Until 100,000 Users

These are scale and market-expansion accelerators.

1. PostGIS optimization beyond basic migration: geo indexes, service zones, heatmaps, active-partner indexes.
2. Read replicas and reporting replicas.
3. Partitioning for orders, events, notifications, and location history.
4. Search/ranking index for restaurants and catalog.
5. Batch/stacked delivery and advanced ETA.
6. KPI warehouse, cohort dashboards, and unit-economics reporting.
7. Cross-vertical catalog for grocery, pharmacy, parcel, and local commerce.
8. Production AWS rollout with autoscaling and stronger DR.

### Phase D: Wait Until 1,000,000 Users

These should not be built now unless usage proves the need.

1. Market-cell architecture and regional control plane.
2. Microservice extraction for dispatch, payments/ledger, notifications, and search.
3. Data lake, feature store, ML model registry, and online features.
4. AI personalization, demand forecasting, fraud ML, and merchant AI assistant.
5. EKS migration if ECS/Fargate becomes limiting.
6. Multi-region active-active strategy.
7. Ads marketplace and sponsored ranking engine.

## Prioritized Engineering Backlog

1. Protect the current app with repeatable tests and CI.
2. Add market/currency primitives without changing existing API responses.
3. Add Money utility and keep decimal fields as backward-compatible storage.
4. Add nullable `market_id` to restaurants, orders, customers, delivery partners, addresses, offers, payments, notifications.
5. Backfill default market and add indexes.
6. Add transactional outbox/inbox and event publisher.
7. Publish `order.created` and `order.status_changed` from existing order creation/status paths.
8. Add event relay worker and tests for retry/idempotency.
9. Add correlation ID middleware and structured logging.
10. Add Celery app, queues, workers, beat, and task base.
11. Move dispatch loop responsibilities into Celery tasks.
12. Move notification writes/sends into asynchronous tasks.
13. Add Organization/Brand/Location/FulfillmentNode while preserving Restaurant APIs.
14. Add PostGIS fields next to decimal coordinate fields.
15. Backfill points from current lat/lng values.
16. Use PostGIS for serviceability and partner candidate generation behind a flag.
17. Add catalog v2 models and compatibility serializers.
18. Add inventory reservations behind checkout validation.
19. Add pricing quote and tax snapshot.
20. Add WebSocket order tracking.
21. Add durable delivery offers and redispatch.
22. Add push provider abstraction.
23. Add ledger shadow mode.
24. Add payout reconciliation.
25. Harden production deployment and observability.

## Next 50 Implementation Tasks In Exact Order

1. Run `python manage.py test api` from `backend` and record the baseline result.
2. Run `python manage.py makemigrations --check --dry-run` from `backend`.
3. Run `npm.cmd run build` from `frontend`.
4. Add feature flag settings: `MARKETS_ENABLED`, `OUTBOX_ENABLED`, `CELERY_NOTIFICATIONS_ENABLED`.
5. Create `backend/markets` Django app.
6. Add `Currency` model with code, numeric code, symbol, name, minor unit, active flag.
7. Add `Market` model with slug, country code, name, timezone, default currency, active flag.
8. Register `markets` in `INSTALLED_APPS`.
9. Add market admin classes.
10. Create market/currency migrations.
11. Add data migration for the initial default market and currency.
12. Add backend tests for currency and market creation/backfill.
13. Add `markets/money.py` with Decimal-safe `Money` utility and rounding helpers.
14. Add Money utility tests for rounding and currency mismatch.
15. Add nullable `market` FK to `Restaurant`.
16. Add nullable `market` FK to `Order`.
17. Add nullable `market` FK to `Customer`.
18. Add nullable `market` FK to `DeliveryAddress`.
19. Add nullable `market` FK to `DeliveryPartner`.
20. Add nullable `market` FK to `Offer`.
21. Add nullable `market` FK to `Payment`.
22. Add nullable `market` FK to `Notification`.
23. Create safe schema migration for nullable market fields and indexes.
24. Add data migration to backfill all existing rows to the default market.
25. Update create flows to set default market when caller does not provide one.
26. Add tests proving old order, merchant, partner, address, and notification APIs still work without `market_id`.
27. Create `backend/events` Django app.
28. Add `OutboxEvent` model with event id, name, version, aggregate type/id, payload, headers, status, attempts, available_at, published_at.
29. Add `InboxEvent` model with event id, consumer name, status, attempts, payload hash, processed_at.
30. Register `events` in `INSTALLED_APPS`.
31. Add events admin classes.
32. Create events migrations and indexes.
33. Add event envelope builder with correlation ID support.
34. Add transactional `publish_event()` helper using `transaction.on_commit`.
35. Add inbox `claim_inbox_event()` helper for idempotent consumers.
36. Add tests for outbox creation inside a transaction and rollback behavior.
37. Add tests for inbox duplicate handling.
38. Add correlation ID contextvar utility.
39. Add correlation ID middleware accepting `X-Correlation-ID` or generating UUID.
40. Add middleware to `MIDDLEWARE`.
41. Add tests for response `X-Correlation-ID` and context propagation.
42. Add structured JSON logging config with correlation ID filter.
43. Add tests or smoke assertions for log filter behavior.
44. Publish `order.created.v1` when checkout creates a new order.
45. Publish `order.status_changed.v1` when order status changes.
46. Add tests for order event payloads and no duplicate event on unchanged status.
47. Add `events` management command `relay_outbox_events`.
48. Implement relay claiming with `select_for_update(skip_locked=True)` where supported, retry counts, and failed state.
49. Add relay tests for success, retry, and idempotent republish.
50. Run backend tests, migration check, frontend build, then update Sprint 1 status docs.

## First Coding Task To Start Today

Start with task 5: create the `markets` app, then implement `Currency` and `Market` models plus the initial default-market data migration.

Why this first: every scalable feature in the package depends on knowing which country/market a restaurant, order, customer, partner, payment, and notification belongs to. It is small, safe, backward-compatible, and does not disturb the working customer, merchant, partner, or admin flows.

Backward compatibility rules for this first task:

- Keep all existing API request bodies valid.
- Do not require clients to send `market_id`.
- Use one default active market for all existing rows.
- Keep all existing amount fields as decimals for now.
- Do not rename `Restaurant`, `FoodItem`, `Order`, `Delivery`, or `Payment`.
- Add fields as nullable first, backfill, then enforce stricter constraints only in a later sprint.

