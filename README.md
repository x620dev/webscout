# WebScout

CLI-инструменты для исследования рынка через веб. Единая точка входа `webscout` объединяет 5 независимых инструментов, которые позволяют найти организации, вакансии, цены, отзывы и юридические данные — и свести всё в один JSON-файл.

## Установка

```bash
# Клонировать репозиторий
git clone <repo-url> && cd WebScout

# Установить пакет (рекомендуется в виртуальном окружении)
pip install -e .

# Для разработки (pytest, ruff)
pip install -e ".[dev]"

# Для MCP-сервера (опционально)
pip install -e ".[mcp]"

# Установить браузер Playwright
playwright install chromium
```

**Требования:** Python 3.12+

## Быстрый старт

```bash
# Найти 50 маникюрных салонов Уфы на Яндекс.Картах
webscout org scrape yandex-maps -q "маникюр" --city "Уфа"

# Узнать кто из них нанимает сотрудников
webscout jobs enrich data/json/результат.json --source hh

# Собрать прайсы с виджетов онлайн-записи
webscout prices collect data/json/результат.json

# Получить юридические данные
webscout legal enrich data/json/результат.json --source egrul
```

---

## Инструменты

- [`org`](#orgscout-org) — организации с картографических сервисов (Яндекс.Карты, 2ГИС)
- [`jobs`](#jobscout-jobs) — вакансии (hh.ru, Avito)
- [`prices`](#pricescout-prices) — прайс-листы (YCLIENTS, Dikidi)
- [`reviews`](#reviewscout-reviews) — отзывы (Яндекс, Flamp)
- [`legal`](#legalscout-legal) — юридические данные (ЕГРЮЛ, Rusprofile)
- [`merge`](#merge) — объединение и дедупликация JSON-файлов
- [`pipeline`](#pipeline) — автоматизация цепочки команд из YAML
- [`render`](#render) — рендеринг произвольных SPA-страниц

---

## OrgScout (`org`)

Поиск организаций на картографических сервисах. Это основной инструмент — его результат (JSON-массив организаций) используется остальными инструментами для обогащения.

### `org scrape` — массовый поиск

Открывает карту в браузере, выполняет поиск, скроллит результаты и собирает карточки организаций.

```bash
webscout org scrape <источник> [опции]
```

**Источники:** `yandex-maps`, `2gis`

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--query` | `-q` | Поисковый запрос (обязательный) | — |
| `--city` | | Город (обязательный) | — |
| `--max-results` | `-n` | Лимит результатов | 50 |
| `--output` | `-o` | Путь к выходному файлу | автоименование |
| `--format` | `-f` | Формат: `json`, `ai-summary` | json |
| `--csv` | | Дополнительно сохранить TSV | false |
| `--append` | | Дозапуск: дописать к существующему файлу | false |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Базовый поиск
webscout org scrape yandex-maps -q "стоматология" --city "Москва"

# Большой скрап из 2ГИС с CSV
webscout org scrape 2gis -q "автосервис" --city "Казань" -n 300 --csv

# Дозапуск: продолжить прерванный скрап
webscout org scrape yandex-maps -q "маникюр" --city "Уфа" -n 200 \
  -o data/json/ufa_manicure.json --append

# Сохранить в конкретный файл
webscout org scrape 2gis -q "кофейня" --city "Санкт-Петербург" \
  -o data/json/spb_coffee.json
```

**Когда использовать:**
- Начало любого исследования рынка — сначала собираешь базу организаций
- Нужно получить контакты, адреса, рейтинги, категории компаний в городе
- Результат — отправная точка для `enrich`-команд остальных инструментов

### `org fetch` — карточка одной организации

Открывает конкретную карточку и извлекает все доступные данные.

```bash
webscout org fetch <источник> --org-url <URL> [опции]
```

**Источники:** `yandex-maps`, `2gis`

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--org-url` | | URL карточки (обязательный) | — |
| `--output` | `-o` | Путь к выходному файлу | вывод в консоль |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Получить карточку с Яндекс.Карт
webscout org fetch yandex-maps \
  --org-url "https://yandex.ru/maps/org/salon_krasoty/1234567890/"

# Получить карточку из 2ГИС и сохранить в файл
webscout org fetch 2gis \
  --org-url "https://2gis.ru/ufa/firm/70000001012345" \
  -o data/json/firm_card.json
```

**Когда использовать:**
- Нужна детальная информация об одной конкретной организации
- Проверка данных из массового скрапа

---

## JobScout (`jobs`)

Поиск вакансий и обогащение организаций данными о найме.

### `jobs search` — поиск вакансий

```bash
webscout jobs search <источник> [опции]
```

**Источники:**
- `hh` — hh.ru (REST API, быстро, без браузера)
- `avito` — Avito Работа (Playwright, SPA)

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--query` | `-q` | Поисковый запрос (обязательный) | — |
| `--city` | | Город (обязательный) | — |
| `--max-results` | `-n` | Лимит результатов | 50 |
| `--output` | `-o` | Путь к выходному файлу | автоименование |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Вакансии маникюристов в Уфе на hh.ru
webscout jobs search hh -q "мастер маникюра" --city "Уфа"

# Вакансии на Avito
webscout jobs search avito -q "администратор салона красоты" --city "Москва" -n 100
```

**Когда использовать:**
- Нужно понять, какие компании в нише активно нанимают (признак роста)
- Анализ зарплат и требований к сотрудникам в отрасли

### `jobs enrich` — обогащение организаций вакансиями

Берёт JSON-файл организаций и для каждой ищет вакансии. Совпадения определяются нечётким матчингом названий компаний. Результат записывается в поле `_enriched.jobs`.

```bash
webscout jobs enrich <файл.json> [опции]
```

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--source` | `-s` | Источник вакансий: `hh` | hh |
| `--output` | `-o` | Выходной файл | перезаписать входной |
| `--threshold` | `-t` | Порог схожести названий (0–100) | 70.0 |
| `--max-per-org` | | Лимит вакансий на организацию | 10 |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Обогатить вакансиями с hh.ru (результат пишется в тот же файл)
webscout jobs enrich data/json/ufa_manicure.json

# Сохранить в другой файл, строже матчить
webscout jobs enrich data/json/studios.json -o data/json/studios_with_jobs.json -t 85
```

---

## PriceScout (`prices`)

Сбор прайс-листов с CRM-виджетов онлайн-записи (YCLIENTS, Dikidi).

### `prices fetch` — прайс одной организации

```bash
webscout prices fetch <источник> [опции]
```

**Источники:** `yclients`, `dikidi`

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--url` | `-u` | URL виджета онлайн-записи (обязательный) | — |
| `--name` | `-n` | Название организации (для метаданных) | — |
| `--output` | `-o` | Путь к выходному файлу | автоименование |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Прайс с YCLIENTS
webscout prices fetch yclients -u "https://n.yclients.com/company/123456" -n "Nail Studio"

# Прайс с Dikidi
webscout prices fetch dikidi -u "https://dikidi.net/salon/456789" -n "Барбершоп"
```

### `prices collect` — массовый сбор прайсов

Обходит JSON-файл организаций, читает поле `online_booking`, определяет CRM по домену и собирает прайсы. Результат — в `_enriched.prices`.

```bash
webscout prices collect <файл.json> [опции]
```

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--output` | `-o` | Выходной файл | перезаписать входной |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Автоопределение CRM:**
- `yclients.com`, `n.yclients.com`, `w.yclients.com` → YCLIENTS
- `dikidi.net` → Dikidi
- Остальные домены пропускаются

**Примеры:**

```bash
# Собрать прайсы для всех организаций с online_booking
webscout prices collect data/json/ufa_manicure.json

# Сохранить в отдельный файл
webscout prices collect data/json/studios.json -o data/json/studios_with_prices.json
```

**Когда использовать:**
- Сравнение цен на услуги в нише
- Поиск организаций с конкретной ценовой политикой

---

## ReviewScout (`reviews`)

Сбор отзывов об организациях с Яндекс.Карт и Flamp.

### `reviews scrape` — отзывы одной организации

```bash
webscout reviews scrape <источник> [опции]
```

**Источники:** `yandex`, `flamp`

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--url` | `-u` | URL карточки/страницы организации (обязательный) | — |
| `--max-reviews` | `-n` | Лимит отзывов | 50 |
| `--output` | `-o` | Путь к выходному файлу | автоименование |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Отзывы с Яндекс.Карт
webscout reviews scrape yandex \
  -u "https://yandex.ru/maps/org/salon_krasoty/1234567890/" -n 100

# Отзывы с Flamp
webscout reviews scrape flamp \
  -u "https://ufa.flamp.ru/firm/salon_krasoty-12345" -n 50
```

### `reviews enrich` — обогащение организаций отзывами

Для каждой организации в JSON берёт `source_url` (или `flamp_url`) и собирает отзывы. Результат — в `_enriched.reviews`.

```bash
webscout reviews enrich <файл.json> [опции]
```

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--source` | `-s` | Платформа: `yandex`, `flamp` | yandex |
| `--max-reviews` | `-n` | Лимит отзывов на организацию | 20 |
| `--output` | `-o` | Выходной файл | перезаписать входной |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Обогатить отзывами с Яндекс.Карт (по source_url из OrgScout)
webscout reviews enrich data/json/ufa_manicure.json

# Обогатить отзывами с Flamp
webscout reviews enrich data/json/studios.json --source flamp
```

**Когда использовать:**
- Оценка репутации организаций в нише
- Поиск организаций с проблемами (низкий рейтинг) или лидеров (высокий рейтинг)

---

## LegalScout (`legal`)

Поиск юридической информации: ИНН, ОГРН, директор, учредители, уставный капитал, статус.

### `legal search` — поиск юрлица

```bash
webscout legal search <источник> [опции]
```

**Источники:**
- `egrul` — ЕГРЮЛ / nalog.ru (HTTP API, быстро, без браузера)
- `rusprofile` — Rusprofile.ru (Playwright, больше данных)

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--name` | `-n` | Название организации | — |
| `--inn` | | ИНН организации | — |
| `--city` | | Город (только для egrul, фильтр по региону) | — |
| `--max-results` | | Лимит результатов | 10 (egrul), 5 (rusprofile) |
| `--details` | `-d` | Загружать полную карточку (только rusprofile) | false |
| `--output` | `-o` | Путь к выходному файлу | автоименование |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

Обязательно указать `--name` или `--inn` (хотя бы один).

**Примеры:**

```bash
# Поиск по названию в ЕГРЮЛ
webscout legal search egrul --name "Красота" --city "Уфа"

# Поиск по ИНН в ЕГРЮЛ
webscout legal search egrul --inn "0278123456"

# Поиск на Rusprofile с детальной карточкой
webscout legal search rusprofile --name "Салон Красоты Люкс" --details
```

### `legal enrich` — обогащение организаций юрданными

Для каждой организации ищет юрлицо по имени (и городу), находит совпадение через нечёткий матчинг и записывает данные в `_enriched.legal`.

```bash
webscout legal enrich <файл.json> [опции]
```

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--source` | `-s` | Источник: `egrul`, `rusprofile` | egrul |
| `--output` | `-o` | Выходной файл | перезаписать входной |
| `--threshold` | `-t` | Порог схожести названий (0–100) | 70.0 |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Обогатить данными из ЕГРЮЛ
webscout legal enrich data/json/ufa_manicure.json

# Обогатить данными с Rusprofile
webscout legal enrich data/json/studios.json --source rusprofile

# С жёстким порогом матчинга
webscout legal enrich data/json/studios.json -t 85 -o data/json/studios_legal.json
```

**Когда использовать:**
- Юридическая проверка контрагентов
- Выявление новых компаний (по дате регистрации)
- Оценка масштаба бизнеса (уставный капитал, число сотрудников)

---

## Merge

Объединение нескольких JSON-файлов с автоматической дедупликацией по нечёткому сравнению названий.

```bash
webscout merge <файл1.json> <файл2.json> [файл3.json ...] [опции]
```

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--output` | `-o` | Выходной файл | автоименование |
| `--threshold` | `-t` | Порог схожести для дедупликации (0–100) | 80.0 |
| `--name-key` | | Поле с названием организации | name |
| `--city-key` | | Поле с городом | city |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Объединить результаты из Яндекс.Карт и 2ГИС
webscout merge data/json/yandex_results.json data/json/2gis_results.json \
  -o data/json/all_orgs.json

# Строгая дедупликация
webscout merge file1.json file2.json file3.json -t 90
```

**Когда использовать:**
- Сбор данных из нескольких источников (Яндекс + 2ГИС) — в merge исключаются дубли
- Объединение результатов нескольких запросов по одной нише

---

## Pipeline

Автоматизация цепочки команд через YAML-файл. Каждый шаг транслируется в команду `webscout` и выполняется последовательно.

```bash
webscout pipeline <файл.yaml> [опции]
```

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--dry-run` | | Показать команды без выполнения | false |
| `--stop-on-error` | `-e` | Остановить при первой ошибке | false |
| `--config` | `-c` | Путь к config.yaml (для всех шагов) | config.yaml |

### Формат YAML

```yaml
name: "Маникюр Уфа — полное исследование"
steps:
  - tool: org
    command: scrape
    source: yandex-maps
    params:
      query: "маникюр"
      city: "Уфа"
      max_results: 200
    output: data/json/ufa_manicure.json

  - tool: org
    command: scrape
    source: 2gis
    params:
      query: "ногтевая студия"
      city: "Уфа"
      max_results: 200
    output: data/json/ufa_nails_2gis.json

  - tool: jobs
    command: enrich
    input: data/json/ufa_manicure.json
    source: hh

  - tool: prices
    command: collect
    input: data/json/ufa_manicure.json

  - tool: reviews
    command: enrich
    input: data/json/ufa_manicure.json
    source: yandex

  - tool: legal
    command: enrich
    input: data/json/ufa_manicure.json
    source: egrul
```

**Поля шага:**

| Поле | Описание | Обязательное |
|------|----------|:---:|
| `tool` | Инструмент: org, jobs, prices, reviews, legal | да |
| `command` | Команда: scrape, search, fetch, enrich, collect | да |
| `source` | Источник данных (yandex-maps, hh, egrul, ...) | нет |
| `input` | Входной JSON-файл (для enrich/collect) | нет |
| `output` | Выходной файл | нет |
| `params` | Словарь параметров (query, city, max_results, ...) | нет |

**Примеры запуска:**

```bash
# Выполнить пайплайн
webscout pipeline research.yaml

# Посмотреть что будет выполнено (без запуска)
webscout pipeline research.yaml --dry-run

# Остановить при первой ошибке
webscout pipeline research.yaml --stop-on-error
```

**Когда использовать:**
- Полный цикл исследования рынка одной командой
- Повторяемые исследования (сохранить YAML, запускать периодически)
- Автоматизация рутинных сценариев

---

## Render

Утилита для рендеринга произвольных SPA-страниц. Открывает страницу в браузере, ждёт загрузки и возвращает HTML или текст. Может перехватывать API-ответы.

```bash
webscout render <URL> [опции]
```

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--output` | `-o` | Файл для сохранения | вывод в консоль |
| `--format` | `-f` | Формат: `html`, `text` | html |
| `--wait-for` | `-w` | CSS-селектор для ожидания загрузки | — |
| `--intercept` | `-i` | Паттерн URL для перехвата API-ответов (можно несколько) | — |
| `--config` | `-c` | Путь к config.yaml | config.yaml |
| `--verbose` | `-v` | Подробный лог | false |

**Примеры:**

```bash
# Получить отрендеренный HTML SPA-страницы
webscout render "https://example.com/spa-page" -o page.html

# Получить текст, дождавшись загрузки элемента
webscout render "https://example.com/app" -f text -w ".content-loaded"

# Перехватить API-ответы
webscout render "https://example.com/app" \
  -i "api.example.com/data" \
  -o page.html
```

**Когда использовать:**
- Отладка: посмотреть что видит Playwright на произвольной странице
- Извлечение данных из SPA, для которого нет отдельного скрапера
- Перехват API-вызовов SPA-приложений

---

## Полный цикл исследования рынка

Пошаговый пример — исследование рынка маникюра в Уфе:

```bash
# 1. Собрать организации с Яндекс.Карт
webscout org scrape yandex-maps -q "маникюр" --city "Уфа" -n 200 \
  -o data/json/studios.json

# 2. Дополнить результатами из 2ГИС
webscout org scrape 2gis -q "ногтевая студия" --city "Уфа" -n 200 \
  -o data/json/studios_2gis.json

# 3. Объединить с дедупликацией
webscout merge data/json/studios.json data/json/studios_2gis.json \
  -o data/json/studios_all.json

# 4. Кто нанимает сотрудников? (признак роста)
webscout jobs enrich data/json/studios_all.json

# 5. Собрать прайсы с YCLIENTS/Dikidi
webscout prices collect data/json/studios_all.json

# 6. Собрать отзывы
webscout reviews enrich data/json/studios_all.json

# 7. Юридическая проверка
webscout legal enrich data/json/studios_all.json --source egrul

# Итог: studios_all.json содержит полную картину —
# организации с контактами, вакансиями, ценами, отзывами и юрданными
```

Тот же сценарий можно оформить как [пайплайн](#pipeline) и запускать одной командой.

---

## Выходные данные

### Автоименование файлов

Если `-o` не указан, файл создаётся автоматически:

```
data/{формат}/{дата}_{инструмент}_{город}_{запрос}.json
```

Пример: `data/json/20260324_orgscout_ufa_manikyur.json`

Кириллица в имени файла автоматически транслитерируется.

### Формат JSON

Результат — JSON-массив объектов. Каждый объект содержит поля соответствующей модели. При обогащении данные добавляются в поле `_enriched`:

```json
{
  "name": "Nail Studio",
  "address": "Уфа, ул. Ленина, 10",
  "contacts": {"phone": "+7-347-123-45-67"},
  "rating": 4.8,
  "source_url": "https://yandex.ru/maps/org/...",
  "_enriched": {
    "jobs": [...],
    "prices": {...},
    "reviews": {...},
    "legal": {...}
  }
}
```

### Режим `--append`

Позволяет продолжить прерванный скрап. При повторном запуске с `--append` уже собранные URL пропускаются.

### TSV-вывод (`--csv`)

В `org scrape` можно дополнительно получить файл `.tsv` — удобно для Excel / Google Sheets.

---

## Конфигурация

Файл `config.yaml` в корне проекта:

```yaml
browser:
  headless: true              # false — показывать браузер (нужно для капчи)
  viewport:
    width: 1920
    height: 1080
  locale: "ru-RU"
  timezone: "Asia/Yekaterinburg"
  rotate_user_agent: true     # ротация User-Agent

scraping:
  delay_min: 1.0              # минимальная задержка между действиями (сек)
  delay_max: 3.0              # максимальная задержка
  max_results: 500            # глобальный лимит
  scroll_pause: 2.0           # пауза при скролле
  page_load_timeout: 30       # таймаут загрузки страницы (сек)
  retry_on_captcha: true      # ждать ручного решения капчи
  captcha_timeout: 120        # таймаут ожидания капчи (сек)

http:
  rate_limit: 5               # запросов в секунду (для HTTP API)
  timeout: 30                 # таймаут HTTP-запроса
  retries: 3                  # число повторов

proxy:
  enabled: false
  url: null                   # "http://user:pass@host:port"

output:
  format: json
  pretty: true
  include_photos: false
```

Путь к конфигу можно указать через `--config` / `-c` в любой команде.

### Капча

При обнаружении капчи скрапер уведомляет и ставит на паузу. Для ручного решения нужно:
1. Установить `headless: false` в config.yaml
2. Решить капчу в открывшемся браузере
3. Скрапер продолжит автоматически

---

## MCP-сервер

WebScout предоставляет MCP-сервер для интеграции с AI-ассистентами (Claude Desktop и др.).

### Установка

```bash
pip install -e ".[mcp]"
```

### Запуск

```bash
python -m src.mcp_server
```

### Конфигурация Claude Desktop

Добавить в `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "webscout": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/WebScout"
    }
  }
}
```

### Доступные инструменты

| Инструмент | Описание | Основные параметры |
|-----------|----------|-------------------|
| `scrape_organizations` | Поиск организаций | query, city, source, max_results |
| `fetch_organization` | Карточка организации | url, source |
| `search_vacancies` | Поиск вакансий | query, city, source, max_results |
| `fetch_prices` | Прайс организации | url, org_name, source |
| `scrape_reviews` | Отзывы | url, source, max_reviews |
| `search_legal` | Юрданные | name, inn, city, source, max_results |

---

## Разработка

```bash
# Установить dev-зависимости
pip install -e ".[dev]"

# Тесты
pytest
pytest tests/test_core/          # тесты ядра
pytest tests/test_orgscout/      # тесты OrgScout
pytest -k "test_name"            # один тест

# Линтинг
ruff check src/
ruff format src/
```

## Лицензия

Проект для исследования рынка и личного использования.
