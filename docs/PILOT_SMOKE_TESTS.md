# T-Food Pilot Smoke Tests

This checklist verifies that a freshly deployed T-Food Version 1.0 environment is ready for a pilot launch. It is intentionally short enough to run before every production release, while the full manual QA checklist remains the deeper certification pass.

## Preconditions

- Production environment variables are set and validated.
- Database migrations have been applied.
- Static files are collected or frontend image is rebuilt.
- Public media and private media volumes are mounted separately.
- Redis, Postgres/PostGIS, backend, frontend, Celery worker, Celery beat, and dispatch worker are running.
- At least one operations admin account exists.
- If payment providers are not configured, COD remains available for pilot smoke testing.
- External notification providers may be disabled; in-app and realtime notifications must still work.

## Recommended Demo Accounts

Create or verify these accounts before the pilot smoke test. Do not use production customer passwords in shared documents.

## Codespaces Demo Setup

Use this flow when testing with friends through a temporary GitHub Codespaces forwarded URL. Full details are in `docs/CODESPACES_DEMO_GUIDE.md`.

Start from the folder that contains `backend`, `frontend`, and `docker-compose.yml`.

```bash
cp -n .env.codespaces.example .env
docker compose --env-file .env build backend frontend celery_worker celery_beat dispatch_worker
docker compose --env-file .env up -d db redis
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
docker compose --env-file .env exec -T backend python manage.py migrate
docker compose --env-file .env exec -T backend python manage.py seed_guinea_demo
docker compose --env-file .env ps
```

Open the Codespaces **Ports** tab, set port `8088` to **Public**, and share only the forwarded `https://...-8088.app.github.dev/` URL with trusted testers.

Safety notes:

- Codespaces is temporary and the public link can change.
- Use demo/test data only.
- Do not upload real verification documents.
- Do not enter real payment card details.
- External email, SMS, WhatsApp, push, and Telegram delivery are inactive.
- Guinea online payment providers remain inactive until real credentials exist.
- Keep the tester group small.

For local, Codespaces, or disposable pilot testing, seed safe Guinea demo data with:

```bash
python manage.py seed_guinea_demo
```

The command is idempotent and can be run more than once. To remove only the clearly marked demo records, run:

```bash
python manage.py seed_guinea_demo --reset-demo
```

Never use these demo credentials in production.

| Actor | Email | Password | Demo state |
| --- | --- | --- | --- |
| Operations admin | `ops.guinea.demo@t-food.test` | `DemoPass123!` | Active global operations profile |
| Customer | `customer.guinea.demo@t-food.test` | `DemoPass123!` | Customer profile and Conakry delivery address |
| Merchant owner | `merchant.guinea.demo@t-food.test` | `DemoPass123!` | Verified merchant company |
| Merchant staff | `staff.guinea.demo@t-food.test` | `DemoPass123!` | Verified active branch manager assigned to Conakry Grill |
| Delivery partner | `rider.guinea.demo@t-food.test` | `DemoPass123!` | Verified available rider |

Seeded Guinea demo data includes:

- Market: Guinea (`GN`, `GNF`, `Africa/Conakry`)
- City: Conakry
- Areas: Kaloum, Ratoma, Matoto, Dixinn, Matam
- Branches: Conakry Grill, Fresh Market Conakry, Sante Plus Pharmacy
- COD payment provider active
- Wave, Orange Money, and MTN Mobile Money present but inactive/unconfigured

| Actor | Purpose | Required state |
| --- | --- | --- |
| Operations admin | Global operations smoke | Active OperationsStaffProfile or superuser |
| Customer | Search, checkout, review, preferences | Active user |
| Merchant owner | Merchant dashboard and order workflow | Verified merchant company |
| Merchant staff | Branch and role-scoped access | Verified and active staff member |
| Delivery partner | Delivery lifecycle | Verified and active partner |

## Service Health

| Check | Expected result | Pass |
| --- | --- | --- |
| Open `/` | Frontend loads |  |
| Open `/api/v1/health/` | Returns healthy response |  |
| Open `/api/v1/health/?detail=1` | Reports backend dependencies without leaking secrets |  |
| Docker service status | Backend, frontend, db, redis, workers are running |  |
| Backend logs | No crash loops or migration errors |  |
| Celery logs | Worker and beat start cleanly |  |
| Dispatch worker logs | Worker starts cleanly |  |

## Guest Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Home page loads | T-Food landing or marketplace entry loads |  |
| Search page loads | Text search is visible |  |
| Visual search control appears | Customer can choose an image |  |
| Visual search with safe test image | Labels and safe fallback/results display |  |
| Restaurant/branch page loads | Menu items and public data display |  |
| Public reviews | Only approved review photos are public |  |
| Language switch | Common UI labels update without refresh |  |
| Theme/accent switch | UI updates immediately and persists after reload |  |

## Customer Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Register customer | Account created successfully |  |
| Login customer | Auth context loads |  |
| Browse restaurants | Results show safely with or without location |  |
| Add item to cart | Cart updates correctly |  |
| Checkout with COD | Order is created without payment-provider dependency |  |
| View order | Order details display |  |
| Track order | Tracking page loads and status is visible |  |
| Customer notifications | Order/payment/delivery notifications appear |  |
| Submit review | Review is created for delivered order |  |
| Upload review photo | Photo is pending moderation |  |
| Delete pending review photo | Customer can delete own pending photo |  |
| Preferences page | Language, theme, accent, regional settings load |  |
| Logout | Session ends cleanly |  |

## Codespaces End-to-End Demo Flow

Use the seeded demo accounts for this short shared-link test.

| Step | Actor | Check | Expected result | Pass |
| --- | --- | --- | --- | --- |
| 1 | Customer | Login with `customer.guinea.demo@t-food.test` | Customer account opens |  |
| 2 | Customer | Search/browse demo branches | Conakry Grill, Fresh Market Conakry, and Sante Plus Pharmacy are discoverable |  |
| 3 | Customer | Place COD order | Order is created without online payment provider |  |
| 4 | Merchant owner | Login with `merchant.guinea.demo@t-food.test` | Merchant dashboard opens |  |
| 5 | Merchant owner | Accept/prepare/ready order | Order workflow updates safely |  |
| 6 | Delivery partner | Login with `rider.guinea.demo@t-food.test` | Partner dashboard opens |  |
| 7 | Delivery partner | Pickup/on the way/delivered | Delivery lifecycle completes |  |
| 8 | Customer | Submit review and upload photo | Review photo is pending moderation |  |
| 9 | Operations admin | Login with `ops.guinea.demo@t-food.test` | Operations dashboard opens |  |
| 10 | Operations admin | Moderate review photo | Approve/reject/hide works with scoped access |  |
| 11 | All actors | Check notifications | In-app/realtime notifications appear where expected |  |

## Merchant Owner Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Login merchant owner | Owner dashboard loads |  |
| No-branch merchant state | Safe empty state, no crash |  |
| Manage branches | Existing branch list and branch actions load |  |
| Manage menu | Menu items/categories load |  |
| View orders | Merchant order list loads |  |
| Update order status | Allowed status transition succeeds |  |
| Manage riders | Rider tools load where enabled |  |
| Manage staff | Staff tab loads |  |
| Invite staff | Invite token/status returned |  |
| Assign branch | Merchant-owned branch assignment works |  |
| View payouts | Payout view loads without changing ledger values |  |
| View analytics | Analytics loads with safe zeros if no data |  |
| View notifications | Merchant notifications load |  |
| Verification panel | Status and documents display without exposing private URLs |  |

## Merchant Staff Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Verified active staff login | Staff context appears |  |
| Branch-scoped staff | Sees assigned branch only |  |
| Company-wide staff | Sees permitted company scope |  |
| Kitchen role | Cannot access finance tools |  |
| Finance role | Cannot manage riders |  |
| Viewer role | Read-only behavior enforced |  |
| Unverified staff | No operational permissions |  |
| Inactive/removed staff | No operational permissions |  |

## Delivery Partner Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Login partner | Partner dashboard loads |  |
| Available deliveries | Eligible deliveries display |  |
| Claim delivery | Partner can claim only allowed delivery |  |
| Pickup | Pickup status update succeeds |  |
| On the way | Delivery status update succeeds |  |
| Delivered | Delivery completes |  |
| Earnings/payout view | Loads without changing ledger history |  |
| Partner notifications | Assignment and delivery notifications appear |  |
| Cross-partner access | Another partner delivery is denied |  |

## Operations Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Login global admin | Operations dashboard loads |  |
| Scope label/filter | Shows expected global or assigned scope |  |
| Marketplace control | Markets/cities/areas load or show setup guidance |  |
| Branch management | Branches are scoped and manageable |  |
| Merchant verification | Queue and actions load |  |
| Staff verification | Queue and actions load |  |
| Rider verification | Queue and actions load |  |
| Review photo moderation | Pending queue, approve/reject/hide controls load |  |
| Ledger view | Read-only ledger view loads |  |
| Provider config view | No credentials are exposed |  |
| Support tickets | Queue loads |  |
| Notifications | Scoped operations notification center loads |  |
| Intelligence | Scoped insights load |  |
| Operations users | Management view loads for authorized admin |  |

## Country, City, and Area Admin Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Country admin | Sees only assigned country/market |  |
| City admin | Sees only assigned city data |  |
| Area admin | Sees only assigned area data |  |
| Finance isolation | Cannot see another country/city/area finance data |  |
| Provider config isolation | Cannot see out-of-scope provider configs |  |
| Verification queue scope | Out-of-scope records are hidden |  |
| Review photo moderation scope | Out-of-scope photos are hidden |  |

## Payments and Ledger Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| COD order | Completes without provider dependency |  |
| Razorpay path if configured | Compatible path still loads |  |
| Refund path | Refund workflow works where configured |  |
| Merchant payout audit | Payout history and ledger references remain consistent |  |
| Partner payout audit | Payout history and ledger references remain consistent |  |
| Ledger balance check | Ledger remains balanced and immutable |  |
| Currency preference | Display preference does not alter transaction currency |  |

## Realtime Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Customer order updates | Customer sees order status updates |  |
| Merchant order notifications | Merchant receives order notifications |  |
| Partner delivery notifications | Partner receives delivery notifications |  |
| Operations notifications | Scoped operations notifications arrive |  |
| WebSocket reconnect | Client reconnects after temporary disconnect |  |

## Security Smoke

| Check | Expected result | Pass |
| --- | --- | --- |
| Private raw media URL | Verification documents are not directly accessible |  |
| Pending review photo raw URL | Not publicly accessible |  |
| Verification document download | Requires authorized owner or scoped operations actor |  |
| Cross-customer object access | Denied |  |
| Cross-merchant object access | Denied |  |
| Cross-country operations access | Denied |  |
| Legacy staff disabled mode | Legacy staff without profile has no business access |  |
| Provider secrets | Not returned by APIs or frontend |  |

## Minimum Configuration Mode Smoke

Run this against a clean or reduced environment when practical.

| Check | Expected result | Pass |
| --- | --- | --- |
| No market configured | App loads with setup guidance or safe empty states |  |
| No city configured | App loads with setup guidance or safe empty states |  |
| No area configured | App loads with setup guidance or safe empty states |  |
| Merchant without branch | Merchant can exist and manage onboarding/profile |  |
| No external payment provider | COD and non-provider flows remain safe |  |
| No external notification provider | In-app/realtime notifications still work |  |

## Go / No-Go

| Area | Go criteria | Status |
| --- | --- | --- |
| Health | All required services healthy |  |
| Customer ordering | COD order flow passes |  |
| Merchant operations | Order workflow and dashboard pass |  |
| Delivery partner | Delivery lifecycle passes |  |
| Operations | Verification, moderation, ledger, notifications pass |  |
| Security | No private media or object-permission leaks found |  |
| Minimum Configuration Mode | Optional hierarchy gaps do not crash platform |  |
| Monitoring | Health endpoint and logs are usable |  |
| Backup readiness | Backup and restore runbooks are available |  |

## Sign-Off

| Role | Name | Date | Decision | Notes |
| --- | --- | --- | --- | --- |
| Engineering |  |  |  |  |
| Operations |  |  |  |  |
| Product |  |  |  |  |
| Pilot owner |  |  |  |  |
