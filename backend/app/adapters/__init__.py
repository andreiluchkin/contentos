from .base import PlatformAdapter, PublishResult, Metrics, ValidationResult
from .telegram import TelegramAdapter
from .registry import AdapterRegistry, registry

__all__ = [
    "PlatformAdapter", "PublishResult", "Metrics", "ValidationResult",
    "TelegramAdapter",
    "AdapterRegistry", "registry",
]
