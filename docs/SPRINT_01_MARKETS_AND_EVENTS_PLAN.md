# Sprint 1 Executable Plan: Markets, Money, Events and Request Tracing

Duration: 10 engineering days  
Scope: Backend foundation plus deployment wiring  
Architecture: Modular monolith  
Release strategy: Expand, backfill, verify, contract  
Baseline requirement: All current APIs and all 80 existing backend tests remain green

## 1. Sprint Goal

Introduce the first multi-country and event-driven foundations without changing current customer, merchant, partner, payment or dispatch behavior.

Sprint 1 delivers:

- `Currency` and `Market` reference models seeded with INR/India.
- A strict `Money` value object for new domain code.
- Safe market ownership on Customer, Restaurant, Offer, Order and DeliveryPartner.
- An order currency snapshot.
- Transactional outbox and idempotent inbox tables.
- A durable Redis Streams relay worker.
- Versioned `order.created.v1` and `order.status_changed.v1` events.
- Correlation/request IDs propagated into logs and event envelopes.
- Structured JSON application logs.
- Feature flags and rollback controls.

Out of scope: Kafka, Celery routing, WebSockets, PostGIS, model extraction, changing financial calculations, changing frontend currency labels, or creating microservices. Those begin in later sprints.

## 2. Non-Negotiable Compatibility Rules

1. Keep every existing URL and response field. New response fields are additive only.
2. Default all existing data and traffic to market `IN` and currency `INR`.
3. Existing Decimal database columns remain unchanged. `Money` wraps them in new domain code; it is not a custom Django field.
4. Do not publish events directly to Redis inside order transactions. Transactions write only to `OutboxEvent`.
5. Relay delivery is at-least-once. Consumers must use `InboxEvent` for deduplication.
6. Events contain identifiers and commercial snapshots, not addresses, phone numbers, passwords or payment secrets.
7. All event and market behavior is guarded by settings so it can be disabled without rolling back schema.
8. No destructive migration and no non-null column added to a populated table in one production step.

## 3. Module Layout

Create two bounded Django apps and one infrastructure package:

```text
backend/
  markets/
    admin.py
    apps.py
    defaults.py
    models.py
    money.py
    serializers.py
    urls.py
    views.py
    migrations/
    tests/
  events/
    admin.py
    apps.py
    contracts.py
    context.py
    inbox.py
    models.py
    publisher.py
    relay.py
    transports.py
    management/commands/relay_events.py
    migrations/
    tests/
  fooddelivery/
    logging.py
    middleware.py
```

`markets` owns country/currency policy. `events` owns event durability and transport. `fooddelivery` keeps HTTP/process configuration only.

## 4. Models

### 4.1 Currency

File: `backend/markets/models.py`

```text
Currency
  code              CharField(3), primary key, uppercase ISO-4217
  name              CharField(80)
  symbol            CharField(8)
  decimal_places    PositiveSmallIntegerField(default=2)
  is_active         BooleanField(default=True)
  created_at        DateTimeField(auto_now_add=True)
  updated_at        DateTimeField(auto_now=True)
```

Constraints:

- `code` must match `^[A-Z]{3}$` through model validation and serializer validation.
- `decimal_places` allowed range is 0-4.
- Currency rows are reference data. API deletion is not exposed.

Seed in migration:

```text
INR | Indian Rupee | Rs. | 2
GNF | Guinean Franc | FG | 0
```

GNF is seeded now so the utility is tested against a zero-decimal currency. Guinea market activation is not part of Sprint 1.

### 4.2 Market

File: `backend/markets/models.py`

```text
Market
  code                 CharField(16), primary key, e.g. IN
  name                 CharField(80)
  country_code         CharField(2), unique, uppercase ISO-3166-1 alpha-2
  default_currency     ForeignKey(Currency, PROTECT)
  default_locale       CharField(16), default en-IN
  timezone             CharField(64), default Asia/Kolkata
  is_active            BooleanField(default=True)
  metadata             JSONField(default=dict, blank=True)
  created_at           DateTimeField(auto_now_add=True)
  updated_at           DateTimeField(auto_now=True)
```

Seed active India market:

```text
IN | India | IN | INR | en-IN | Asia/Kolkata
```

Do not seed an active Guinea market yet. It should be created only when gateway, tax and operational policies are ready.

### 4.3 Market ownership on existing models

Add `market = ForeignKey(Market, PROTECT, null=True, db_index=True)` during the expand migration to:

- `customers.Customer`
- `restaurants.Restaurant`
- `orders.Offer`
- `orders.Order`
- `delivery.DeliveryPartner`

Add `currency = ForeignKey(Currency, PROTECT, null=True)` to `orders.Order`. This is the immutable order currency snapshot. It defaults from `order.market.default_currency` when creating new orders.

Do not add market fields to FoodItem, Delivery, Payment, DeliveryAddress or Notification in Sprint 1. Their market is unambiguous through Restaurant, Order or Customer. Add direct market keys later only when query volume proves they are needed.

Runtime defaults:

- `markets.defaults.get_default_market_id()` reads `settings.DEFAULT_MARKET_CODE` and returns `IN` by default.
- `markets.defaults.get_default_currency_id()` reads the default market's currency and returns `INR` by default.
- Existing model creation in tests and legacy views continues to work without supplying market/currency.
- `OrderCreateSerializer` explicitly copies market and currency from the first item's Restaurant. It does not trust a client-supplied market.
- New Restaurant creation uses the authenticated merchant profile market if present; in Sprint 1, it falls back to the default market.
- New DeliveryPartner and Customer profiles default to the configured market.

### 4.4 OutboxEvent

File: `backend/events/models.py`

```text
OutboxEvent
  id                    UUIDField(primary_key=True, default=uuid4)
  topic                 CharField(100, db_index=True)
  event_type            CharField(120, db_index=True)
  schema_version        PositiveSmallIntegerField(default=1)
  aggregate_type        CharField(80)
  aggregate_id          CharField(80)
  aggregate_version     PositiveBigIntegerField(null=True)
  market                ForeignKey(Market, PROTECT, null=True)
  correlation_id        UUIDField(null=True, db_index=True)
  causation_id          UUIDField(null=True)
  payload               JSONField(default=dict)
  headers               JSONField(default=dict, blank=True)
  status                CharField(PENDING/PROCESSING/PUBLISHED/FAILED)
  available_at          DateTimeField(default=timezone.now, db_index=True)
  claimed_at            DateTimeField(null=True)
  published_at          DateTimeField(null=True)
  attempts              PositiveSmallIntegerField(default=0)
  last_error            TextField(blank=True)
  created_at            DateTimeField(auto_now_add=True)
```

Indexes:

- `(status, available_at, created_at)` for relay claims.
- `(aggregate_type, aggregate_id, created_at)` for investigation.
- `(event_type, created_at)` for audit/search.

No code updates or deletes outbox rows except a future retention task. Admin fields are read-only.

### 4.5 InboxEvent

File: `backend/events/models.py`

```text
InboxEvent
  id               BigAutoField/AutoField according to project default
  consumer_name    CharField(120)
  event_id         UUIDField()
  event_type       CharField(120)
  status           CharField(PROCESSING/PROCESSED/FAILED)
  attempts         PositiveSmallIntegerField(default=0)
  received_at      DateTimeField(auto_now_add=True)
  processed_at     DateTimeField(null=True)
  last_error       TextField(blank=True)
```

Constraint: unique `(consumer_name, event_id)`.

`events.inbox.process_once(consumer_name, envelope, handler)` creates the inbox row and runs the handler in one database transaction. A duplicate processed event returns `False` without invoking the handler. A failed handler records failure and re-raises; retry behavior is explicit and tested.

## 5. Money Utility

File: `backend/markets/money.py`

Implement immutable `Money` as a frozen dataclass:

```text
Money(amount: Decimal, currency: str, decimal_places: int)
```

Required behavior:

- Construct only from Decimal, string or integer. Reject float.
- Normalize currency to uppercase.
- Quantize using `ROUND_HALF_UP` and the currency decimal places.
- Support addition/subtraction/comparison only when currency matches.
- Support multiplication by Decimal/integer.
- Expose `to_minor_units()`, `from_minor_units()`, `as_dict()` and `zero()`.
- Raise `CurrencyMismatch` for cross-currency arithmetic.
- Never fetch the database implicitly. `Money.from_currency_model()` is the explicit adapter.

Sprint 1 does not replace all existing Decimal calculations. Use Money first in event payload construction and new market-aware tests. Pricing conversion happens incrementally in later sprints.

## 6. Event Contracts

File: `backend/events/contracts.py`

Common envelope:

```json
{
  "event_id": "uuid",
  "event_type": "order.created.v1",
  "schema_version": 1,
  "occurred_at": "ISO-8601 UTC",
  "topic": "orders",
  "market_id": "IN",
  "aggregate_type": "order",
  "aggregate_id": "123",
  "aggregate_version": 1,
  "correlation_id": "uuid-or-null",
  "causation_id": null,
  "payload": {}
}
```

### order.created.v1 payload

```json
{
  "order_id": 123,
  "customer_id": 45,
  "restaurant_id": 7,
  "status": "PLACED",
  "currency": "INR",
  "subtotal_amount": "280.00",
  "discount_amount": "0.00",
  "delivery_fee": "30.00",
  "total_amount": "310.00",
  "created_at": "ISO-8601 UTC"
}
```

### order.status_changed.v1 payload

```json
{
  "order_id": 123,
  "previous_status": "CONFIRMED",
  "status": "PREPARING",
  "source": "MERCHANT",
  "status_event_id": 999,
  "changed_at": "ISO-8601 UTC"
}
```

Use strings for money in JSON. Do not include customer name, address, phone, coordinates, confirmation code, payment token or gateway secret.

## 7. Transaction Boundary and Publishing

Current order transitions occur in multiple modules but all call `Order.save()`. Current `orders.signals` already records timeline events through pre/post-save signals.

Implementation:

1. Override `Order.save()` with a narrow `transaction.atomic()` wrapper around `super().save()` so the order row, timeline event and outbox row commit or roll back together for current call sites.
2. Keep `remember_previous_order_status` unchanged except for testable helper extraction.
3. Extend `record_order_status_event`:
   - On create: create the existing PLACED timeline row, then enqueue `order.created.v1`.
   - On later status change: create the existing timeline row, then enqueue `order.status_changed.v1`.
   - On unrelated save: create neither timeline nor outbox event.
4. `events.publisher.publish()` only inserts an OutboxEvent. It must assert `connection.in_atomic_block` when `EVENT_OUTBOX_REQUIRE_TRANSACTION=True`.
5. Keep direct model saves working for all current API, admin, legacy and test paths.
6. Document that `QuerySet.update()`/`bulk_update()` must never change Order.status because they bypass signals. Add a regression test and a code comment near the model manager.

Feature flag:

- `EVENT_OUTBOX_ENABLED=False` skips outbox insertion but preserves the timeline.
- Local and test default: `True`.
- Production deployment can start `False`, apply/backfill migrations, then enable before starting the relay.

## 8. Event Relay Worker

### Transport

File: `backend/events/transports.py`

Define an interface:

```text
EventTransport.publish(envelope) -> transport_message_id
```

Implement:

- `RedisStreamTransport`: `XADD` to `EVENT_STREAM_KEY` (default `tfood:domain-events`) with `event_id`, `event_type`, `topic` and compact JSON envelope.
- `MemoryTransport`: tests only.

Do not use Redis Pub/Sub because it does not provide durable replay.

### Claim/publish algorithm

File: `backend/events/relay.py`

1. In a short transaction, select eligible PENDING events and stale PROCESSING events with `select_for_update(skip_locked=True)` ordered by creation.
2. Mark them PROCESSING, increment attempts, set claimed_at, then commit.
3. Publish outside the database transaction.
4. On success, mark PUBLISHED and set published_at.
5. On failure, store a truncated error and set:
   - PENDING with exponential backoff while attempts < max attempts.
   - FAILED after max attempts.
6. A crashed relay is recovered when PROCESSING is older than `EVENT_RELAY_VISIBILITY_TIMEOUT_SECONDS`.
7. Duplicate Redis entries are permitted; inbox deduplication is mandatory.

### Process

File: `backend/events/management/commands/relay_events.py`

Options:

- `--once`
- `--batch-size`
- `--poll-seconds`
- `--max-attempts`

Add Docker Compose service:

```text
event_relay:
  build: ./backend
  environment:
    SERVICE_MODE: event_relay
    same DB/Redis/market/event variables as backend
  depends_on:
    backend: healthy
```

Update `entrypoint.sh`:

```text
SERVICE_MODE=event_relay -> python manage.py relay_events
```

Celery tasks in Sprint 1: **none**. This is intentional. Sprint 2 introduces Celery queue topology and can schedule relay recovery/retention while the always-on relay remains independent. Mixing Celery bootstrap into this sprint would make event durability harder to isolate and test.

## 9. Correlation IDs and Structured Logging

### Context

File: `backend/events/context.py`

Use `contextvars.ContextVar` for:

- `request_id`
- `correlation_id`
- `causation_id`

Provide getters and a context manager so HTTP, management commands and future Celery tasks use the same API.

### Middleware

File: `backend/fooddelivery/middleware.py`

`CorrelationIdMiddleware` runs immediately after SecurityMiddleware.

Behavior:

1. Accept `X-Request-ID` and `X-Correlation-ID` only when each parses as UUID.
2. Generate UUID4 when absent or invalid.
3. Store both in context variables for the request lifetime.
4. Return `X-Request-ID` and `X-Correlation-ID` response headers.
5. Clear context variables in `finally` to prevent Gunicorn worker leakage.
6. Do not use arbitrary caller text as a log field.

### JSON logs

File: `backend/fooddelivery/logging.py`

Implement a standard-library JSON formatter to avoid another dependency. Every application log contains:

```text
timestamp, level, logger, message, request_id, correlation_id,
event_type, aggregate_id, exception
```

Configure Django `LOGGING` in settings:

- JSON to stdout when `STRUCTURED_LOGGING=True`.
- Human-readable console formatter for local development when false.
- Do not log request bodies, authorization headers, cookies or event payloads by default.
- Relay logs event ID/type, attempt, duration and result.

Nginx/Gunicorn access-log JSON is deferred to the observability sprint. Sprint 1 guarantees structured Django and worker logs.

## 10. API Changes

New public read-only endpoints:

```text
GET /api/v1/markets/
GET /api/v1/markets/{code}/
```

Response fields: code, name, country_code, currency code/symbol/decimal_places, default_locale and timezone. Return active markets only. Permissions: AllowAny. Cache for 5 minutes through Django cache.

Additive changes to existing responses:

- Restaurant serializers: `market_code`.
- Order serializers: `market_code`, `currency_code`.
- Customer/partner profile serializers: `market_code` read-only in Sprint 1.

Do not accept market from order checkout. Market is server-derived from Restaurant. Merchant/customer market switching requires a dedicated validated flow in a later sprint.

No outbox/inbox API is public. Operators inspect them through read-only Django admin initially.

## 11. Frontend Scope

No page redesign in Sprint 1.

Add:

- `frontend/src/api/markets.js`: list/get market configuration.
- `frontend/src/context/MarketContext.jsx`: load active/default market, falling back to `{code: 'IN', currency: 'INR', locale: 'en-IN'}`.
- `frontend/src/utils/money.js`: `Intl.NumberFormat` wrapper using market metadata.

Wire `MarketProvider` behind `VITE_MARKET_CONTEXT_ENABLED=false`. Do not replace every existing `Rs.` label in this sprint. Enable the provider in tests and convert one non-critical summary component as a proof; broad UI localization belongs to the localization sprint.

Backward compatibility: with the flag off, the rendered application is byte-for-byte behaviorally equivalent regarding currency labels.

## 12. Database Migration Sequence

Use two deployments. Do not combine expand and contract migrations.

### Deployment A: expand and backfill

1. `markets.0001_initial`
   - Create Currency and Market.
   - Seed INR, GNF and active IN.
2. `events.0001_initial`
   - Create OutboxEvent and InboxEvent with indexes/constraints.
3. `customers.0010_customer_market_expand`
   - Add nullable indexed market FK.
4. `restaurants.0012_restaurant_market_expand`
   - Add nullable indexed market FK.
5. `orders.0019_order_market_currency_expand`
   - Add nullable market to Offer and Order.
   - Add nullable currency to Order.
6. `delivery.0008_partner_market_expand`
   - Add nullable indexed market FK.
7. Management command `backfill_markets --batch-size 1000`
   - Uses primary-key batches and `update()` to avoid loading all rows.
   - Is idempotent and reports counts.
   - Sets Order market from first order item's Restaurant where possible, otherwise IN.
   - Sets Order currency from its resolved market.
8. Verification command `verify_market_backfill` fails if any target field is null or inconsistent.

Run application code in dual-read mode:

```text
resolved_market = object.market or default_market
```

### Deployment B: contract

After verification and at least one successful staging smoke cycle:

1. `customers.0011_customer_market_required`
2. `restaurants.0013_restaurant_market_required`
3. `orders.0020_order_market_currency_required`
4. `delivery.0009_partner_market_required`

These alter fields to non-null and install runtime defaults where needed. Before applying, run `verify_market_backfill` in the deployment pipeline.

At current local volume both deployments can happen on the same day, but keep separate migration files so production growth does not force a rewrite.

## 13. Tests

### Markets and Money

Files:

- `backend/markets/tests/test_models.py`
- `backend/markets/tests/test_money.py`
- `backend/markets/tests/test_api.py`
- `backend/markets/tests/test_backfill.py`

Cases:

- ISO code normalization/validation.
- INR two-decimal and GNF zero-decimal quantization.
- Float rejection.
- Currency mismatch arithmetic rejection.
- Minor-unit conversion and JSON string serialization.
- Active markets API and inactive market exclusion.
- Default market assigned to direct legacy model creation.
- Order market/currency derived from Restaurant, not request data.
- Backfill is idempotent and resolves historical order market.

### Outbox and Inbox

Files:

- `backend/events/tests/test_publisher.py`
- `backend/events/tests/test_relay.py`
- `backend/events/tests/test_inbox.py`
- `backend/events/tests/test_order_events.py`

Cases:

- Order creation creates one timeline event and one `order.created.v1` outbox event.
- Status change creates one timeline event and one `order.status_changed.v1` event.
- Non-status Order.save creates no outbox duplicate.
- Transaction rollback persists neither order/timeline nor outbox.
- Publisher rejects use outside a transaction when enforcement is enabled.
- Payload contains exact allow-listed keys and no PII.
- Relay claims with SKIP LOCKED on PostgreSQL.
- Successful publish marks PUBLISHED.
- Failure stores error, applies backoff and retries.
- Stale PROCESSING event is reclaimed.
- Max attempts produces FAILED.
- Inbox invokes handler once across duplicate deliveries.
- Failed inbox handler is recorded and can be retried according to policy.
- Feature flag off preserves order/timeline behavior and creates no outbox row.

### Correlation and logging

Files:

- `backend/events/tests/test_context.py`
- `backend/fooddelivery/tests/test_middleware.py`
- `backend/fooddelivery/tests/test_logging.py`

Cases:

- Valid inbound UUID is preserved.
- Invalid/missing ID is replaced.
- IDs appear in response headers.
- IDs do not leak to the next request.
- Order event created in request context contains the correlation ID.
- JSON log line parses and contains required keys.
- Secrets and request body are absent.

### Regression

- Run all existing `api` tests after each model/event checkpoint.
- Add one full checkout test asserting existing response values plus additive market/currency fields.
- Add one merchant, partner and payment status transition event test because these paths currently live in separate modules.
- Frontend build and MarketContext fallback unit test.

Expected backend test count after Sprint 1: approximately 110-125.

## 14. Exact Implementation Order

### Day 1: Safety baseline

1. Create a working branch/checkpoint.
2. Run and record current tests, migration check and frontend build.
3. Add settings flags and environment documentation with behavior disabled.
4. Create empty `markets` and `events` apps and register them.

Checkpoint: no migrations yet; all existing tests pass.

### Day 2: Currency, Market and Money

1. Implement models and admin.
2. Create/inspect `markets.0001_initial` and reference-data migration.
3. Implement Money utility.
4. Add model/Money tests.
5. Add read-only market API.

Checkpoint: market tests and existing API tests pass.

### Day 3: Expand market columns

1. Add nullable market/currency fields to domain models.
2. Generate one expand migration per owning app.
3. Add default-resolution helpers and dual-read properties.
4. Modify OrderCreateSerializer to derive market/currency from Restaurant.
5. Add additive serializer fields.

Checkpoint: migration check clean; all existing tests pass without modifying their factories.

### Day 4: Backfill and contract preparation

1. Implement batched backfill and verification commands.
2. Test idempotency and historical order fallback.
3. Run against a copy/backup of local PostgreSQL data.
4. Generate but do not yet deploy required-field contract migrations.

Checkpoint: zero target nulls and no changed order totals/statuses.

### Day 5: Outbox/inbox persistence

1. Implement models, indexes, admin and migrations.
2. Implement event envelope/contracts.
3. Implement transaction-enforcing publisher.
4. Implement inbox `process_once` helper.
5. Add persistence/idempotency tests.

Checkpoint: no order publishing wired yet; persistence tests pass.

### Day 6: Order event integration

1. Add the narrow atomic Order.save boundary.
2. Extend the existing order timeline signal to enqueue events.
3. Add created/status-changed/no-op/rollback tests.
4. Exercise customer cancel, payment confirmation, merchant preparation, delivery and expiry transitions.

Checkpoint: all old timeline tests pass unchanged; exactly one outbox event per semantic transition.

### Day 7: Relay worker

1. Implement transport interface and Redis Streams adapter.
2. Implement claim, publish, backoff, failure and stale recovery.
3. Implement `relay_events` command.
4. Add isolated unit tests with MemoryTransport and PostgreSQL concurrency integration test.

Checkpoint: a committed test event appears in Redis Stream and is marked PUBLISHED.

### Day 8: Correlation and logs

1. Implement context variables and middleware.
2. Register middleware after SecurityMiddleware.
3. Implement JSON formatter and settings configuration.
4. Propagate correlation ID into publisher.
5. Add context/middleware/log tests.

Checkpoint: one checkout request, its order event and relay log share a correlation ID.

### Day 9: Deployment and frontend compatibility

1. Add event_relay Docker service and health/operational logging.
2. Add environment variables to `.env.example` and Compose.
3. Add frontend MarketContext/money helper behind flag.
4. Build containers and run Deployment A migrations/backfill/verify.
5. Start relay only after outbox feature is enabled.

Checkpoint: current app remains usable at port 8088; services healthy.

### Day 10: Contract and release verification

1. Run full backend tests and frontend build.
2. Run a self-cleaning live order/event smoke test.
3. Apply required-field migrations only after verification passes.
4. Test feature-flag rollback: stop relay and disable publishing without affecting ordering.
5. Document event replay/failure runbook and release notes.

Checkpoint: Sprint acceptance criteria all met.

## 15. Files Likely to Change

Existing backend files:

```text
backend/fooddelivery/settings.py
backend/orders/models.py
backend/orders/signals.py
backend/api/serializers.py
backend/api/urls.py
backend/customers/models.py
backend/restaurants/models.py
backend/delivery/models.py
backend/entrypoint.sh
backend/requirements.txt (only if a dependency proves necessary; none planned)
```

Deployment/configuration:

```text
docker-compose.yml
.env.example
README.md
```

Frontend:

```text
frontend/src/main.jsx
frontend/src/api/markets.js
frontend/src/context/MarketContext.jsx
frontend/src/utils/money.js
```

New apps/files are listed in Section 3. Migration filenames are listed in Section 12.

## 16. Settings and Feature Flags

Add:

```text
DEFAULT_MARKET_CODE=IN
EVENT_OUTBOX_ENABLED=True
EVENT_OUTBOX_REQUIRE_TRANSACTION=True
EVENT_TRANSPORT=redis_stream
EVENT_STREAM_KEY=tfood:domain-events
EVENT_RELAY_ENABLED=True
EVENT_RELAY_BATCH_SIZE=100
EVENT_RELAY_POLL_SECONDS=1
EVENT_RELAY_MAX_ATTEMPTS=10
EVENT_RELAY_VISIBILITY_TIMEOUT_SECONDS=60
STRUCTURED_LOGGING=True
LOG_LEVEL=INFO
```

Frontend:

```text
VITE_MARKET_CONTEXT_ENABLED=false
```

Rollback order:

1. Set `EVENT_RELAY_ENABLED=False` or stop event_relay.
2. Set `EVENT_OUTBOX_ENABLED=False` if outbox inserts are implicated.
3. Leave additive schema in place.
4. Ordering, payment and dispatch continue synchronously as they do today.

## 17. Commands

Run from `D:\Mister T\t-food\work\T-food-clean` unless noted.

Baseline:

```powershell
cd backend
python manage.py test api
python manage.py makemigrations --check --dry-run
cd ..\frontend
npm.cmd run build
```

App creation and migrations:

```powershell
cd backend
python manage.py startapp markets
python manage.py startapp events
python manage.py makemigrations markets events customers restaurants orders delivery
python manage.py migrate --plan
python manage.py migrate
python manage.py backfill_markets --batch-size 1000
python manage.py verify_market_backfill
```

Focused tests during development:

```powershell
python manage.py test markets.tests
python manage.py test events.tests
python manage.py test api.test_order_timeline api.test_order_idempotency api.test_payments api.test_merchant_orders api.test_dispatch api.test_order_expiry
```

Relay smoke test:

```powershell
python manage.py relay_events --once --batch-size 10
docker compose exec redis redis-cli XRANGE tfood:domain-events - + COUNT 10
```

Full verification:

```powershell
python manage.py test api markets.tests events.tests fooddelivery.tests
python manage.py makemigrations --check --dry-run
python manage.py check --deploy
cd ..\frontend
npm.cmd run build
cd ..
docker compose build backend frontend event_relay
docker compose up -d
docker compose ps
```

Before any production-like migration, create and verify a database backup using the repository's documented `pg_dump` process.

## 18. Risks and Mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Signal emits duplicate events | Consumers perform duplicate side effects | Semantic change check plus inbox unique key and idempotent handlers |
| Order save is not atomic with signal writes | Lost event after committed state | Narrow atomic wrapper and rollback tests |
| Relay crashes after Redis XADD | Duplicate stream event | At-least-once contract and inbox deduplication |
| Relay holds DB lock during Redis call | Checkout/relay contention | Claim in short transaction, publish after commit |
| Large backfill locks tables | Production latency | Nullable expand, PK batches, separate contract deployment |
| Historical order has no items | Unknown market | Explicit default IN fallback with audit count |
| Client selects wrong market | Cross-market pricing/data issue | Server derives market from Restaurant; request field ignored/rejected |
| Event payload leaks PII | Privacy/security exposure | Exact allow-list contract tests |
| Redis unavailable | Outbox backlog grows | Checkout unaffected; relay backoff and backlog alert |
| Context leaks across requests | Incorrect tracing | Middleware finally-reset and sequential-request test |
| New response fields break strict clients | Rare schema validation failure | Add behind serializer flag if a known strict client exists; current React ignores unknown fields |

## 19. Acceptance Criteria

Sprint 1 is complete only when all are true:

1. India/INR reference data exists and all current key records have a non-null market after contract migration.
2. Every new Order has market and currency derived from its Restaurant.
3. Existing endpoint paths, request bodies and financial values are unchanged.
4. Existing 80 tests pass without weakening assertions.
5. New Market/Money/event/correlation tests pass.
6. A successful order creates exactly one durable `order.created.v1` event in the same DB transaction.
7. Each real status change creates exactly one `order.status_changed.v1`; unrelated saves create none.
8. Rolling back an order transaction leaves no outbox event.
9. Relay restart recovers stale work and may duplicate transport delivery without duplicating an inbox consumer side effect.
10. Redis outage does not prevent checkout or status transitions; events remain pending.
11. Request, order outbox event and relay logs share one correlation ID.
12. Structured logs are valid JSON and contain no request body or secrets.
13. Backfill and verification commands are idempotent.
14. Docker services, including `event_relay`, are healthy or operationally observable at `http://127.0.0.1:8088`.
15. Event publishing and relay can be disabled independently without rolling back database migrations.

## 20. Sprint Review Deliverables

- Migration plan output and zero-null verification report.
- Event contract examples for both order events.
- Redis Stream relay demonstration.
- Correlated JSON log sample from HTTP request through relay.
- Full test/build output.
- Backfill, relay failure and feature-flag rollback runbook.
- Updated architecture status in `NEXT_GENERATION_BLUEPRINT.md` marking Sprint 1 foundations as implemented only after deployment verification.
