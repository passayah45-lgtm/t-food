from django.core.exceptions import ValidationError

from .providers.local_mock import LocalMockVisualLabelExtractor
from .validators import strip_image_exif, validate_visual_search_image


PROVIDERS = {
    'local_mock': LocalMockVisualLabelExtractor,
}


def get_visual_label_extractor(provider_code='local_mock'):
    provider_cls = PROVIDERS.get(provider_code)
    if not provider_cls:
        raise ValidationError(f'Unknown visual search provider: {provider_code}.')
    provider = provider_cls()
    if not provider.is_configured():
        raise ValidationError('Visual search provider is not configured.')
    return provider


def normalize_visual_query(labels):
    clean_labels = [
        str(label).strip().lower()
        for label in labels
        if str(label).strip()
    ]
    return ' '.join(dict.fromkeys(clean_labels))


def extract_visual_product_labels(image_file, provider_code='local_mock', context=None):
    image_metadata = validate_visual_search_image(image_file)
    safe_image = strip_image_exif(image_file)
    provider = get_visual_label_extractor(provider_code)
    result = provider.extract_labels(safe_image, context=context or {})
    labels = result.get('labels') or ['product']
    normalized_query = normalize_visual_query(labels) or 'product'
    return {
        'provider_code': provider.provider_code,
        'labels': labels,
        'confidence': float(result.get('confidence') or 0),
        'normalized_query': normalized_query,
        'fallback_query': normalized_query or 'product',
        'metadata': {
            'image': image_metadata,
            **(result.get('metadata') or {}),
        },
    }

