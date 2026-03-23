"""HTTP-клиент для API без браузера — httpx async + rate limiting + retry."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.core.anti_detect import get_random_user_agent, with_retry
from src.core.config import HttpConfig, ProxyConfig

logger = logging.getLogger(__name__)


class HttpClient:
    """Async HTTP-клиент для открытых API (hh.ru, ЕГРЮЛ и др.).

    Включает:
    - Rate limiting (ограничение числа одновременных запросов)
    - Retry с exponential backoff
    - Ротацию User-Agent
    - Поддержку прокси

    Использование:
        async with HttpClient(config) as client:
            data = await client.get_json("https://api.hh.ru/vacancies", params={"text": "..."})
    """

    def __init__(
        self,
        config: HttpConfig | None = None,
        proxy: ProxyConfig | None = None,
    ) -> None:
        self._config = config or HttpConfig()
        self._proxy = proxy
        self._client: httpx.AsyncClient | None = None
        # Семафор ограничивает число одновременных запросов = rate_limit
        self._semaphore = asyncio.Semaphore(self._config.rate_limit)

    async def start(self) -> None:
        """Инициализировать httpx-клиент."""
        proxy_url = (
            self._proxy.url
            if self._proxy and self._proxy.enabled and self._proxy.url
            else None
        )
        self._client = httpx.AsyncClient(
            timeout=self._config.timeout,
            proxy=proxy_url,
            headers={
                "User-Agent": get_random_user_agent(),
                "Accept": "application/json",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )

    async def stop(self) -> None:
        """Закрыть httpx-клиент."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Выполнить GET-запрос и вернуть распарсенный JSON.

        Args:
            url: URL эндпоинта.
            params: Query-параметры.
            headers: Дополнительные заголовки (перекрывают дефолтные).

        Returns:
            Распарсенный JSON (dict, list и т.п.)

        Raises:
            httpx.HTTPStatusError: При HTTP-ошибке (4xx, 5xx).
            httpx.RequestError: При ошибке сети.
        """
        return await with_retry(
            self._get_json,
            url,
            params=params,
            headers=headers,
            max_attempts=self._config.retries,
            base_delay=1.0,
        )

    async def get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Выполнить GET-запрос и вернуть текст ответа.

        Args:
            url: URL.
            params: Query-параметры.
            headers: Дополнительные заголовки.

        Returns:
            Текст ответа.
        """
        return await with_retry(
            self._get_text,
            url,
            params=params,
            headers=headers,
            max_attempts=self._config.retries,
            base_delay=1.0,
        )

    async def _get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        if not self._client:
            raise RuntimeError("HttpClient не запущен. Используйте async with или вызовите start().")
        async with self._semaphore:
            logger.debug("GET JSON: %s params=%s", url, params)
            response = await self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        if not self._client:
            raise RuntimeError("HttpClient не запущен. Используйте async with или вызовите start().")
        async with self._semaphore:
            logger.debug("GET TEXT: %s params=%s", url, params)
            response = await self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.text

    async def __aenter__(self) -> HttpClient:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
