# T-Food Version 1.0 Manual QA Checklist

Purpose: verify T-Food end to end before pilot launch without adding features
or changing business behavior.

Use this checklist after CI passes, after deployment, and before inviting pilot
users. Record tester, date, environment, browser/device, account used, result,
evidence, and bug link for each item.

Result values:

- `PASS`
- `FAIL`
- `BLOCKED`
- `NOT APPLICABLE`

## Test Data Guidance

Use non-production test accounts unless this is the final production smoke test.

Recommended roles:

- Customer: `qa_customer`
- Merchant owner: `qa_merchant_owner`
- Merchant staff: `qa_kitchen_staff`, `qa_finance_staff`, `qa_viewer_staff`
- Delivery partner: `qa_partner`
- Operations admin: `qa_global_ops`
- Scoped admins: `qa_country_admin`, `qa_city_admin`, `qa_area_admin`

Minimum Configuration Mode must also be tested with:

- no market
- no city
- no area
- merchant without branch
- no external payment provider
- no external notification provider

Expected behavior in Minimum Configuration Mode: safe empty states, setup
guidance, no server errors, and no forced hierarchy creation.

## 1. Guest Flow

| ID | Check | Expected Result | Result |
|---|---|---|---|
| G-01 | Home page loads | Landing/customer home renders without login | |
| G-02 | Search page loads | Text search UI is visible | |
| G-03 | Text search works | Results or safe empty state appear | |
| G-04 | Visual search control is visible | Customer can choose image search from search UI | |
| G-05 | Visual search works | Valid image returns labels/results or safe fallback | |
| G-06 | Invalid visual search image | Clear error, no crash | |
| G-07 | Restaurant page loads | Branch/storefront details and menu render | |
| G-08 | Menu items show | Item names, prices, availability display correctly | |
| G-09 | Public reviews show approved photos only | Pending/rejected/hidden photos are not public | |
| G-10 | Language switch works | UI labels switch between English/French without reload | |
| G-11 | Theme switch works | Light/dark/system applies without reload | |
| G-12 | Accent switch works | Buttons, active tabs, and highlights change clearly | |

## 2. Customer Flow

| ID | Check | Expected Result | Result |
|---|---|---|---|
| C-01 | Register | Customer account is created | |
| C-02 | Login | Customer receives authenticated session | |
| C-03 | Browse restaurants | Restaurant list loads with public data only | |
| C-04 | Add item to cart | Cart updates with item/options/price | |
| C-05 | Checkout with COD | Order is created without online provider dependency | |
| C-06 | View order | Customer sees own order only | |
| C-07 | Track order | Tracking reflects status changes | |
| C-08 | Receive notifications | In-app/realtime notifications appear | |
| C-09 | Submit review | Completed-order review can be submitted | |
| C-10 | Upload review photo | Photo uploads as pending moderation | |
| C-11 | Delete pending review photo | Customer can delete own pending photo | |
| C-12 | Approved review photo visibility | Approved photo appears publicly | |
| C-13 | View preferences | Preferences page loads | |
| C-14 | Update preferences | Language/theme/currency/accessibility save | |
| C-15 | Logout | Session ends; protected pages require login | |

## 3. Merchant Owner Flow

| ID | Check | Expected Result | Result |
|---|---|---|---|
| M-01 | Login | Merchant owner reaches dashboard | |
| M-02 | Dashboard overview | Company/branch-safe summary loads | |
| M-03 | Merchant without branch | Empty state appears; no branch is forced | |
| M-04 | Manage branches | Create/edit/open/close branch works | |
| M-05 | Manage menu | Add/edit item without breaking public menu | |
| M-06 | View orders | Merchant sees own company/branch orders only | |
| M-07 | Update order status | Valid status changes work | |
| M-08 | Manage riders | Invite/assign/filter riders by branch | |
| M-09 | Manage staff | Staff tab loads | |
| M-10 | Invite staff | Invite token is generated; no verification bypass | |
| M-11 | Assign staff branch | Only merchant-owned branches are assignable | |
| M-12 | Activate staff | Only verified staff can be activated | |
| M-13 | View payouts | Payout data loads without provider secrets | |
| M-14 | View analytics | Company/branch analytics load, zero-safe if no branch | |
| M-15 | View notifications | Merchant notifications are scoped correctly | |
| M-16 | Verification panel | Documents/status show without approval powers | |

## 4. Merchant Staff Flow

| ID | Check | Expected Result | Result |
|---|---|---|---|
| S-01 | Verified active staff login | Staff context and permissions load | |
| S-02 | Branch-scoped access | Staff sees assigned branch only | |
| S-03 | Company-wide staff | Staff sees company scope allowed by role | |
| S-04 | Kitchen role | Can access preparation/order tasks only | |
| S-05 | Kitchen finance denial | Finance/payout/ledger access denied | |
| S-06 | Finance role | Can view finance summaries/payouts | |
| S-07 | Finance rider denial | Rider management denied | |
| S-08 | Viewer role | Read-only; action buttons blocked or denied | |
| S-09 | Unverified staff | No operational access | |
| S-10 | Inactive/removed staff | No operational access | |

## 5. Delivery Partner Flow

| ID | Check | Expected Result | Result |
|---|---|---|---|
| D-01 | Login | Partner dashboard loads | |
| D-02 | View available deliveries | Eligible deliveries appear | |
| D-03 | Claim delivery | Partner can claim one eligible delivery | |
| D-04 | Cross-partner denial | Partner cannot access another partner delivery | |
| D-05 | Pickup | Status updates to picked up | |
| D-06 | On the way | Status updates to on the way | |
| D-07 | Delivered | Handoff-code delivery completes | |
| D-08 | Earnings/payout | Partner sees own earnings/payout data | |
| D-09 | Notifications | Assignment/status notifications arrive | |

## 6. Operations Flow

| ID | Check | Expected Result | Result |
|---|---|---|---|
| O-01 | Global admin login | Operations dashboard loads | |
| O-02 | Scoped filters | Viewing label and filters reflect actor scope | |
| O-03 | Manage branches | Authorized branch actions work | |
| O-04 | Merchant verification | Review queue and decisions work | |
| O-05 | Staff verification | Approve/reject/suspend/more-info works | |
| O-06 | Rider verification | Review flow remains compatible | |
| O-07 | Review photo moderation | Approve/reject/hide works; reason required | |
| O-08 | Ledger view | Ledger visible to authorized finance/admin only | |
| O-09 | Provider configs | Credentials are never exposed | |
| O-10 | Support tickets | List/update support tickets by permission | |
| O-11 | Notifications | Operations notification center is scoped | |
| O-12 | Intelligence | Insights respect selected scope | |
| O-13 | Operations users | Global admin can manage operations profiles | |

## 7. Country, City, and Area Admin Flow

| ID | Check | Expected Result | Result |
|---|---|---|---|
| A-01 | Country admin scope | Sees assigned country/market only | |
| A-02 | City admin scope | Sees assigned city only | |
| A-03 | Area admin scope | Sees assigned area only | |
| A-04 | Finance isolation | Cannot see another country/city/area finance | |
| A-05 | Provider config isolation | Cannot see out-of-scope provider configs | |
| A-06 | Verification isolation | Out-of-scope queues hidden | |
| A-07 | Review photo moderation scope | Out-of-scope photos hidden | |
| A-08 | Empty scope | Safe empty state if no assigned data exists | |

## 8. Payments and Ledger

| ID | Check | Expected Result | Result |
|---|---|---|---|
| P-01 | COD order | Checkout and order confirmation work | |
| P-02 | Razorpay compatibility | Path remains available when configured | |
| P-03 | Failed payment | Does not confirm order | |
| P-04 | Refund path | Refund workflow works where authorized | |
| P-05 | Merchant payout audit | Payout creates audit/ledger trail | |
| P-06 | Partner payout audit | Partner payout creates audit/ledger trail | |
| P-07 | Ledger balance | Ledger entries remain balanced/immutable | |
| P-08 | Currency preference | Display preference does not alter calculations | |

## 9. Realtime

| ID | Check | Expected Result | Result |
|---|---|---|---|
| R-01 | Customer order updates | Customer sees order status changes | |
| R-02 | Merchant notifications | Merchant receives new order/status notifications | |
| R-03 | Partner notifications | Partner receives delivery notifications | |
| R-04 | Operations notifications | Operations receives only scoped notifications | |
| R-05 | WebSocket reconnect | UI recovers after temporary disconnect | |
| R-06 | Existing events | Existing order/dispatch realtime types still work | |

## 10. Security

| ID | Check | Expected Result | Result |
|---|---|---|---|
| X-01 | Private media raw path | Raw private media URL is not accessible | |
| X-02 | Verification documents | Auth and object permissions required | |
| X-03 | Pending review photos | Authenticated preview only; not public | |
| X-04 | Cross-customer access | Denied | |
| X-05 | Cross-merchant access | Denied | |
| X-06 | Cross-branch staff access | Denied | |
| X-07 | Cross-country operations access | Denied | |
| X-08 | Provider secrets | Never returned to frontend/API clients | |
| X-09 | Legacy staff production mode | `ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False` blocks legacy business access | |
| X-10 | Rate limits | Login/register/upload throttles respond safely | |

## 11. Minimum Configuration Mode

| ID | Check | Expected Result | Result |
|---|---|---|---|
| MC-01 | No market | App loads; scoped screens show setup guidance | |
| MC-02 | No city | App loads; city filters show empty state | |
| MC-03 | No area | App loads; area filters show empty state | |
| MC-04 | Merchant without branch | Profile/staff/provider setup works | |
| MC-05 | No external payment provider | COD and safe provider warnings work | |
| MC-06 | No external notification provider | In-app/realtime work; external channels skipped | |
| MC-07 | No staff | Staff screens show empty state | |
| MC-08 | No riders | Dispatch/rider screens show empty state | |

## 12. Production Smoke

| ID | Check | Expected Result | Result |
|---|---|---|---|
| PS-01 | `/` | Returns `200` | |
| PS-02 | `/api/v1/health/` | Returns `status: ok` | |
| PS-03 | `/api/v1/health/?detail=1` | Reports DB/cache/media/channel/workers | |
| PS-04 | Frontend container | Healthy/running | |
| PS-05 | Backend container | Healthy/running | |
| PS-06 | DB container | Healthy/running | |
| PS-07 | Redis container | Healthy/running | |
| PS-08 | Celery worker | Running and heartbeat visible | |
| PS-09 | Celery Beat | Running and heartbeat visible | |
| PS-10 | Dispatch worker | Running and heartbeat visible | |

## Sign-Off

Do not approve pilot launch until all Critical and High findings are resolved.

| Role | Name | Date | Approved |
|---|---|---|---|
| Engineering | | | |
| Operations | | | |
| Support | | | |
| Business owner | | | |
