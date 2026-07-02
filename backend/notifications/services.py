from dataclasses import dataclass, field
from string import Formatter

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q

from .models import Notification, NotificationTemplate
from .preferences import in_app_enabled
from .realtime import broadcast_notification_created_on_commit
from .tasks import create_notification_task


@dataclass
class ResolvedRecipient:
    user: object
    recipient_type: str = Notification.RECIPIENT_CUSTOMER


@dataclass
class NotificationResult:
    notifications: list = field(default_factory=list)
    skipped_duplicates: int = 0
    errors: list = field(default_factory=list)

    @property
    def created(self):
        return self.notifications


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def _is_user(value):
    User = get_user_model()
    return isinstance(value, User)


def _iter_values(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _scope_value(scope, key):
    if not scope:
        return None
    if isinstance(scope, dict):
        return scope.get(key)
    return getattr(scope, key, None)


def _normalize_scope(scope=None, subject=None):
    scope = scope or {}
    subject = subject or _scope_value(scope, 'subject')
    order = _scope_value(scope, 'order') or (
        subject if subject.__class__.__name__ == 'Order' else None
    )
    branch = _scope_value(scope, 'branch') or getattr(order, 'pickup_branch', None)
    market = (
        _scope_value(scope, 'market')
        or getattr(order, 'market', None)
        or getattr(branch, 'market', None)
    )
    city = _scope_value(scope, 'city') or getattr(branch, 'city_ref', None)
    area = _scope_value(scope, 'area') or getattr(branch, 'area_ref', None)
    if area and not city:
        city = getattr(area, 'city', None)
    if area and not market:
        market = getattr(area, 'market', None)
    if city and not market:
        market = getattr(city, 'market', None)
    country_code = (
        _scope_value(scope, 'country_code')
        or getattr(branch, 'country_code', None)
        or getattr(market, 'country_code', None)
    )
    if country_code:
        country_code = str(country_code).upper()
    return {
        'market': market,
        'country_code': country_code or None,
        'city': city,
        'area': area,
        'branch': branch,
        'order': order,
    }


def _kind_for_category(category):
    if category in {
        Notification.CATEGORY_ORDER,
        Notification.CATEGORY_PAYMENT,
        Notification.CATEGORY_DELIVERY,
    }:
        return category
    return 'ACCOUNT'


def _safe_template_render(template, payload):
    values = _SafeFormatDict(payload or {})
    formatter = Formatter()
    return (
        formatter.vformat(template.title_template, (), values),
        formatter.vformat(template.message_template, (), values),
    )


def _template_for_event(event_type, language='en'):
    if not event_type:
        return None
    return (
        NotificationTemplate.objects
        .filter(
            Q(code=event_type) | Q(event_type=event_type),
            language=language or 'en',
            is_active=True,
        )
        .order_by('code', 'id')
        .first()
    )


def _dedupe_recipients(recipients):
    seen = set()
    deduped = []
    for recipient in recipients:
        if not recipient or not recipient.user:
            continue
        key = (recipient.user.id, recipient.recipient_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(recipient)
    return deduped


def resolve_merchant_recipients(merchant=None, branch=None, include_owner=True):
    recipients = []
    if not merchant and branch:
        merchant = getattr(branch.owner, 'merchant_profile', None)
    if include_owner and merchant and merchant.user_id and merchant.user.is_active:
        recipients.append(ResolvedRecipient(
            merchant.user,
            Notification.RECIPIENT_MERCHANT_OWNER,
        ))
    return recipients


def _staff_is_notification_eligible(staff):
    return (
        staff
        and staff.user
        and staff.user.is_active
        and staff.membership_status == staff.STATUS_ACTIVE
        and staff.verification_status == staff.VERIFICATION_VERIFIED
    )


def _notification_intent(event_type='', category=None, payload=None):
    payload = payload or {}
    if payload.get('intent'):
        return str(payload.get('intent')).lower()
    event = (event_type or '').lower()
    category = (category or '').upper()
    if any(token in event for token in ('payout', 'ledger')):
        return 'finance'
    if 'refund' in event:
        return 'support' if category == Notification.CATEGORY_SUPPORT else 'finance'
    if category == Notification.CATEGORY_PAYMENT or any(
        token in event for token in ('payment', 'cod')
    ):
        return 'payment'
    if category in {
        Notification.CATEGORY_DISPATCH,
        Notification.CATEGORY_DELIVERY,
        Notification.CATEGORY_RIDER,
    } or any(token in event for token in ('dispatch', 'delivery', 'rider')):
        return 'dispatch'
    if any(
        token in event
        for token in ('preparation', 'preparing', 'kitchen', 'order.ready')
    ):
        return 'kitchen'
    if category == Notification.CATEGORY_SUPPORT or any(
        token in event for token in ('support', 'ticket', 'escalation')
    ):
        return 'support'
    if category == Notification.CATEGORY_STAFF or 'staff' in event:
        return 'staff'
    if category == Notification.CATEGORY_INTELLIGENCE or any(
        token in event for token in ('analytics', 'insight', 'summary')
    ):
        return 'informational'
    if category == Notification.CATEGORY_MERCHANT or any(
        token in event for token in ('branch', 'health', 'warning')
    ):
        return 'branch'
    return 'informational'


def _role_can_receive_notification(staff, *, event_type='', category=None, priority=None, payload=None):
    from merchant_staff.models import MerchantStaffMember

    if not _staff_is_notification_eligible(staff):
        return False
    role = staff.role
    if role in {
        MerchantStaffMember.ROLE_OWNER,
        MerchantStaffMember.ROLE_ADMIN,
    }:
        return True
    intent = _notification_intent(event_type, category, payload)
    if role == MerchantStaffMember.ROLE_BRANCH_MANAGER:
        return intent in {
            'kitchen',
            'payment',
            'dispatch',
            'support',
            'staff',
            'branch',
            'informational',
        }
    if role == MerchantStaffMember.ROLE_KITCHEN_STAFF:
        return intent == 'kitchen'
    if role == MerchantStaffMember.ROLE_CASHIER:
        return intent == 'payment'
    if role == MerchantStaffMember.ROLE_DISPATCHER:
        return intent == 'dispatch'
    if role == MerchantStaffMember.ROLE_FINANCE_STAFF:
        return intent in {'finance', 'payment'}
    if role == MerchantStaffMember.ROLE_CUSTOMER_SUPPORT:
        return intent == 'support'
    if role == MerchantStaffMember.ROLE_VIEWER:
        action_required = bool((payload or {}).get('action_required'))
        if priority in {Notification.PRIORITY_HIGH, Notification.PRIORITY_CRITICAL}:
            return False
        return not action_required and intent == 'informational'
    return False


def resolve_merchant_staff_recipients(
    merchant=None,
    branch=None,
    roles=None,
    event_type='',
    category=None,
    priority=None,
    payload=None,
):
    from merchant_staff.models import MerchantStaffMember

    if not merchant and branch:
        merchant = getattr(branch.owner, 'merchant_profile', None)
    if not merchant:
        return []
    queryset = (
        MerchantStaffMember.objects
        .select_related('user', 'merchant')
        .prefetch_related('branch_access')
        .filter(
            merchant=merchant,
            user__is_active=True,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
        )
    )
    if roles:
        queryset = queryset.filter(role__in=set(_iter_values(roles)))
    recipients = []
    for staff in queryset:
        if not _role_can_receive_notification(
            staff,
            event_type=event_type,
            category=category,
            priority=priority,
            payload=payload,
        ):
            continue
        if branch and not staff.is_company_wide:
            if not staff.branch_access.filter(branch=branch).exists():
                continue
        recipients.append(ResolvedRecipient(
            staff.user,
            Notification.RECIPIENT_MERCHANT_STAFF,
        ))
    return recipients


def resolve_staff_recipients(merchant=None, branch=None, roles=None):
    return resolve_merchant_staff_recipients(
        merchant=merchant,
        branch=branch,
        roles=roles,
    )


def _operations_scope_matches(actor, scope):
    from operations_access.permissions import (
        can_access_area,
        can_access_city,
        can_access_country,
        can_access_market,
    )

    if not actor or not actor.permissions:
        return False
    if actor.is_global_scope:
        return True
    market = scope.get('market')
    country_code = scope.get('country_code')
    city = scope.get('city')
    area = scope.get('area')
    branch = scope.get('branch')
    if area:
        return can_access_area(actor, area)
    if city:
        return can_access_city(actor, city)
    if branch:
        if getattr(branch, 'area_ref_id', None):
            return can_access_area(actor, branch.area_ref)
        if getattr(branch, 'city_ref_id', None):
            return can_access_city(actor, branch.city_ref)
        if getattr(branch, 'market_id', None):
            return can_access_market(actor, branch.market)
        if getattr(branch, 'country_code', None):
            return can_access_country(actor, branch.country_code)
        return False
    if market:
        return can_access_market(actor, market)
    if country_code:
        return can_access_country(actor, country_code)
    return False


def resolve_operations_recipients(scope=None, permission=None):
    from operations_access.permissions import get_operations_actor

    User = get_user_model()
    normalized_scope = _normalize_scope(scope)
    users = (
        User.objects
        .filter(Q(is_staff=True) | Q(operations_staff_profile__isnull=False))
        .select_related('operations_staff_profile')
        .distinct()
    )
    recipients = []
    for user in users:
        actor = get_operations_actor(user)
        if not actor.permissions:
            continue
        if permission and not actor.can(permission):
            continue
        if _operations_scope_matches(actor, normalized_scope):
            recipient_type = Notification.RECIPIENT_OPERATIONS
            if actor.role == 'GLOBAL_ADMIN' or actor.is_superuser:
                recipient_type = Notification.RECIPIENT_GLOBAL_ADMIN
            elif actor.role == 'COUNTRY_ADMIN':
                recipient_type = Notification.RECIPIENT_COUNTRY_ADMIN
            elif actor.role == 'CITY_ADMIN':
                recipient_type = Notification.RECIPIENT_CITY_ADMIN
            elif actor.role == 'AREA_ADMIN':
                recipient_type = Notification.RECIPIENT_AREA_ADMIN
            recipients.append(ResolvedRecipient(user, recipient_type))
    return recipients


def _resolve_recipient_value(value, scope):
    if isinstance(value, ResolvedRecipient):
        return [value]
    if _is_user(value):
        return [ResolvedRecipient(value, Notification.RECIPIENT_CUSTOMER)]
    if hasattr(value, 'user') and value.__class__.__name__ == 'Customer':
        return [ResolvedRecipient(value.user, Notification.RECIPIENT_CUSTOMER)]
    if value.__class__.__name__ == 'MerchantProfile':
        return resolve_merchant_recipients(value, branch=scope.get('branch'))
    if value.__class__.__name__ == 'MerchantStaffMember':
        if not _staff_is_notification_eligible(value):
            return []
        return [ResolvedRecipient(value.user, Notification.RECIPIENT_MERCHANT_STAFF)]
    if value.__class__.__name__ == 'DeliveryPartner':
        return [ResolvedRecipient(value.user, Notification.RECIPIENT_DELIVERY_PARTNER)]
    return []


def resolve_recipients(
    recipients=None,
    subject=None,
    scope=None,
    event_type='',
    category=None,
    priority=None,
    payload=None,
):
    normalized_scope = _normalize_scope(scope, subject)
    resolved = []
    if isinstance(recipients, dict):
        for user in _iter_values(recipients.get('users')):
            resolved.extend(_resolve_recipient_value(user, normalized_scope))
        if recipients.get('customer'):
            resolved.extend(_resolve_recipient_value(
                recipients.get('customer'),
                normalized_scope,
            ))
        if recipients.get('merchant') or recipients.get('merchant_owner'):
            merchant = recipients.get('merchant') or recipients.get('merchant_owner')
            resolved.extend(resolve_merchant_recipients(
                merchant,
                branch=recipients.get('branch') or normalized_scope.get('branch'),
                include_owner=True,
            ))
        if recipients.get('merchant_staff'):
            staff_spec = recipients.get('merchant_staff')
            if isinstance(staff_spec, dict):
                resolved.extend(resolve_merchant_staff_recipients(
                    merchant=staff_spec.get('merchant') or recipients.get('merchant'),
                    branch=staff_spec.get('branch') or normalized_scope.get('branch'),
                    roles=staff_spec.get('roles'),
                    event_type=event_type,
                    category=category,
                    priority=priority,
                    payload=payload,
                ))
            else:
                resolved.extend(_resolve_recipient_value(staff_spec, normalized_scope))
        if recipients.get('delivery_partner'):
            resolved.extend(_resolve_recipient_value(
                recipients.get('delivery_partner'),
                normalized_scope,
            ))
        if recipients.get('operations'):
            operations_spec = recipients.get('operations')
            permission = None
            operation_scope = normalized_scope
            if isinstance(operations_spec, dict):
                permission = operations_spec.get('permission')
                operation_scope = operations_spec.get('scope') or normalized_scope
            resolved.extend(resolve_operations_recipients(operation_scope, permission))
    else:
        for value in _iter_values(recipients):
            resolved.extend(_resolve_recipient_value(value, normalized_scope))
    return _dedupe_recipients(resolved)


def build_notification(
    *,
    user,
    recipient_type,
    event_type,
    category,
    priority,
    scope,
    payload,
    action_url,
    idempotency_key=None,
):
    payload = payload or {}
    language = payload.get('language') or 'en'
    template = _template_for_event(event_type, language=language)
    if template:
        title, message = _safe_template_render(template, payload)
    else:
        title = payload.get('title') or event_type or 'Notification'
        message = payload.get('message') or title
    return Notification(
        user=user,
        recipient_type=recipient_type,
        category=category or Notification.CATEGORY_SYSTEM,
        event_type=event_type or '',
        priority=priority or Notification.PRIORITY_NORMAL,
        status=Notification.STATUS_UNREAD,
        kind=_kind_for_category(category),
        title=title,
        message=message,
        market=scope.get('market'),
        country_code=scope.get('country_code'),
        city=scope.get('city'),
        area=scope.get('area'),
        branch=scope.get('branch'),
        order=scope.get('order'),
        metadata=payload.get('metadata') or payload,
        action_url=action_url or payload.get('action_url') or '',
        idempotency_key=idempotency_key,
    )


def notify_event(
    event_type,
    actor=None,
    recipients=None,
    subject=None,
    scope=None,
    payload=None,
    priority=Notification.PRIORITY_NORMAL,
    category=None,
    action_url=None,
    idempotency_key=None,
    channels=None,
):
    del actor, channels
    result = NotificationResult()
    normalized_scope = _normalize_scope(scope, subject)
    resolved_recipients = resolve_recipients(
        recipients=recipients,
        subject=subject,
        scope=normalized_scope,
        event_type=event_type,
        category=category,
        priority=priority,
        payload=payload or {},
    )
    if not resolved_recipients:
        return result

    for recipient in resolved_recipients:
        if not in_app_enabled(
            recipient.user,
            category or Notification.CATEGORY_SYSTEM,
        ):
            continue
        recipient_key = idempotency_key
        if idempotency_key and len(resolved_recipients) > 1:
            recipient_key = f'{idempotency_key}:user:{recipient.user.id}'
        if recipient_key and Notification.objects.filter(
            idempotency_key=recipient_key,
        ).exists():
            result.skipped_duplicates += 1
            continue
        notification = build_notification(
            user=recipient.user,
            recipient_type=recipient.recipient_type,
            event_type=event_type,
            category=category or Notification.CATEGORY_SYSTEM,
            priority=priority,
            scope=normalized_scope,
            payload=payload or {},
            action_url=action_url,
            idempotency_key=recipient_key,
        )
        try:
            notification.save()
        except IntegrityError:
            result.skipped_duplicates += 1
            continue
        except Exception as exc:
            result.errors.append(str(exc))
            continue
        result.notifications.append(notification)
        broadcast_notification_created_on_commit(notification.id)
    return result


def create_notification(user, kind, title, message, order=None):
    if not user:
        return None
    result = notify_event(
        event_type='',
        recipients=[user],
        subject=order,
        scope={'order': order},
        payload={'title': title, 'message': message},
        category=kind if kind in {
            Notification.CATEGORY_ORDER,
            Notification.CATEGORY_PAYMENT,
            Notification.CATEGORY_DELIVERY,
        } else Notification.CATEGORY_SYSTEM,
    )
    return result.notifications[0] if result.notifications else None


def notify(user, kind, title, message, order=None):
    if not user:
        return None
    if settings.NOTIFICATIONS_ASYNC_ENABLED:
        order_id = order.id if order else None
        transaction.on_commit(
            lambda: create_notification_task.delay(
                user.id,
                kind,
                title,
                message,
                order_id,
            )
        )
        return None
    return create_notification(user, kind, title, message, order)
