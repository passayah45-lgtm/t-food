import re

from .base import VisualLabelExtractor


LABEL_HINTS = [
    (('pizza',), ['pizza', 'food']),
    (('biryani', 'chicken', 'burger', 'dosa', 'meal', 'food'), ['food']),
    (('medicine', 'tablet', 'capsule', 'pharmacy', 'drug'), ['medicine', 'tablet', 'pharmacy']),
    (('rice', 'grain', 'bag', 'flour', 'grocery'), ['rice', 'grocery']),
    (('shirt', 'shoe', 'phone', 'retail'), ['retail']),
    (('parcel', 'courier', 'package'), ['courier']),
]


class LocalMockVisualLabelExtractor(VisualLabelExtractor):
    provider_code = 'local_mock'
    display_name = 'Local mock visual label extractor'

    def is_configured(self):
        return True

    def capabilities(self):
        return {
            'labels': True,
            'external_calls': False,
            'requires_credentials': False,
            'deterministic': True,
        }

    def extract_labels(self, image_file, context=None):
        filename = getattr(image_file, 'name', '') or ''
        haystack = re.sub(r'[^a-z0-9]+', ' ', filename.lower())
        labels = []
        for hints, mapped_labels in LABEL_HINTS:
            if any(hint in haystack for hint in hints):
                labels.extend(mapped_labels)
        labels = _unique(labels) or ['product']
        confidence = 0.82 if labels != ['product'] else 0.35
        return {
            'provider_code': self.provider_code,
            'labels': labels,
            'confidence': confidence,
            'metadata': {
                'source': 'filename_hints',
                'external_calls': False,
            },
        }


def _unique(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result

