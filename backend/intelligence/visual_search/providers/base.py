from abc import ABC, abstractmethod


class VisualLabelExtractor(ABC):
    provider_code = None
    display_name = None

    def is_configured(self):
        return False

    def capabilities(self):
        return {
            'labels': True,
            'external_calls': False,
            'requires_credentials': True,
        }

    @abstractmethod
    def extract_labels(self, image_file, context=None):
        raise NotImplementedError

