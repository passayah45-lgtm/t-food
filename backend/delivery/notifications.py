from django.core.mail import send_mail


def notify_partner_assigned(delivery):
    partner = delivery.delivery_partner
    user = partner.user

    send_mail(
        subject='🚴 New Delivery Assigned',
        message=f'''
Hello {partner.partner_name},

You have been assigned a new delivery.

Order ID: {delivery.order.id}
Status: {delivery.get_status_display()}

Please check your dashboard.
''',
        from_email=None,
        recipient_list=[user.email],
        fail_silently=True,
    )


def notify_customer_status(delivery):
    customer_email = delivery.order.customer.email

    send_mail(
        subject='📦 Order Update',
        message=f'''
Your order #{delivery.order.id} status is now:

{delivery.get_status_display()}

Thank you for using our service.
''',
        from_email=None,
        recipient_list=[customer_email],
        fail_silently=True,
    )


def notify_admin_delivered(delivery):
    send_mail(
        subject='✅ Delivery Completed',
        message=f'''
Order #{delivery.order.id} has been delivered successfully.
''',
        from_email=None,
        recipient_list=['admin@fooddelivery.com'],
        fail_silently=True,
    )
