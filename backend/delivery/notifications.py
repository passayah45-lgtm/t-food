from django.core.mail import send_mail


def _order_display_label(order):
    code = getattr(order, 'merchant_order_code', '') or getattr(order, 'id', '')
    return f'Order {code}' if code else 'Order'


def notify_partner_assigned(delivery):
    partner = delivery.delivery_partner
    user = partner.user
    order_label = _order_display_label(delivery.order)

    send_mail(
        subject='🚴 New Delivery Assigned',
        message=f'''
Hello {partner.partner_name},

You have been assigned a new delivery.

{order_label}
Status: {delivery.get_status_display()}

Please check your dashboard.
''',
        from_email=None,
        recipient_list=[user.email],
        fail_silently=True,
    )


def notify_customer_status(delivery):
    customer_email = delivery.order.customer.email
    order_label = _order_display_label(delivery.order)

    send_mail(
        subject='📦 Order Update',
        message=f'''
{order_label} status is now:

{delivery.get_status_display()}

Thank you for using our service.
''',
        from_email=None,
        recipient_list=[customer_email],
        fail_silently=True,
    )


def notify_admin_delivered(delivery):
    order_label = _order_display_label(delivery.order)

    send_mail(
        subject='✅ Delivery Completed',
        message=f'''
{order_label} has been delivered successfully.
''',
        from_email=None,
        recipient_list=['admin@fooddelivery.com'],
        fail_silently=True,
    )
