from .base import PlatformAdapter
from .telegram import TelegramAdapter
from .instagram import InstagramAdapter
from .tiktok import TikTokAdapter
from .youtube import YouTubeAdapter


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        self._adapters[adapter.platform] = adapter

    def get(self, platform: str) -> PlatformAdapter:
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"No adapter registered for platform: {platform}")
        return adapter

    def available(self) -> list[str]:
        return list(self._adapters.keys())


registry = AdapterRegistry()
registry.register(TelegramAdapter())
registry.register(InstagramAdapter())
registry.register(TikTokAdapter())
registry.register(YouTubeAdapter())
