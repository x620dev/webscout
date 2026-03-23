"""Тесты для модуля конфигурации."""

from pathlib import Path

import pytest
import yaml

from src.core.config import AppConfig, BrowserConfig, HttpConfig, ScrapingConfig, load_config


def test_default_config():
    """Дефолтная конфигурация создаётся без ошибок."""
    cfg = AppConfig()
    assert cfg.browser.headless is True
    assert cfg.browser.viewport.width == 1920
    assert cfg.browser.viewport.height == 1080
    assert cfg.browser.locale == "ru-RU"
    assert cfg.browser.timezone == "Asia/Yekaterinburg"
    assert cfg.scraping.delay_min == 1.0
    assert cfg.scraping.delay_max == 3.0
    assert cfg.scraping.page_load_timeout == 30
    assert cfg.proxy.enabled is False
    assert cfg.output.format == "json"
    assert cfg.http.rate_limit == 5
    assert cfg.http.timeout == 30
    assert cfg.http.retries == 3


def test_load_config_from_yaml(tmp_path):
    """Конфигурация загружается из YAML-файла."""
    config_data = {
        "browser": {
            "headless": False,
            "viewport": {"width": 1280, "height": 720},
            "locale": "en-US",
            "timezone": "UTC",
        },
        "scraping": {
            "delay_min": 2.0,
            "max_results": 100,
        },
        "http": {
            "rate_limit": 3,
            "timeout": 15,
        },
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data))

    cfg = load_config(config_file)
    assert cfg.browser.headless is False
    assert cfg.browser.viewport.width == 1280
    assert cfg.browser.locale == "en-US"
    assert cfg.scraping.delay_min == 2.0
    assert cfg.scraping.max_results == 100
    assert cfg.http.rate_limit == 3
    assert cfg.http.timeout == 15
    # Дефолтные значения для полей, не указанных в YAML
    assert cfg.proxy.enabled is False


def test_load_config_missing_file():
    """Если файл не найден, возвращается дефолтная конфигурация."""
    cfg = load_config(Path("/nonexistent/config.yaml"))
    assert cfg.browser.headless is True
    assert cfg.scraping.max_results == 500


def test_load_config_empty_yaml(tmp_path):
    """Пустой YAML-файл → дефолтная конфигурация."""
    config_file = tmp_path / "empty.yaml"
    config_file.write_text("")

    cfg = load_config(config_file)
    assert cfg.browser.headless is True


def test_browser_config_custom():
    """BrowserConfig принимает кастомные значения."""
    cfg = BrowserConfig(headless=False, locale="en-US")
    assert cfg.headless is False
    assert cfg.locale == "en-US"


def test_scraping_config_custom():
    """ScrapingConfig принимает кастомные значения."""
    cfg = ScrapingConfig(delay_min=5.0, delay_max=10.0, max_results=50)
    assert cfg.delay_min == 5.0
    assert cfg.delay_max == 10.0
    assert cfg.max_results == 50


def test_http_config_custom():
    """HttpConfig принимает кастомные значения."""
    cfg = HttpConfig(rate_limit=10, timeout=60, retries=5)
    assert cfg.rate_limit == 10
    assert cfg.timeout == 60
    assert cfg.retries == 5
