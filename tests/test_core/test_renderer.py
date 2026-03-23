"""Тесты для Renderer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import ScrapingConfig
from src.core.renderer import OutputFormat, PageRenderer, RenderResult


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Hello</body></html>")
    page.inner_text = AsyncMock(return_value="Hello")
    page.close = AsyncMock()
    page.on = MagicMock()

    mock_response = AsyncMock()
    mock_response.status = 200
    page.goto = AsyncMock(return_value=mock_response)
    page.wait_for_selector = AsyncMock()
    return page


@pytest.fixture
def mock_context(mock_page):
    ctx = AsyncMock()
    ctx.new_page = AsyncMock(return_value=mock_page)
    return ctx


@pytest.fixture
def scraping_config():
    return ScrapingConfig(page_load_timeout=30)


@pytest.mark.asyncio
async def test_render_html(mock_context, scraping_config):
    """Рендеринг в формате HTML."""
    renderer = PageRenderer(mock_context, scraping_config)
    result = await renderer.render("https://example.com", fmt=OutputFormat.HTML)

    assert result.url == "https://example.com"
    assert result.content == "<html><body>Hello</body></html>"
    assert result.format == OutputFormat.HTML
    assert result.status == 200


@pytest.mark.asyncio
async def test_render_text(mock_context, mock_page, scraping_config):
    """Рендеринг в формате текст."""
    renderer = PageRenderer(mock_context, scraping_config)
    result = await renderer.render("https://example.com", fmt=OutputFormat.TEXT)

    assert result.content == "Hello"
    assert result.format == OutputFormat.TEXT
    mock_page.inner_text.assert_called_once_with("body")


@pytest.mark.asyncio
async def test_render_with_wait_for(mock_context, mock_page, scraping_config):
    """Рендеринг с ожиданием CSS-селектора."""
    renderer = PageRenderer(mock_context, scraping_config)
    await renderer.render("https://example.com", wait_for=".content-loaded")

    mock_page.wait_for_selector.assert_called_once_with(
        ".content-loaded",
        timeout=30000,
    )


@pytest.mark.asyncio
async def test_render_page_closed_on_success(mock_context, mock_page, scraping_config):
    """Страница закрывается после успешного рендеринга."""
    renderer = PageRenderer(mock_context, scraping_config)
    await renderer.render("https://example.com")
    mock_page.close.assert_called_once()


@pytest.mark.asyncio
async def test_render_page_closed_on_error(mock_context, mock_page, scraping_config):
    """Страница закрывается даже при ошибке."""
    mock_page.goto = AsyncMock(side_effect=Exception("Network error"))
    renderer = PageRenderer(mock_context, scraping_config)

    with pytest.raises(Exception, match="Network error"):
        await renderer.render("https://example.com")

    mock_page.close.assert_called_once()


@pytest.mark.asyncio
async def test_render_with_interception(mock_context, mock_page, scraping_config):
    """Рендеринг с перехватом API-ответов настраивает обработчик."""
    renderer = PageRenderer(mock_context, scraping_config)
    await renderer.render(
        "https://example.com",
        intercept_urls=["api.example.com"],
    )

    mock_page.on.assert_called_once()
    assert mock_page.on.call_args[0][0] == "response"


@pytest.mark.asyncio
async def test_render_default_config(mock_context):
    """Рендерер работает с дефолтной конфигурацией."""
    renderer = PageRenderer(mock_context)
    result = await renderer.render("https://example.com")
    assert result.status == 200


def test_render_result_dataclass():
    """RenderResult создаётся с правильными полями."""
    result = RenderResult(
        url="https://example.com",
        content="<html></html>",
        format=OutputFormat.HTML,
        status=200,
    )
    assert result.url == "https://example.com"
    assert result.intercepted_responses == []


def test_output_format_enum():
    """OutputFormat содержит HTML и TEXT."""
    assert OutputFormat.HTML.value == "html"
    assert OutputFormat.TEXT.value == "text"
