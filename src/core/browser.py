"""Browser Manager — запуск и управление Playwright Chromium."""

from __future__ import annotations

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from src.core.config import BrowserConfig, ProxyConfig
from src.core.anti_detect import get_random_user_agent


class BrowserManager:
    """Управление жизненным циклом Playwright-браузера.

    Использование:
        async with BrowserManager(config) as manager:
            ctx = await manager.new_context()
            page = await ctx.new_page()
            ...
    """

    def __init__(
        self,
        config: BrowserConfig | None = None,
        proxy: ProxyConfig | None = None,
    ) -> None:
        self._config = config or BrowserConfig()
        self._proxy = proxy
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        """Запустить Playwright и браузер Chromium."""
        self._playwright = await async_playwright().start()

        launch_kwargs: dict = {"headless": self._config.headless}

        # Прокси на уровне браузера применяется ко всем контекстам
        if self._proxy and self._proxy.enabled and self._proxy.url:
            launch_kwargs["proxy"] = {"server": self._proxy.url}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def stop(self) -> None:
        """Закрыть браузер и освободить ресурсы Playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def new_context(self, **overrides) -> BrowserContext:
        """Создать новый браузерный контекст с настройками из конфигурации.

        При включённой ротации user-agent каждый контекст получает случайный UA
        из пула реальных браузерных строк.
        """
        if not self._browser:
            raise RuntimeError("BrowserManager не запущен. Вызовите start() или используйте async with.")

        defaults: dict = {
            "viewport": {
                "width": self._config.viewport.width,
                "height": self._config.viewport.height,
            },
            "locale": self._config.locale,
            "timezone_id": self._config.timezone,
        }

        if self._config.rotate_user_agent:
            defaults["user_agent"] = get_random_user_agent()

        defaults.update(overrides)
        return await self._browser.new_context(**defaults)

    @property
    def browser(self) -> Browser | None:
        return self._browser

    async def __aenter__(self) -> BrowserManager:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
