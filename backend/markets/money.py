from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class MoneyError(ValueError):
    pass


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError(f'Invalid money amount: {value!r}') from exc


def currency_code(value) -> str:
    code = getattr(value, 'code', value)
    code = str(code or '').upper()
    if len(code) != 3 or not code.isalpha():
        raise MoneyError('Currency must be a three-letter ISO 4217 code.')
    return code


def quantizer(minor_unit: int) -> Decimal:
    if minor_unit < 0 or minor_unit > 6:
        raise MoneyError('Currency minor unit must be between 0 and 6.')
    return Decimal('1').scaleb(-minor_unit)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str
    minor_unit: int = 2

    def __post_init__(self):
        minor_unit = int(self.minor_unit)
        amount = _to_decimal(self.amount).quantize(
            quantizer(minor_unit),
            rounding=ROUND_HALF_UP,
        )
        object.__setattr__(self, 'currency', currency_code(self.currency))
        object.__setattr__(self, 'minor_unit', minor_unit)
        object.__setattr__(self, 'amount', amount)

    @classmethod
    def zero(cls, currency, minor_unit: int = 2) -> 'Money':
        return cls(Decimal('0'), currency, minor_unit)

    @classmethod
    def from_minor_units(cls, value: int, currency, minor_unit: int = 2) -> 'Money':
        amount = Decimal(int(value)) / (Decimal(10) ** int(minor_unit))
        return cls(amount, currency, minor_unit)

    def quantized(self) -> 'Money':
        amount = self.amount.quantize(
            quantizer(self.minor_unit),
            rounding=ROUND_HALF_UP,
        )
        if amount == self.amount:
            return self
        return Money(amount, self.currency, self.minor_unit)

    def to_minor_units(self) -> int:
        multiplier = Decimal(10) ** self.minor_unit
        return int((self.amount * multiplier).to_integral_value(rounding=ROUND_HALF_UP))

    def same_currency(self, other: 'Money') -> None:
        if self.currency != other.currency or self.minor_unit != other.minor_unit:
            raise MoneyError('Cannot operate on money with different currencies.')

    def __add__(self, other: 'Money') -> 'Money':
        self.same_currency(other)
        return Money(self.amount + other.amount, self.currency, self.minor_unit)

    def __sub__(self, other: 'Money') -> 'Money':
        self.same_currency(other)
        return Money(self.amount - other.amount, self.currency, self.minor_unit)

    def __mul__(self, value) -> 'Money':
        return Money(self.amount * _to_decimal(value), self.currency, self.minor_unit)

    def __rmul__(self, value) -> 'Money':
        return self.__mul__(value)

    def __truediv__(self, value) -> 'Money':
        divisor = _to_decimal(value)
        if divisor == 0:
            raise MoneyError('Cannot divide money by zero.')
        return Money(self.amount / divisor, self.currency, self.minor_unit)

    def __neg__(self) -> 'Money':
        return Money(-self.amount, self.currency, self.minor_unit)

    def __str__(self):
        return f'{self.currency} {self.amount:.{self.minor_unit}f}'

    def as_dict(self) -> dict:
        return {
            'amount': str(self.amount),
            'currency': self.currency,
            'minor_unit': self.minor_unit,
            'minor_amount': self.to_minor_units(),
        }
