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
