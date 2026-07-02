# 10. Investor-Grade Startup Roadmap

## Stage Definitions

Technology follows marketplace proof. Funding stage names are not substitutes for measurable operating gates.

## MVP / Pre-Seed: Prove One Dense Operating Zone

Time: 0-6 months

Product:

- reliable food order, payment/COD, merchant prep and delivery lifecycle
- shared partner offer/claim flow with expiry and redispatch
- support/refund operations and merchant/partner statements
- market/currency, event, Celery, observability and PostGIS foundations

Business gates:

- 20-50 active merchants in one dense zone
- repeat customers and consistent successful deliveries
- measurable order-level contribution margin path
- merchant and partner retention evidence
- cancellation, refund, late and support rates under active control

Team: 10-14, as specified in the main blueprint. Keep founders close to operations and merchant onboarding.

Infrastructure budget: modeled $1K-$5K/month plus maps/messages/payments. Optimize learning and reliability, not premature multi-region scale.

## Seed: Repeatable City Playbook

Time: 6-18 months

Product:

- multi-branch merchant OS, catalog v2, inventory and grocery pilot
- automated payouts/refunds and shadow-to-authoritative ledger
- real-time tracking/push, ETA baseline and dispatch recovery
- referrals/membership experiments and merchant campaign tools
- privacy, RBAC, audit and CI/CD maturity

Business gates:

- repeatable merchant onboarding and zone launch time
- improving 30/90-day customer cohorts
- positive contribution margin in mature zones before central overhead
- partner utilization/earnings that retain supply
- low merchant concentration and strong active-merchant retention

Team: 25-45 in squads: Consumer, Merchant/Catalog, Fulfillment, Payments/Ledger, Platform/Data plus operations, finance/risk and design.

Infrastructure budget: modeled $10K-$50K/month depending on order/location volume and provider usage.

## Series A: Multi-City, Multi-Vertical Engine

Time: 18-30 months

Product:

- food plus grocery/courier using shared commerce/fulfillment primitives
- search/recommendation, demand heatmaps and production ETA model
- constrained batching pilot
- robust financial reconciliation and settlement automation
- first additional market cell where operational economics justify it
- merchant subscriptions and fulfillment-as-a-service pilots

Business gates:

- several cities reproduce mature-zone economics
- cross-vertical frequency increases retention without destroying margin
- strong monthly order growth with controlled acquisition payback
- merchant OS adoption creates non-order engagement
- audited financial data and tested DR/security program

Team: 60-100 with dedicated platform/SRE, data/ML, trust/safety, search, country operations and finance engineering.

Infrastructure budget: modeled $50K-$250K/month; require FinOps allocation per market and order.

## Series B: Regional Network Effects

Time: 30-48 months

Product:

- market/metro cells, selective service extraction and mature data platform
- stacked delivery optimization, advanced fraud and partner positioning
- merchant AI assistant, ads platform and enterprise logistics APIs
- multiple payment/mobile-money/tax integrations
- pharmacy only in legally ready markets

Business gates:

- durable city and cross-vertical network effects
- profitable mature-market contribution with credible company-level path
- diversified revenue beyond commissions/delivery fees
- defensible merchant retention and proprietary operational data loops
- governance capable of multi-country regulatory and incident response

Team: 120-250 based on countries, with platform groups and autonomous market pods under shared architecture/security standards.

Infrastructure budget: modeled $250K-$1.2M+/month at target traffic; provider fees can materially exceed base cloud.

## Hiring Roadmap

| When | Critical hires | Why |
|---|---|---|
| Now | senior backend, frontend/mobile, product, QA automation, DevOps, operations | stabilize core and learn marketplace |
| Before automated money | finance engineer/controller and risk/compliance advisor | ledger/payout correctness |
| Before PostGIS/real time scale | staff fulfillment engineer and SRE | dispatch/location reliability |
| Before ML | analytics/data engineer and experimentation lead | trustworthy data/labels |
| Before second country | country GM/product ops, legal/privacy/payments specialists | local execution and compliance |
| Before service extraction | platform engineering lead and service-owning teams | avoid unsupported microservices |

## Revenue Model

1. Marketplace commission differentiated by vertical/fulfillment.
2. Transparent delivery/service fees.
3. Merchant SaaS subscriptions for analytics, CRM, inventory, automation and lower commission options.
4. Customer membership benefits.
5. Sponsored listings and advertising with clear labels/attribution.
6. Fulfillment-as-a-service for merchant-owned demand.
7. Enterprise/white-label ordering and logistics APIs.
8. Payment/settlement services where licensed/partnered.
9. Privacy-safe aggregate market insights.

Avoid revenue that weakens marketplace trust: opaque ranking pay-to-win, hidden fees, exploitative partner penalties or unconsented data resale.

## KPI Tree

### Marketplace

- gross merchandise value and completed orders
- active customers/merchants/partners
- order frequency and cross-vertical frequency
- merchant availability/menu/inventory accuracy
- supply hours, utilization and assignment time

### Customer

- browse-to-cart, cart-to-paid, completion rate
- D7/D30/D90 cohort retention
- late/cancel/refund/support contacts per order
- NPS/rating and price/ETA accuracy

### Merchant

- onboarding-to-live time
- active/retained merchants and sales concentration
- acceptance, prep-time accuracy, cancellation and stock accuracy
- merchant contribution margin and SaaS adoption

### Partner

- online-to-paid time utilization
- earnings per active hour and variance
- offer acceptance, pickup wait and completion
- partner retention, safety and fairness indicators

### Financial

- take rate and net revenue
- variable contribution per order
- payment/refund/fraud loss
- acquisition payback and LTV/CAC by cohort
- settlement/reconciliation exceptions

### Reliability

- checkout/payment/dispatch SLOs
- incident rate/MTTR
- event/queue age
- cost per completed order

## Unit Economics

Per-order contribution:

```text
merchant commission
+ customer delivery/service fees
+ ad/subscription allocation
- partner delivery cost/incentive
- payment processing
- promotion subsidy
- refund/fraud/support variable cost
- maps/messages/cloud variable cost
= contribution margin
```

Report by market, zone, vertical, distance band, customer cohort and merchant cohort. GMV growth without improved mature-zone contribution is not sufficient.

## Expansion Strategy

1. Select one dense zone with demand, merchant supply, workable payments and manageable regulation.
2. Establish service quality and mature-zone economics.
3. Expand adjacent zones sharing supply and merchant operations.
4. Add grocery/courier to fill supply dayparts only after food operations are reliable.
5. Launch a second city using a documented playbook and compare cohort/economics.
6. Enter a new country only when market configuration, payment, tax, support, privacy, payout and DR gates pass.

India strategy emphasizes metro density, UPI/COD, GST, multilingual discovery and operational optimization. Guinea strategy should emphasize French-first localization, mobile money, landmark/phone-centric addresses, intermittent connectivity and concentrated city operations.

## Investor Data Room

- reconciled monthly financial statements and ledger/control narrative
- cohort retention and unit economics by market
- merchant/customer/partner concentration and retention
- architecture/data-flow/security diagrams
- incident/SLO and DR restore evidence
- privacy/compliance and processor inventory
- IP assignments, dependency licenses, SBOM and security testing
- roadmap tied to measurable gates and hiring/capital plan

## Fundraising Narrative Tests

The strongest story is not “we can copy every large delivery app.” It is:

- T-Food has a repeatable local-commerce market cell.
- Shared merchant and fulfillment primitives lower the cost of adding verticals.
- Merchant OS engagement and cross-vertical density improve retention and economics.
- The operating/event data improves dispatch, ETA, inventory and fraud decisions.
- Financial and reliability controls support regulated global growth.

