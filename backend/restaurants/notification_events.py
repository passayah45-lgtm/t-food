import logging

from django.db import transaction

from notifications.models import Notification
from notifications.services import notify_event
from operations_access.permissions import VIEW_SUPPORT
from restaurants.models import ReviewPhoto


logger = logging.getLogger(__name__)


def _scope_for_review_photo(photo):
    branch = getattr(photo.review, 'restaurant', None)
    market = getattr(branch, 'market', None)
    return {
        'branch': branch,
        'market': market,
        'country_code': (
            getattr(branch, 'country_code', None)
            or getattr(market, 'country_code', None)
        ),
        'city': getattr(branch, 'city_ref', None),
        'area': getattr(branch, 'area_ref', None),
        'order': getattr(photo.review, 'order', None),
    }


def _safe_notify_event(**kwargs):
    try:
        return notify_event(**kwargs)
    except Exception:
        logger.exception('Review photo notification delivery failed.')
        return None


def schedule_review_photo_pending_notification(photo, actor=None):
    photo_id = photo.id
    review_id = photo.review_id
    branch = getattr(photo.review, 'restaurant', None)
    branch_name = branch.branch_name or branch.rest_name if branch else 'Review'
    scope = _scope_for_review_photo(photo)

    def emit():
        _safe_notify_event(
            event_type='review_photo.pending',
            actor=actor,
            recipients={
                'operations': {
                    'scope': scope,
                    'permission': VIEW_SUPPORT,
                },
            },
            subject=scope.get('order'),
            scope=scope,
            payload={
                'title': 'Review photo pending moderation',
                'message': f'{branch_name} has a review photo awaiting moderation.',
                'intent': 'support',
                'metadata': {
                    'review_photo_id': photo_id,
                    'review_id': review_id,
                    'status': ReviewPhoto.STATUS_PENDING,
                },
            },
            priority=Notification.PRIORITY_NORMAL,
            category=Notification.CATEGORY_SUPPORT,
            action_url='/operations?view=review-photo-moderation',
            idempotency_key=f'review-photo-pending:{photo_id}',
        )

    transaction.on_commit(emit)


def schedule_review_photo_moderation_notification(photo, action, actor=None):
    event_by_action = {
        'APPROVE': 'review_photo.approved',
        'REJECT': 'review_photo.rejected',
        'HIDE': 'review_photo.hidden',
    }
    status_by_action = {
        'APPROVE': ReviewPhoto.STATUS_APPROVED,
        'REJECT': ReviewPhoto.STATUS_REJECTED,
        'HIDE': ReviewPhoto.STATUS_HIDDEN,
    }
    event_type = event_by_action[action]
    status_label = status_by_action[action]
    photo_id = photo.id
    review_id = photo.review_id
    branch = getattr(photo.review, 'restaurant', None)
    scope = _scope_for_review_photo(photo)
    action_url = f'/restaurants/{branch.id}#reviews' if branch else '/orders'
    metadata = {
        'review_photo_id': photo_id,
        'review_id': review_id,
        'status': status_label,
    }
    if action in {'REJECT', 'HIDE'} and photo.moderation_reason:
        metadata['moderation_reason'] = photo.moderation_reason

    def emit():
        _safe_notify_event(
            event_type=event_type,
            actor=actor,
            recipients=[photo.review.customer],
            subject=scope.get('order'),
            scope=scope,
            payload={
                'title': f'Review photo {status_label.lower()}',
                'message': f'Your review photo was {status_label.lower()}.',
                'intent': 'informational',
                'metadata': metadata,
            },
            priority=Notification.PRIORITY_NORMAL,
            category=Notification.CATEGORY_SUPPORT,
            action_url=action_url,
            idempotency_key=f'review-photo-{status_label.lower()}:{photo_id}',
        )

    transaction.on_commit(emit)
