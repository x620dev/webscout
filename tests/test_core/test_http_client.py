"""Тесты для HTTP-клиента (http_client.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.config import HttpConfig, ProxyConfig
from src.core.http_client import HttpClient


@pytest.fixture
def http_config():
    return HttpConfig(rate_limit=5, timeout=10, retries=2)


def _make_mock_response(json_data=None, text_data=None, status_code=200):
    """Создать мок httpx.Response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    if json_data is not None:
        mock_resp.json = MagicMock(return_value=json_data)
    if text_data is not None:
        mock_resp.text = text_data
    return mock_resp


@pytest.mark.asyncio
async def test_http_client_start_stop(http_config):
    """HttpClient запускается и останавливается без ошибок."""
    client = HttpClient(http_config)
    await client.start()
    assert client._client is not None
    await client.stop()
    assert client._client is None


@pytest.mark.asyncio
async def test_http_client_context_manager(http_config):
    """HttpClient работает как async context manager."""
    async with HttpClient(http_config) as client:
        assert client._client is not None
    assert client._client is None


@pytest.mark.asyncio
async def test_get_json_not_started():
    """get_json бросает RuntimeError если клиент не запущен."""
    client = HttpClient()
    with pytest.raises(RuntimeError, match="не запущен"):
        await client._get_json("https://example.com")


@pytest.mark.asyncio
async def test_get_text_not_started():
    """get_text бросает RuntimeError если клиент не запущен."""
    client = HttpClient()
    with pytest.raises(RuntimeError, match="не запущен"):
        await client._get_text("https://example.com")


@pytest.mark.asyncio
async def test_get_json_success(http_config):
    """get_json возвращает распарсенный JSON."""
    mock_response = _make_mock_response(json_data={"items": [1, 2, 3]})

    async with HttpClient(http_config) as client:
        client._client.get = AsyncMock(return_value=mock_response)
        result = await client._get_json("https://api.example.com/data")

    assert result == {"items": [1, 2, 3]}


@pytest.mark.asyncio
async def test_get_text_success(http_config):
    """get_text возвращает текст ответа."""
    mock_response = _make_mock_response(text_data="hello world")

    async with HttpClient(http_config) as client:
        client._client.get = AsyncMock(return_value=mock_response)
        result = await client._get_text("https://example.com/page")

    assert result == "hello world"


@pytest.mark.asyncio
async def test_http_client_proxy_enabled(http_config):
    """HttpClient создаёт клиент с прокси при proxy.enabled=True."""
    proxy_config = ProxyConfig(enabled=True, url="http://proxy.example.com:8080")

    with patch("src.core.http_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = AsyncMock()
        client = HttpClient(http_config, proxy=proxy_config)
        await client.start()

        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["proxy"] == "http://proxy.example.com:8080"
        await client.stop()


@pytest.mark.asyncio
async def test_http_client_proxy_disabled(http_config):
    """HttpClient не передаёт прокси при proxy.enabled=False."""
    proxy_config = ProxyConfig(enabled=False, url="http://proxy.example.com:8080")

    with patch("src.core.http_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = AsyncMock()
        client = HttpClient(http_config, proxy=proxy_config)
        await client.start()

        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs.get("proxy") is None
        await client.stop()


@pytest.mark.asyncio
async def test_get_json_uses_semaphore(http_config):
    """get_json использует семафор для ограничения параллельных запросов."""
    mock_response = _make_mock_response(json_data={})

    async with HttpClient(http_config) as client:
        client._client.get = AsyncMock(return_value=mock_response)
        # Проверяем, что семафор инициализирован с rate_limit
        assert client._semaphore._value == http_config.rate_limit
        await client._get_json("https://api.example.com/")
