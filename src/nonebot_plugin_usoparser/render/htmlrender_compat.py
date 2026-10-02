"""Support the page API used by htmlrender 0.6 and UBot's 0.8 runtime."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

try:
    from nonebot_plugin_htmlrender import get_new_page
except ImportError:
    from nonebot_plugin_htmlrender import get_default_application

    @asynccontextmanager
    async def get_new_page(
        device_scale_factor: float = 2, **options: Any
    ) -> AsyncIterator[Any]:
        application = get_default_application()
        async with application.extensions.playwright.page(
            device_scale_factor=device_scale_factor, **options
        ) as page:
            yield page
