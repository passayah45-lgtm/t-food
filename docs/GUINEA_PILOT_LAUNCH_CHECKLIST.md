# T-Food Guinea Pilot Launch Checklist

This is the final readiness checklist for the first controlled T-Food pilot in Guinea. It is a launch gate, not a feature plan. Do not proceed to public pilot traffic until every launch-blocking item is complete or explicitly accepted by the pilot owner.

## Launch Scope

| Item | Decision / value | Status |
| --- | --- | --- |
| Pilot country | Guinea |  |
| Pilot city | Conakry |  |
| Pilot area |  |  |
| Pilot start date |  |  |
| Pilot owner |  |  |
| Engineering owner |  |  |
| Operations owner |  |  |
| Support contact |  |  |
| Launch decision | Go / No-Go |  |

## 1. Technical Readiness

| Check | Required result | Status | Notes |
| --- | --- | --- | --- |
| Backend health | `/api/v1/health/` returns OK |  |  |
| Detailed health | `/api/v1/health/?detail=1` reports DB, Redis, media, channel layer, and worker heartbeats |  |  |
| Frontend health | `/` loads through the production domain |  |  |
| Database health | PostgreSQL/PostGIS healthy and reachable only from private network |  |  |
| Redis health | Redis healthy and not publicly exposed |  |  |
| Celery worker | Running and processing queue |  |  |
| Celery beat | Running scheduled tasks |  |  |
| Dispatch worker | Running and heartbeat visible |  |  |
| Docker status | Required containers up and healthy |  |  |
| Production env validation | Production variables present; unsafe defaults rejected |  |  |
| Migrations | `python manage.py migrate` completed successfully |  |  |
| Static files | Static assets served correctly |  |  |
| Public media | Public restaurant/menu/approved review media served from public media only |  |  |
| Private media | Private media volume is not mounted into public Nginx/media path |  |  |
| Backup created | Database, public media, and private media backups created before launch |  |  |
| Restore drill | Restore process successfully tested |  |  |
| Monitoring | Health endpoints, logs, and worker heartbeats checked |  |  |
| Logs | No startup crashes, permission errors, or secret leakage |  |  |

## 2. Security Readiness

| Check | Required result | Status | Notes |
| --- | --- | --- | --- |
| Private media protected | Raw private media URLs do not expose files |  |  |
| Verification documents private | Merchant, staff, and partner documents require authorized access |  |  |
| Pending review photos private | Pending photos are not public |  |  |
| Rejected/hidden review photos private | Rejected and hidden photos are not public |  |  |
| Approved review photos public | Approved photos display through safe public path |  |  |
| Legacy staff disabled | Production runs with `ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False` |  |  |
| Operations users scoped | Global, country, city, and area scopes enforced |  |  |
| Cross-scope tests | Customer, merchant, branch, country, city, area isolation verified |  |  |
| Upload validation | Images/documents validate type, size, content, filename, and EXIF stripping |  |  |
| Rate limits | Login, register, uploads, visual search, support, and sensitive mutations reviewed |  |  |
| Secrets not exposed | Provider credentials, JWTs, passwords, and private paths absent from API/frontend/logs |  |  |

## 3. Business Readiness

| Check | Required result | Status | Notes |
| --- | --- | --- | --- |
| Pilot city selected | Conakry confirmed |  |  |
| Pilot area selected | Initial service area confirmed or Minimum Configuration Mode accepted |  |  |
| Test merchants selected | Merchant list approved for pilot |  |  |
| Merchant onboarding | Pilot merchants verified or explicitly staged for onboarding |  |  |
| Menu/catalog readiness | Pilot menus/items loaded and reviewed |  |  |
| Delivery partners selected | Initial rider/partner list approved |  |  |
| Operations admins selected | Operations users created with correct scopes |  |  |
| Support contact ready | Customer/merchant support escalation path active |  |  |
| Refund process defined | Manual or system-assisted refund path documented |  |  |
| Manual payout process | Merchant/partner payout process documented if automated payout is not live |  |  |
| Commission rules | Pilot commission rules documented and approved |  |  |

## 4. Payment Readiness

| Check | Required result | Status | Notes |
| --- | --- | --- | --- |
| COD enabled | Cash on delivery works for Guinea pilot |  |  |
| Razorpay scoped | Razorpay used only for India testing if configured |  |  |
| Guinea providers inactive | Guinea external providers inactive until real credentials are available |  |  |
| Provider dashboard checked | No credentials exposed; inactive providers clearly marked |  |  |
| Ledger tests passed | Ledger regression tests pass |  |  |
| Refund audit works | Refund state and audit trail verified |  |  |
| Merchant payout audit works | Merchant payout records and ledger references verified |  |  |
| Partner payout audit works | Partner payout records and ledger references verified |  |  |
| Currency display checked | Preferences do not alter transaction currency or ledger values |  |  |

## 5. Notification Readiness

| Check | Required result | Status | Notes |
| --- | --- | --- | --- |
| In-app notifications | Enabled and visible |  |  |
| Realtime notifications | `notification.created` and existing realtime events work |  |  |
| Email inactive | Clearly future/inactive; no provider calls |  |  |
| SMS inactive | Clearly future/inactive; no provider calls |  |  |
| WhatsApp inactive | Clearly future/inactive; no provider calls |  |  |
| Notification preferences | User preferences can be saved |  |  |
| Operations notification center | Scoped operations inbox works |  |  |
| Failed delivery safety | Notification failures do not block business workflows |  |  |

## 6. Localization and Personalization Readiness

| Check | Required result | Status | Notes |
| --- | --- | --- | --- |
| English works | Main flows usable in English |  |  |
| French works | Main flows usable in French |  |  |
| Translation gaps documented | Any untranslated non-critical UI is listed |  |  |
| Theme works | Light, dark, and system modes work |  |  |
| Accent color works | Accent color changes buttons, highlights, links, and active tabs |  |  |
| Currency display works | Display preference only; no financial recalculation |  |  |
| Preferences page works | Guest and logged-in preferences persist |  |  |
| Accessibility toggles | Large text, high contrast, reduced motion, enhanced focus checked |  |  |

## 7. Operations Readiness

| Check | Required result | Status | Notes |
| --- | --- | --- | --- |
| Operations dashboard | Loads for authorized operations users |  |  |
| Branch management | Branches optional; no-branch merchants handled safely |  |  |
| Merchant verification | Merchant verification queue and decisions work |  |  |
| Staff verification | Merchant staff verification queue and decisions work |  |  |
| Delivery partner verification | Partner verification queue and decisions work |  |  |
| Review photo moderation | Pending queue and approve/reject/hide actions work |  |  |
| Support tickets | Support queue and status updates work |  |  |
| Scoped admin users | Global, country, city, and area users behave as expected |  |  |
| Intelligence | Scoped intelligence loads without leaking data |  |  |
| Provider configs | Provider config view does not expose credentials |  |  |

## 8. Manual QA Sign-Off

| Flow | Owner | Result | Date | Notes |
| --- | --- | --- | --- | --- |
| Customer flow |  | Pass / Fail |  |  |
| Merchant flow |  | Pass / Fail |  |  |
| Merchant staff flow |  | Pass / Fail |  |  |
| Partner flow |  | Pass / Fail |  |  |
| Operations flow |  | Pass / Fail |  |  |
| Payment flow |  | Pass / Fail |  |  |
| Refund flow |  | Pass / Fail |  |  |
| Notification flow |  | Pass / Fail |  |  |
| Security flow |  | Pass / Fail |  |  |
| Backup/restore flow |  | Pass / Fail |  |  |
| Production smoke flow |  | Pass / Fail |  |  |

## 9. Go / No-Go Criteria

### Go only if

- Backend tests pass.
- Frontend build passes.
- Docker health is OK.
- `/api/v1/health/` is OK.
- `/api/v1/health/?detail=1` is OK.
- Private media is protected.
- Backup is created.
- Restore drill is done.
- Manual QA passed.
- COD test order passed.
- Dispatch test passed.
- Operations support path passed.
- No ledger imbalance is detected.
- No operations scope leakage is detected.

### No-Go if

- Payment state is inconsistent.
- Ledger imbalance is detected.
- Private media is exposed.
- Operations scope leakage is found.
- Backup is not available.
- Restore drill is not complete.
- Health checks are failing.
- Dispatch worker is down.
- Redis is down.
- Database is unhealthy.
- Checkout, order, dispatch, or delivery smoke tests fail.

## 10. Post-Launch Monitoring

Monitor continuously during the first 24 hours.

| Area | Watch for | Owner | Status |
| --- | --- | --- | --- |
| Orders | Failed creation, stuck statuses, cancellation spikes |  |  |
| Payments | Failed COD confirmation, refund errors, provider errors |  |  |
| Dispatch | Unclaimed deliveries, claim conflicts, worker heartbeat gaps |  |  |
| Support tickets | Customer or merchant incident spikes |  |  |
| Error logs | 4xx spikes, 5xx errors, tracebacks, permission errors |  |  |
| Worker heartbeats | Celery worker, beat, and dispatch freshness |  |  |
| Redis/Postgres | Health, latency, restarts, disk pressure |  |  |
| Notifications | Failed delivery attempts, realtime failures |  |  |
| Media | Upload failures, private media access denials |  |  |
| Operations dashboard | Queue health, verification backlog, moderation backlog |  |  |

## Final Launch Decision

| Decision | Name | Date | Notes |
| --- | --- | --- | --- |
| Engineering Go / No-Go |  |  |  |
| Operations Go / No-Go |  |  |  |
| Business Go / No-Go |  |  |  |
| Pilot owner final decision |  |  |  |
