"""Renderer — рендеринг SPA-страниц через Playwright."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from playwright.async_api import BrowserContext, Page, Response

from src.core.config import ScrapingConfig


class OutputFormat(str, Enum):
    HTML = "html"
    TEXT = "text"


@dataclass
class RenderResult:
    """Результат рендеринга страницы."""

    url: str
    content: str
    format: OutputFormat
    status: int | None = None
    intercepted_responses: list[dict] = field(default_factory=list)


class PageRenderer:
    """Рендеринг произвольных SPA-страниц.

    Открывает URL в браузерном контексте, дожидается полной загрузки
    и возвращает контент в выбранном формате (HTML или текст).
    """

    def __init__(self, context: BrowserContext, config: ScrapingConfig | None = None) -> None:
        self._context = context
        self._config = config or ScrapingConfig()

    async def render(
        self,
        url: str,
        fmt: OutputFormat = OutputFormat.HTML,
        wait_for: str | None = None,
        intercept_urls: list[str] | None = None,
    ) -> RenderResult:
        """Открыть URL и вернуть отрендеренный контент.

        Args:
            url: URL страницы для рендеринга.
            fmt: Формат вывода — HTML или текст.
            wait_for: CSS-селектор, ожидание появления которого подтверждает загрузку.
            intercept_urls: Паттерны URL для перехвата API-ответов.
        """
        page = await self._context.new_page()
        intercepted: list[dict] = []

        if intercept_urls:
            self._setup_interception(page, intercept_urls, intercepted)

        try:
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=self._config.page_load_timeout * 1000,
            )

            if wait_for:
                await page.wait_for_selector(
                    wait_for,
                    timeout=self._config.page_load_timeout * 1000,
                )

            if fmt == OutputFormat.HTML:
                content = await page.content()
            else:
                content = await page.inner_text("body")

            return RenderResult(
                url=url,
                content=content,
                format=fmt,
                status=response.status if response else None,
                intercepted_responses=intercepted,
            )
        finally:
            await page.close()

    @staticmethod
    def _setup_interception(
        page: Page,
        url_patterns: list[str],
        storage: list[dict],
    ) -> None:
        """Настроить перехват API-ответов по паттернам URL."""

        async def on_response(response: Response) -> None:
            for pattern in url_patterns:
                if pattern in response.url:
                    try:
                        body = await response.json()
                    except Exception:
                        body = await response.text()
                    storage.append({
                        "url": response.url,
                        "status": response.status,
                        "body": body,
                    })
                    break

        page.on("response", on_response)
