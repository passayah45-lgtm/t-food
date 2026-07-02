import logging
import time

from .correlation import (
    CORRELATION_ID_HEADER,
    CORRELATION_ID_RESPONSE_HEADER,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)


logger = logging.getLogger('tfood.request')


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.META.get(CORRELATION_ID_HEADER) or new_correlation_id()
        token = set_correlation_id(correlation_id)
        request.correlation_id = correlation_id
        try:
            response = self.get_response(request)
            response[CORRELATION_ID_RESPONSE_HEADER] = correlation_id
            return response
        finally:
            reset_correlation_id(token)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        user = getattr(request, 'user', None)
        user_id = user.id if getattr(user, 'is_authenticated', False) else None
        logger.info(
            'HTTP request completed',
            extra={
                'operation': 'http_request',
                'request_id': getattr(request, 'correlation_id', ''),
                'user_id': user_id,
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': duration_ms,
            },
        )
        return response
