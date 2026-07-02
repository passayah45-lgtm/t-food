import uuid
from contextvars import ContextVar


CORRELATION_ID_HEADER = 'HTTP_X_CORRELATION_ID'
CORRELATION_ID_RESPONSE_HEADER = 'X-Correlation-ID'

_correlation_id = ContextVar('correlation_id', default='')


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(value: str):
    return _correlation_id.set(value)


def reset_correlation_id(token) -> None:
    _correlation_id.reset(token)


def new_correlation_id() -> str:
    return str(uuid.uuid4())

