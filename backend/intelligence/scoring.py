from dataclasses import dataclass, field
from decimal import Decimal

from restaurants.services import restaurant_accepting_orders


REASON_LABELS = {
    'ordered_before': 'You ordered here before',
    'favorite': 'Matches your favorites',
    'close_to_you': 'Close to your location',
    'fast_nearby': 'Fast nearby option',
    'popular': 'Popular near you',
    'top_rated': 'Top rated',
    'verified_merchant': 'Verified merchant',
    'open_now': 'Open now',
    'category_match': 'Matches food you like',
    'new_to_try': 'New to try',
}

REASON_PRIORITY = (
    'ordered_before',
    'favorite',
    'fast_nearby',
    'close_to_you',
    'popular',
    'top_rated',
    'category_match',
    'verified_merchant',
    'new_to_try',
    'open_now',
)


@dataclass
class RecommendationCandidate:
    restaurant: object
    score: Decimal = Decimal('0')
    reason_codes: list[str] = field(default_factory=list)

    @property
    def reason_label(self):
        for code in REASON_PRIORITY:
            if code in self.reason_codes:
                return REASON_LABELS[code]
        return 'Recommended for you'

    @property
    def is_serviceable(self):
        return getattr(self.restaurant, 'is_serviceable', None)

    @property
    def distance_km(self):
        return getattr(self.restaurant, 'distance_km', None)

    @property
    def is_accepting_orders(self):
        return restaurant_accepting_orders(self.restaurant)

    def add_reason(self, code):
        if code not in self.reason_codes:
            self.reason_codes.append(code)

    def add_score(self, amount, code=None):
        self.score += Decimal(str(amount))
        if code:
            self.add_reason(code)

    def output_score(self):
        return float(self.score.quantize(Decimal('0.01')))
