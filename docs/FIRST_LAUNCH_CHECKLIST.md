# T-Food First Launch Checklist

Target: launch carefully with real restaurants, real delivery partners, and the first 100 users without adding new product features.

## 1. Launch Readiness

Complete before inviting public users:

- VPS deployment completed.
- Domain points to the VPS.
- HTTPS works.
- `DEBUG=False`.
- Production `.env` uses real generated secrets.
- PostgreSQL backup created and copied off the VPS.
- Media backup created and copied off the VPS.
- Restore drill completed.
- `backend` is healthy.
- `frontend` is reachable.
- `dispatch_worker` is running.
- `celery_worker` is consuming tasks.
- `celery_beat` is scheduling tasks.
- Launch smoke test passed.
- Admin login works.
- Support contact channel is ready.

## 2. First Restaurant Onboarding

Collect from each restaurant:

- Business name.
- Owner name.
- Phone number.
- Email address.
- Full pickup address.
- Pickup latitude and longitude if available.
- Food license or local compliance details if required.
- Opening hours.
- Prep time estimate.
- Delivery radius.
- Minimum order amount.
- Delivery fee.
- Commission agreement.
- Payment/payout method.
- Menu photos.
- Restaurant cover image.

Admin setup:

- Create merchant user.
- Create merchant profile.
- Mark merchant as verified only after approval.
- Create restaurant.
- Set restaurant active/open state.
- Add pickup address and city.
- Add pickup coordinates if available.
- Set operating hours.
- Set delivery fee and delivery radius.
- Set estimated prep minutes.
- Add food items.
- Add item options/modifiers where needed.
- Mark unavailable items as unavailable.

Restaurant acceptance test:

- Merchant can log in.
- Merchant can see dashboard.
- Merchant can see restaurant.
- Merchant can update restaurant details.
- Merchant can add/edit menu item.
- Merchant can receive a test order.
- Merchant can move order to `PREPARING`.
- Merchant can move order to `READY_FOR_PICKUP`.

## 3. Menu Quality Checklist

For each menu item:

- Name is clear.
- Description is short and useful.
- Price is correct.
- Category is correct.
- Availability is correct.
- Image is clean and not misleading.
- Required options are configured correctly.
- Optional add-ons have correct prices.
- Spicy/veg/non-veg labels are clear if used in the local market.

Before launch, place one test order from every restaurant.

## 4. Delivery Partner Onboarding

Collect from each partner:

- Full name.
- Phone number.
- Email or username.
- Vehicle type.
- Vehicle number if required.
- Service area.
- ID verification details if required.
- Bank or payout details.

Admin setup:

- Create delivery partner user.
- Create partner profile.
- Mark partner as verified only after approval.
- Confirm partner availability can be toggled.
- Confirm partner can update current location.
- Confirm partner sees available deliveries.

Partner readiness test:

- Partner can log in.
- Partner can see dashboard.
- Partner can see available order after merchant marks ready.
- Partner can claim order.
- Partner can mark `PICKED_UP`.
- Partner can mark `ON_THE_WAY`.
- Partner can mark `DELIVERED` with handoff code.
- Partner becomes available again after delivery.

## 5. Customer Launch Test

Use a real test customer account:

- Register customer.
- Log in.
- Browse restaurants.
- Open restaurant.
- Add item with options.
- Checkout with COD.
- Confirm order appears in customer orders.
- Confirm customer tracking updates.
- Confirm handoff code appears before delivery.
- Confirm order shows delivered after partner completes delivery.

## 6. Payment Launch Policy

Start simple:

- Use COD first if online payments are not fully verified.
- Keep online payment keys empty until Razorpay or payment provider is tested.
- Do not enable public online payments until webhook verification passes.
- Test refund/cancellation behavior before enabling prepaid orders.

Before enabling online payments:

- Provider dashboard account is approved.
- Production key and secret are configured in `.env`.
- Webhook secret is configured.
- Webhook URL is reachable over HTTPS.
- One small live payment succeeds.
- Payment verification updates order correctly.
- Failed payment does not confirm order.
- Refund process is documented for support.

## 7. Support Setup

Prepare one support channel before inviting users:

- WhatsApp number or phone line.
- Support email.
- Admin user who checks support.
- Refund/cancellation policy.
- Failed delivery policy.
- Restaurant delay escalation process.
- Delivery partner no-response process.

Minimum response templates:

- Order delayed.
- Partner cannot find address.
- Merchant unavailable.
- Item unavailable.
- Refund requested.
- Payment deducted but order not confirmed.
- Delivery marked incorrectly.

## 8. First Launch Smoke Test

Run this after every deploy and before public invite:

1. Customer login.
2. Restaurant browse.
3. Add item/options.
4. Checkout with COD.
5. Confirm `order.created` exists.
6. Merchant login.
7. Merchant accepts order.
8. Merchant marks ready for pickup.
9. Confirm `order.status_changed` exists.
10. Partner login.
11. Partner sees available delivery.
12. Partner claims delivery.
13. Partner marks picked up.
14. Partner marks on the way.
15. Partner marks delivered with code.
16. Customer tracking shows delivered.
17. Run:

```bash
docker compose exec -T backend python manage.py relay_outbox_events --limit 100
```

18. Confirm pending order events are published.

## 9. First 10 Orders

For the first 10 real orders, manually watch:

- Order created.
- Merchant receives order.
- Merchant accepts within expected time.
- Merchant marks ready.
- Partner sees available delivery.
- Partner claims.
- Partner location/status updates.
- Customer tracking updates.
- Delivery completes with handoff code.
- Merchant payout state is correct.
- Partner payout state is correct.
- Notifications are created.
- No backend errors appear.

Useful checks:

```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 dispatch_worker
docker compose logs --tail=100 celery_worker
docker compose logs --tail=100 celery_beat
docker compose exec -T backend python manage.py shell -c "from orders.models import Order; print(list(Order.objects.values('id','status','total_amount').order_by('-created_at')[:10]))"
```

## 10. First 100 Users Checklist

Growth readiness:

- At least 2 active restaurants.
- At least 2 verified delivery partners.
- One backup delivery partner available by phone.
- Support contact shown clearly.
- Daily backups running.
- Restore drill already tested.
- Admin can disable a restaurant quickly.
- Merchant can mark items unavailable.
- Partner can become unavailable.
- Founder can manually monitor orders.

Operational checks:

- Review failed logins and user issues daily.
- Review unclaimed delivery situations daily.
- Review cancelled orders daily.
- Review payment issues daily.
- Review merchant preparation delays daily.
- Review customer complaints daily.
- Review partner payout totals daily.

Technical checks:

```bash
docker compose ps
curl -i https://your-domain.example/api/v1/health/
df -h
docker system df
docker compose logs --tail=100 backend
docker compose logs --tail=100 celery_worker
docker compose logs --tail=100 celery_beat
```

Do not scale features yet. For the first 100 users, stability and support matter more than new functionality.

## 11. Daily Launch Routine

Morning:

- Check service health.
- Check public health endpoint.
- Check backend logs.
- Check Celery logs.
- Check open orders.
- Check unclaimed deliveries.
- Check support messages.

During service hours:

- Keep admin dashboard open.
- Keep merchant support phone ready.
- Keep delivery partner support phone ready.
- Watch every order until the flow feels boring and predictable.

Evening:

- Run PostgreSQL backup.
- Run media backup.
- Copy backups off VPS.
- Review daily order issues.
- List fixes needed for next maintenance window.

## 12. No-Go Conditions

Do not invite public users if:

- HTTPS is broken.
- `DEBUG=True`.
- Backups are not verified.
- Restore has never been tested.
- Backend health fails.
- Celery worker is not consuming tasks.
- Celery beat is not scheduling tasks.
- `dispatch_worker` is not running.
- Merchant cannot accept a test order.
- Partner cannot claim and deliver a test order.
- Customer tracking does not update.
- Outbox relay fails.
- You do not have a support channel ready.

## 13. Launch Day Notes

Keep the first launch small:

- Invite a controlled group first.
- Start with a limited delivery area.
- Start with a limited restaurant set.
- Keep COD as the safest payment option until online payments are fully proven.
- Do not onboard more restaurants than support can handle.
- Do not onboard more users than delivery capacity can serve.

The first goal is not maximum traffic. The first goal is reliable completed orders.
