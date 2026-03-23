"""Конфигурация WebScout — загрузка из YAML с валидацией через Pydantic."""

from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.yaml"


class ViewportConfig(BaseModel):
    width: int = 1920
    height: int = 1080


class BrowserConfig(BaseModel):
    headless: bool = True
    viewport: ViewportConfig = ViewportConfig()
    locale: str = "ru-RU"
    timezone: str = "Asia/Yekaterinburg"
    rotate_user_agent: bool = True


class ScrapingConfig(BaseModel):
    delay_min: float = 1.0
    delay_max: float = 3.0
    max_results: int = 500
    scroll_pause: float = 2.0
    page_load_timeout: int = 30
    retry_on_captcha: bool = True
    captcha_timeout: int = 120


class HttpConfig(BaseModel):
    rate_limit: int = 5  # запросов в секунду
    timeout: int = 30
    retries: int = 3


class ProxyConfig(BaseModel):
    enabled: bool = False
    url: str | None = None


class OutputConfig(BaseModel):
    format: str = "json"
    pretty: bool = True
    include_photos: bool = False


class AppConfig(BaseModel):
    browser: BrowserConfig = BrowserConfig()
    scraping: ScrapingConfig = ScrapingConfig()
    http: HttpConfig = HttpConfig()
    proxy: ProxyConfig = ProxyConfig()
    output: OutputConfig = OutputConfig()


def load_config(path: Path | None = None) -> AppConfig:
    """Загрузить конфигурацию из YAML-файла. Если файл не найден — вернуть дефолтные значения."""
    config_path = path or DEFAULT_CONFIG_PATH
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return AppConfig(**data)
    return AppConfig()
