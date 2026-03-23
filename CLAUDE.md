# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

WebScout — монорепозиторий CLI-инструментов для исследования рынка через веб. Единая точка входа `webscout` объединяет 5 независимых инструментов (OrgScout, JobScout, PriceScout, ReviewScout, LegalScout), разделяющих общее ядро: браузерную автоматизацию, антидетект, HTTP-клиент, форматирование вывода.

Полная спецификация: `docs/webscout.md`.

## Стек

- Python 3.12+, asyncio
- CLI: Typer
- Модели: Pydantic v2
- Браузер: Playwright (Chromium)
- HTTP: httpx (async)
- Пакетный менеджер: uv или pip
- Конфигурация: YAML (`config.yaml`)

## Команды

```bash
# Установка зависимостей (когда появится pyproject.toml)
uv sync                 # или pip install -e .

# Установка браузера Playwright
playwright install chromium

# Запуск CLI
webscout <tool> <command> [OPTIONS]

# Тесты
pytest
pytest tests/test_core/          # тесты ядра
pytest tests/test_orgscout/      # тесты конкретного инструмента
pytest -k "test_name"            # один тест

# Линтинг (если настроен)
ruff check src/
ruff format src/
```

## Архитектура

### Общая структура: ядро + независимые инструменты

```
src/
├── cli.py              # Корневой CLI — собирает подкоманды всех инструментов
├── mcp_server.py       # MCP-сервер (все инструменты, фаза 6)
├── core/               # Общее ядро (не зависит от инструментов)
│   ├── browser.py      # Playwright browser pool
│   ├── anti_detect.py  # Задержки, user-agent, fingerprint
│   ├── renderer.py     # Рендеринг SPA (network interception)
│   ├── http_client.py  # httpx async + rate limiting + retry
│   ├── models.py       # Базовые модели: Contacts, GeoPoint, ScrapedEntity
│   └── config.py       # Загрузка config.yaml
├── output/             # Общие форматтеры (json, csv, ai-summary)
└── tools/              # Каждый инструмент в своей директории
    ├── orgscout/       # Организации с карт (Яндекс.Карты, 2ГИС)
    ├── jobscout/       # Вакансии (hh.ru API, Avito, SuperJob)
    ├── pricescout/     # Прайсы (YCLIENTS, Dikidi)
    ├── reviewscout/    # Отзывы (Яндекс, Flamp, Google)
    └── legalscout/     # Юрданные (ЕГРЮЛ, Rusprofile)
```

### Ключевые принципы

- **Зависимости инструментов**: `tools/<name>/` импортирует из `core/` и `output/`. Может импортировать модели из других tools (для обогащения), но не их внутреннюю логику.
- **Обмен данными**: JSON-файлы как промежуточный формат. Каждый инструмент выводит JSON-массив, команда `enrich` читает чужой JSON и добавляет данные в поле `_enriched`.
- **Два типа скраперов**: SPA через Playwright (Яндекс.Карты, Avito, YCLIENTS) и HTTP API без браузера (hh.ru, ЕГРЮЛ). Выбор определяется источником.
- **Результаты** хранятся в `data/` — поддиректории по формату (`json/`, `csv/`, `ai/`), не по инструменту.
- **`webscout render <url>`** — общая утилита для рендеринга произвольных SPA-страниц, не привязана к конкретному инструменту.

### Структура каждого инструмента

```
tools/<name>/
├── __init__.py
├── cli.py         # Typer-подкоманды (scrape, fetch, enrich)
├── models.py      # Pydantic-модели, наследуют ScrapedEntity
└── scrapers/      # По одному модулю на источник данных
    ├── source1.py
    └── source2.py
```

### Антидетект

Обязательно для всех скраперов: рандомизированные задержки, ротация User-Agent, уважение rate limits API. При обнаружении капчи — пауза и ожидание ручного решения (headless: false).

## Язык

Проект на русском: комментарии, документация, коммиты — на русском. Код (имена переменных, функций, классов) — на английском.

## Текущий статус

Проект в фазе 0 (инициализация). Код ещё не написан — есть только спецификация. Фазы 0–1 — портирование из существующего проекта OrgScout (core, output, orgscout scrapers), не написание с нуля. Фазы разработки описаны в `docs/webscout.md` (разделы «Фазы разработки»).
