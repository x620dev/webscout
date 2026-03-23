"""Тесты для Browser Manager."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.browser import BrowserManager
from src.core.config import BrowserConfig, ProxyConfig


@pytest.fixture
def browser_config():
    return BrowserConfig(
        headless=True,
        locale="ru-RU",
        timezone="Asia/Yekaterinburg",
        rotate_user_agent=False,
    )


@pytest.fixture
def browser_config_with_ua():
    return BrowserConfig(
        headless=True,
        locale="ru-RU",
        timezone="Asia/Yekaterinburg",
        rotate_user_agent=True,
    )


@pytest.mark.asyncio
async def test_browser_manager_start_stop():
    """BrowserManager запускает и останавливает Playwright."""
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        manager = BrowserManager()
        await manager.start()

        assert manager.browser is mock_browser
        mock_playwright.chromium.launch.assert_called_once_with(headless=True)

        await manager.stop()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert manager.browser is None


@pytest.mark.asyncio
async def test_browser_manager_context_manager():
    """BrowserManager работает как async context manager."""
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        async with BrowserManager() as manager:
            assert manager.browser is mock_browser

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()


@pytest.mark.asyncio
async def test_browser_manager_new_context(browser_config):
    """new_context создаёт контекст с правильными параметрами (без ротации UA)."""
    mock_context = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        async with BrowserManager(browser_config) as manager:
            ctx = await manager.new_context()

        mock_browser.new_context.assert_called_once_with(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Asia/Yekaterinburg",
        )
        assert ctx is mock_context


@pytest.mark.asyncio
async def test_browser_manager_new_context_with_user_agent(browser_config_with_ua):
    """new_context добавляет user_agent при rotate_user_agent=True."""
    mock_context = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        async with BrowserManager(browser_config_with_ua) as manager:
            await manager.new_context()

        call_kwargs = mock_browser.new_context.call_args[1]
        assert "user_agent" in call_kwargs
        assert isinstance(call_kwargs["user_agent"], str)
        assert "Mozilla" in call_kwargs["user_agent"]


@pytest.mark.asyncio
async def test_browser_manager_new_context_not_started():
    """new_context бросает RuntimeError если браузер не запущен."""
    manager = BrowserManager()
    with pytest.raises(RuntimeError, match="не запущен"):
        await manager.new_context()


@pytest.mark.asyncio
async def test_browser_manager_new_context_overrides(browser_config):
    """new_context принимает переопределения параметров."""
    mock_context = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        async with BrowserManager(browser_config) as manager:
            await manager.new_context(locale="en-US")

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["locale"] == "en-US"


@pytest.mark.asyncio
async def test_browser_manager_proxy_enabled(browser_config):
    """BrowserManager передаёт proxy в chromium.launch при proxy.enabled=True."""
    proxy_config = ProxyConfig(enabled=True, url="http://user:pass@proxy.example.com:8080")
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        manager = BrowserManager(browser_config, proxy=proxy_config)
        await manager.start()
        await manager.stop()

    mock_playwright.chromium.launch.assert_called_once_with(
        headless=True,
        proxy={"server": "http://user:pass@proxy.example.com:8080"},
    )


@pytest.mark.asyncio
async def test_browser_manager_proxy_disabled(browser_config):
    """BrowserManager не передаёт proxy при proxy.enabled=False."""
    proxy_config = ProxyConfig(enabled=False, url="http://proxy.example.com:8080")
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        manager = BrowserManager(browser_config, proxy=proxy_config)
        await manager.start()
        await manager.stop()

    mock_playwright.chromium.launch.assert_called_once_with(headless=True)


@pytest.mark.asyncio
async def test_browser_manager_no_proxy(browser_config):
    """BrowserManager без proxy запускает браузер без proxy-параметра."""
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("src.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        manager = BrowserManager(browser_config)
        await manager.start()
        await manager.stop()

    mock_playwright.chromium.launch.assert_called_once_with(headless=True)
