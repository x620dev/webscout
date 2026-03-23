# WebScout — набор инструментов для исследования рынка через веб

## Идея

WebScout — монорепозиторий с набором CLI-инструментов для сбора и анализа данных из интернета. Каждый инструмент решает свою задачу (организации, вакансии, цены, отзывы), но все разделяют общее ядро: браузерную автоматизацию, антидетект, форматирование вывода.

Цель — дать AI-ассистенту (или человеку) возможность провести полноценное исследование рынка одним набором команд: найти игроков, узнать кто нанимает, сравнить цены, оценить репутацию.

## Проблема

Данные для исследования рынка разбросаны по десяткам SPA-сайтов (карты, вакансии, агрегаторы, соцсети). Каждый требует свою стратегию извлечения: DOM-парсинг, перехват API, прямые HTTP-запросы. Ручной сбор занимает часы. AI-ассистенты не имеют браузера и не могут работать с SPA.

WebScout решает это: единый интерфейс, общая инфраструктура, структурированный вывод в JSON — готовый для анализа человеком или AI.

---

## Архитектура

### Принцип: общее ядро + независимые инструменты

```
WebScout/
├── docs/                          # Документация
│   └── webscout.md                # Этот файл
├── pyproject.toml                 # Единый пакет, общие зависимости
├── config.yaml                    # Общий конфиг (браузер, прокси, антидетект)
├── data/                          # Общее хранилище результатов
│   ├── json/
│   ├── csv/
│   └── ai/
├── src/
│   ├── cli.py                     # Корневой CLI — собирает подкоманды
│   ├── core/                      # Общее ядро
│   │   ├── browser.py             # Playwright browser pool
│   │   ├── anti_detect.py         # Задержки, user-agent, fingerprint
│   │   ├── renderer.py            # Рендеринг SPA-страниц
│   │   ├── http_client.py         # HTTP-клиент для открытых API (без браузера)
│   │   ├── models.py              # Базовые модели (Contacts, GeoPoint и т.п.)
│   │   └── config.py              # Загрузка конфигурации
│   ├── output/                    # Общие форматтеры вывода
│   │   ├── json_writer.py
│   │   ├── csv_writer.py
│   │   ├── ai_summary.py
│   │   └── progress.py            # rich progress bar
│   ├── tools/                     # Инструменты (независимые модули)
│   │   ├── orgscout/              # Организации (карты)
│   │   │   ├── __init__.py
│   │   │   ├── cli.py
│   │   │   ├── models.py
│   │   │   └── scrapers/
│   │   │       ├── yandex_maps.py
│   │   │       ├── twogis.py
│   │   │       └── google_maps.py
│   │   ├── jobscout/              # Вакансии
│   │   │   ├── __init__.py
│   │   │   ├── cli.py
│   │   │   ├── models.py
│   │   │   └── scrapers/
│   │   │       ├── hh.py
│   │   │       └── avito.py
│   │   ├── pricescout/            # Цены и прайсы
│   │   │   ├── __init__.py
│   │   │   ├── cli.py
│   │   │   ├── models.py
│   │   │   └── scrapers/
│   │   │       ├── yclients.py
│   │   │       └── dikidi.py
│   │   ├── reviewscout/           # Отзывы и репутация
│   │   │   ├── __init__.py
│   │   │   ├── cli.py
│   │   │   ├── models.py
│   │   │   └── scrapers/
│   │   │       ├── flamp.py
│   │   │       ├── yandex_reviews.py
│   │   │       └── google_reviews.py
│   │   └── legalscout/            # Юридические данные
│   │       ├── __init__.py
│   │       ├── cli.py
│   │       ├── models.py
│   │       └── scrapers/
│   │           ├── egrul.py
│   │           └── rusprofile.py
│   └── mcp_server.py             # MCP-сервер (все инструменты)
└── tests/
    ├── test_core/
    ├── test_orgscout/
    ├── test_jobscout/
    └── ...
```

### Правила организации кода

- **`src/core/`** — код, который используют все инструменты. Не зависит от конкретного инструмента.
- **`src/tools/<name>/`** — изолированный инструмент. Может импортировать из `core/` и `output/`. Может импортировать модели из других tools (для обогащения), но не их внутреннюю логику.
- **`src/output/`** — общие форматтеры и прогресс. Каждый инструмент использует их для вывода.
- **`data/`** — результаты всех инструментов хранятся здесь. Поддиректории по формату, не по инструменту.

### Автоименование выходных файлов

Если `-o` не указан, файл создаётся автоматически по шаблону:

```
data/json/{datetime}_{tool}_{city}_{query}.json
```

Пример: `data/json/20260323_1430_orgscout_ufa_manicure.json`

- `{datetime}` — дата и время запуска (`YYYYMMDD_HHmm`), для сортировки по времени создания
- Кириллица транслитерируется (`Уфа` → `ufa`, `маникюр` → `manicure`)
- Если `-o` указан — используется как есть

---

## CLI

Единая точка входа: `webscout`.

```bash
webscout <tool> <command> [OPTIONS]
```

### Команды по инструментам

```bash
# ─── OrgScout: организации с карт ───
webscout org scrape yandex-maps --query "маникюр" --city "Уфа"
webscout org scrape 2gis --query "автосервис" --city "Казань"
webscout org fetch yandex-maps --org-url <url>
webscout org fetch 2gis --org-url <url>

# ─── JobScout: вакансии ───
webscout jobs search hh --query "администратор салона" --city "Уфа"
webscout jobs search avito --query "мастер маникюра" --city "Уфа"
webscout jobs enrich data/json/studios.json --source hh   # обогатить вакансиями

# ─── PriceScout: цены ───
webscout prices fetch yclients --url <url>
webscout prices collect data/json/studios.json             # обойти online_booking URL

# ─── ReviewScout: отзывы ───
webscout reviews scrape yandex --query "маникюр" --city "Уфа"
webscout reviews scrape flamp --org-name "Colorstar"
webscout reviews enrich data/json/studios.json --source yandex

# ─── LegalScout: юридические данные ───
webscout legal search egrul --name "ООО Колорстар" --city "Уфа"
webscout legal enrich data/json/studios.json --source egrul

# ─── Общие команды ───
webscout render <url>                                      # рендеринг произвольной SPA
webscout merge file1.json file2.json -o merged.json        # дедупликация и объединение
webscout pipeline research.yaml                            # запуск цепочки (будущее)
```

### Общие параметры (доступны для всех команд)

| Параметр | Короткий | Описание |
|----------|----------|---------|
| `--output` | `-o` | Путь к выходному файлу |
| `--format` | `-f` | Формат: `json` (по умолчанию), `ai-summary` |
| `--max-results` | `-n` | Лимит результатов |
| `--config` | `-c` | Путь к config.yaml |
| `--verbose` | `-v` | Подробный лог (построчно каждая запись) |
| `--csv` | | Дополнительно сохранить TSV рядом с основным JSON |
| `--append` | | Дозапуск: загрузить существующий файл, пропустить собранное, дописать новое |

---

## Общее ядро (`src/core/`)

### Browser Manager (`browser.py`)

Управление Playwright Chromium. Используется инструментами, которым нужен рендеринг SPA.

- Запуск headless/headed браузера
- Пул контекстов с настройкой viewport, locale, timezone
- Поддержка прокси
- Graceful shutdown

### HTTP Client (`http_client.py`)

Лёгкий HTTP-клиент для API, не требующих браузера (hh.ru, ЕГРЮЛ). На основе `httpx` (async).

- Единый интерфейс: `get_json(url, params)`, `get_text(url)`
- Retry с exponential backoff
- Rate limiting (не превышать лимиты API)
- Ротация User-Agent
- Поддержка прокси из общего конфига

### Anti-Detection (`anti_detect.py`)

- Рандомизация задержек между действиями
- Ротация user-agent из пула реальных браузеров
- Эмуляция человеческого скроллинга
- Обнаружение и ожидание капчи
- Retry с exponential backoff

### Renderer (`renderer.py`)

Рендеринг произвольных SPA-страниц. Общая команда `webscout render`.

- Открытие URL, ожидание загрузки
- Возврат HTML / plain text
- Network interception (перехват API-ответов)
- Ожидание конкретного CSS-селектора

## Вывод (`src/output/`)

### AI-summary (`ai_summary.py`)

Формат `ai-summary` — компактный текстовый отчёт, оптимизированный для вставки в промпт LLM (Claude, ChatGPT). Содержит ключевые факты без форматирования: количество записей, агрегации (средний рейтинг, разброс цен, топ-категории), аномалии. Цель — уместить суть данных в минимум токенов.

### Прогресс (`progress.py`)

Все долгие операции (scrape, enrich, collect) показывают rich progress bar в stderr (не мешает pipe/redirect). Формат: `Обработано 150/200 | Ошибки: 3 | ETA: ~2 мин`. Флаг `--verbose` добавляет построчный лог каждой записи.

---

### Базовые модели (`models.py`)

Общие модели данных, используемые несколькими инструментами:

```python
class Contacts(BaseModel):
    phone: list[str] = []
    email: str | None = None
    website: str | None = None
    telegram: str | None = None
    instagram: str | None = None
    vk: str | None = None
    whatsapp: str | None = None

class GeoPoint(BaseModel):
    lat: float
    lon: float

class ScrapedEntity(BaseModel):
    """Базовый класс для всех собираемых сущностей."""
    source: str               # yandex_maps, hh, flamp, egrul...
    source_url: str
    scraped_at: str            # ISO datetime
```

---

## Инструменты

### OrgScout — организации с карт

**Статус:** реализован (портируется из текущего проекта OrgScout).

**Источники:**
- Яндекс.Карты — DOM-парсинг + автоскролл
- 2ГИС — network interception (`catalog.api.2gis.ru`)
- Google Maps — опционально, на будущее

**Модель данных:**

```python
class Organization(ScrapedEntity):
    name: str
    type: str | None = None           # студия, салон, сеть, клиника
    address: str | list[str]
    geo: GeoPoint | None = None
    contacts: Contacts
    working_hours: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    categories: list[str] = []
    services: list[str] = []
    online_booking: str | None = None  # URL или CRM (YCLIENTS, Dikidi)
    photos: list[str] = []
    notes: str | None = None
```

**Команды:**
```bash
webscout org scrape yandex-maps --query <q> --city <city> [-n 50] [-f json]
webscout org scrape 2gis --query <q> --city <city> [-n 50] [-f json]
webscout org fetch yandex-maps --org-url <url>
webscout org fetch 2gis --org-url <url>
```

---

### JobScout — вакансии

**Источники:**

| Источник | Стратегия | Playwright нужен? |
|----------|----------|-------------------|
| hh.ru | Открытый REST API (`api.hh.ru`) | Нет, HTTP-клиент |
| Avito Работа | SPA, DOM-парсинг | Да |
| SuperJob | REST API (требует API-ключ) | Нет — **отложен, см. «Только открытые источники»** |

**Модель данных:**

```python
class Vacancy(ScrapedEntity):
    title: str                         # "Администратор салона красоты"
    employer: str                      # название компании
    employer_url: str | None = None    # ссылка на профиль работодателя
    city: str
    address: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str = "RUR"
    experience: str | None = None      # "от 1 года", "без опыта"
    employment: str | None = None      # полная, частичная, стажировка
    schedule: str | None = None        # полный день, сменный, гибкий
    description: str | None = None     # текст вакансии (краткий)
    skills: list[str] = []
    published_at: str | None = None    # ISO datetime публикации
    contacts: Contacts = Contacts()
```

**Команды:**
```bash
# Поиск вакансий
webscout jobs search hh --query "администратор салона" --city "Уфа" [-n 50]
webscout jobs search avito --query "мастер маникюра" --city "Уфа"

# Обогащение: взять организации из OrgScout → найти их вакансии
webscout jobs enrich data/json/studios.json --source hh
```

**Команда `enrich`:**
Принимает JSON-файл с организациями (результат OrgScout). Для каждой организации ищет вакансии через API по нормализованному названию с нечётким матчингом (rapidfuzz). Добавляет найденные совпадения в `_enriched.vacancies`. Сохраняет обогащённый файл.

**hh.ru API:**
- Эндпоинт: `GET https://api.hh.ru/vacancies?text=...&area=...`
- Не требует авторизации для поиска
- Rate limit: ~5 запросов/сек (уважаем)
- Справочник регионов: `GET https://api.hh.ru/areas`

---

### PriceScout — цены и прайсы

**Источники:**

| Источник | Стратегия | Описание |
|----------|----------|---------|
| YCLIENTS | SPA, Playwright | Виджет записи с прайсом |
| Dikidi | SPA, Playwright | Аналогично YCLIENTS |
| Сайты организаций | SPA/HTML, Playwright | Страницы «Услуги и цены» |

**Модель данных:**

```python
class ServicePrice(BaseModel):
    name: str                          # "Маникюр с покрытием гель-лак"
    price: int | None = None           # цена в рублях
    price_from: int | None = None      # "от 1500"
    price_to: int | None = None        # "до 2500"
    duration: str | None = None        # "60 мин"
    category: str | None = None        # "Маникюр", "Педикюр"

class PriceList(ScrapedEntity):
    org_name: str
    services: list[ServicePrice] = []
    currency: str = "RUB"
    fetched_from: str                  # URL откуда взят прайс
```

**Команды:**
```bash
# Прайс конкретной организации
webscout prices fetch yclients --url "https://yclients.com/company/12345"
webscout prices fetch dikidi --url "https://dikidi.net/salon/12345"

# Массовый сбор: обойти все online_booking URL из файла организаций
webscout prices collect data/json/studios.json
```

**Определение CRM в `collect`:**
Тип скрапера выбирается автоматически по домену URL из поля `online_booking`:
- `yclients.com` → scraper yclients
- `dikidi.net` → scraper dikidi
- Другие домены → пропуск (в логе: "неизвестный CRM, пропущено")

---

### ReviewScout — отзывы и репутация

**Источники:**

| Источник | Стратегия | Описание |
|----------|----------|---------|
| Яндекс.Отзывы | SPA, Playwright | Отзывы из карточки Яндекс.Карт |
| Flamp | SPA, Playwright | Агрегатор отзывов |
| Google Reviews | SPA, Playwright | Отзывы Google Maps |

**Модель данных:**

```python
class Review(BaseModel):
    author: str | None = None
    rating: int                        # 1-5
    text: str
    date: str | None = None            # ISO date
    response: str | None = None        # ответ организации

class ReviewSummary(ScrapedEntity):
    org_name: str
    avg_rating: float
    total_reviews: int
    reviews: list[Review] = []
    rating_distribution: dict[int, int] = {}  # {5: 120, 4: 30, ...}
```

**Команды:**
```bash
webscout reviews scrape yandex --query "маникюр" --city "Уфа"
webscout reviews scrape flamp --org-name "Colorstar" --city "Уфа"

# Обогащение организаций отзывами
webscout reviews enrich data/json/studios.json --source yandex
```

---

### LegalScout — юридические данные

**Источники:**

| Источник | Стратегия | Описание |
|----------|----------|---------|
| ЕГРЮЛ (nalog.ru) | HTTP / SPA | ИНН, ОГРН, дата регистрации, учредители |
| Rusprofile | SPA, Playwright | Финансы, суды, связи |

**Модель данных:**

```python
class LegalEntity(ScrapedEntity):
    name: str                          # полное наименование юрлица
    short_name: str | None = None
    inn: str
    ogrn: str | None = None
    registration_date: str | None = None
    address: str | None = None
    director: str | None = None
    founders: list[str] = []
    status: str | None = None          # действующее, ликвидировано
    main_activity: str | None = None   # основной ОКВЭД
    authorized_capital: int | None = None
    employee_count: str | None = None  # диапазон
```

**Команды:**
```bash
webscout legal search egrul --name "Колорстар" --city "Уфа"
webscout legal search egrul --inn "0277123456"

# Обогащение
webscout legal enrich data/json/studios.json --source egrul
```

---

## Обмен данными между инструментами

### Принцип: JSON-файлы как промежуточный формат

Каждый инструмент:
- **На выходе** — сохраняет JSON-массив с объектами своей модели
- **На входе (`enrich`)** — принимает JSON-файл другого инструмента, обогащает его

### Команда `enrich`

Паттерн обогащения — ключевая концепция. Инструмент читает JSON другого инструмента, для каждой записи ищет связанные данные и добавляет их.

```bash
# Шаг 1: Собрать организации
webscout org scrape yandex-maps --query "маникюр" --city "Уфа" -o data/json/studios.json

# Шаг 2: Добавить вакансии
webscout jobs enrich data/json/studios.json --source hh
# Результат: studios.json теперь содержит поле vacancies[] у каждой организации

# Шаг 3: Добавить прайсы
webscout prices collect data/json/studios.json
# Результат: studios.json теперь содержит поле price_list у организаций с online_booking

# Шаг 4: Добавить юрданные
webscout legal enrich data/json/studios.json --source egrul
# Результат: studios.json содержит поле legal_entity у найденных организаций
```

### Формат обогащённого файла

После enrich файл сохраняет исходную структуру, но каждый объект получает дополнительные поля:

```json
{
  "name": "Colorstar Nail Studio",
  "address": "ул. Ленина, 12",
  "contacts": { "phone": ["+79991234567"] },
  "rating": 4.8,
  "source": "yandex_maps",

  "_enriched": {
    "vacancies": [
      { "title": "Администратор", "salary_from": 35000, "source": "hh", "source_url": "..." }
    ],
    "price_list": {
      "services": [
        { "name": "Маникюр гель-лак", "price": 1500 }
      ],
      "fetched_from": "https://yclients.com/..."
    },
    "legal_entity": {
      "inn": "0277123456",
      "registration_date": "2019-05-15",
      "status": "действующее"
    }
  }
}
```

Все обогащённые данные хранятся в `_enriched` — не смешиваются с исходными данными инструмента.

### Матчинг при обогащении

Для связывания записей между источниками используется нечёткий матчинг (rapidfuzz). Названия нормализуются (убираются кавычки, организационно-правовые формы: ООО, ИП и т.п., приведение к нижнему регистру), затем сравниваются с порогом схожести. Матчинг дополнительно фильтруется по городу для снижения ложных срабатываний.

Пример: "Colorstar Nail Studio" (Яндекс.Карты) ↔ "ООО Колорстар" (hh.ru) — после нормализации "colorstar nail studio" vs "колорстар" → fuzzy match по подстроке.

### Повторный enrich

При повторном запуске `enrich` перезаписывается только соответствующий ключ в `_enriched`. Например, второй `jobs enrich` перезапишет `_enriched.vacancies`, но не тронет `_enriched.legal_entity`.

### Обработка ошибок и частичные результаты

При прерывании (ошибка сети, капча без решения, Ctrl+C) результат сохраняется с тем, что удалось собрать. Выводится сообщение: "Собрано N из M, результат сохранён в <файл>".

Для дозапуска используется флаг `--append`: команда загружает существующий файл, пропускает уже собранные записи (по `source_url`) и дописывает новые.

### Команда `merge` — дедупликация между источниками

```bash
webscout merge data/json/yandex_studios.json data/json/2gis_studios.json -o data/json/all_studios.json
```

Объединяет JSON-файлы из разных источников с дедупликацией. Дубли определяются по нечёткому матчингу названий + совпадению города/адреса. При конфликте данные мержатся: приоритет у записи с большим количеством заполненных полей.

---

## Конфигурация

Единый `config.yaml` в корне проекта:

```yaml
browser:
  headless: true
  viewport:
    width: 1920
    height: 1080
  locale: "ru-RU"
  timezone: "Asia/Yekaterinburg"
  rotate_user_agent: true

scraping:
  delay_min: 1.0
  delay_max: 3.0
  max_results: 500
  scroll_pause: 2.0
  page_load_timeout: 30
  retry_on_captcha: true
  captcha_timeout: 120

http:
  rate_limit: 5              # запросов в секунду (для API без браузера)
  timeout: 30
  retries: 3

proxy:
  enabled: false
  url: null                  # "http://user:pass@proxy:port"

output:
  format: json
  pretty: true
  include_photos: false
```

---

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.12+ |
| Браузер | Playwright (Chromium) |
| HTTP-клиент | httpx (async) |
| CLI | Typer |
| Модели данных | Pydantic v2 |
| Async | asyncio |
| Вывод | JSON, CSV (TSV), ai-summary |
| Нечёткий матчинг | rapidfuzz |
| Прогресс | rich (progress bar) |
| MCP | mcp (опционально) |
| Пакетный менеджер | uv или pip |

---

## Фазы разработки

### Фаза 0: Инициализация проекта
- [x] Создать структуру монорепозитория
- [x] Настроить pyproject.toml с единой точкой входа `webscout`
- [x] Портировать core из OrgScout: browser, anti_detect, renderer, config
- [x] Портировать output: json_writer, csv_writer, ai_summary
- [x] Progress bar (rich) для долгих операций (`output/progress.py`)
- [x] Автоименование выходных файлов (`{datetime}_{tool}_{city}_{query}.json`) + транслитерация
- [x] Обработка частичных результатов (сохранение при прерывании) и флаг `--append`
- [x] Корневой cli.py с подключением подкоманд
- [x] Портировать тесты core

> **Выполнено.** Создана полная структура монорепо: `src/core/` (config, models, browser,
> anti_detect, renderer, http_client), `src/output/` (json_writer, csv_writer, ai_summary,
> progress, naming, partial), `src/cli.py` (root CLI с командой `render`), `tests/` (152 теста,
> все проходят). Ключевые решения: output-модули обобщены до `BaseModel` (не привязаны к
> Organization); транслитерация кириллицы в `naming.py`; `http_client.py` добавлен в core
> (нужен в фазе 2); базовые модели `Contacts`, `GeoPoint`, `ScrapedEntity` в `core/models.py`.

### Фаза 1: OrgScout (порт)
- [x] Портировать scrapers: yandex_maps, twogis
- [x] Портировать модели: Organization, Contacts
- [x] CLI: `webscout org scrape ...`, `webscout org fetch ...`
- [x] Нечёткий матчинг (rapidfuzz) — core-утилита для merge и enrich
- [x] Команда `webscout merge` — объединение и дедупликация JSON из разных источников
- [x] Портировать тесты orgscout
- [x] Проверить что всё работает как раньше

> **Выполнено.** Созданы: `src/tools/orgscout/models.py` (Organization наследует ScrapedEntity),
> `src/tools/orgscout/scrapers/yandex_maps.py` (DOM-парсинг + автоскролл, helper `_extract_geo_from_url`),
> `src/tools/orgscout/scrapers/twogis.py` (перехват catalog.api.2gis.ru, публичная `parse_api_item` для тестирования),
> `src/tools/orgscout/cli.py` (scrape/fetch sub-apps, флаги --csv/--append/--verbose),
> `src/core/matching.py` (normalize_name, find_best_match, find_matches, deduplicate),
> команда `webscout merge` добавлена в корневой `cli.py`.
> Тесты: 230 проходят (78 новых). Ключевые решения: `parse_api_item` вынесена
> в module-level функцию (удобно тестировать без Playwright); `address: str | list[str]`
> сохранён по спеке; дедупликация фильтрует по городу для снижения false-positives.

### Фаза 2: JobScout
- [ ] Скрапер hh.ru (REST API, без Playwright)
- [ ] Модель Vacancy
- [ ] CLI: `webscout jobs search hh ...`
- [ ] Команда `webscout jobs enrich` — обогащение организаций вакансиями (fuzzy matching)
- [ ] Скрапер Avito (SPA, DOM-парсинг)
- [ ] Тесты
- _SuperJob отложен (требует API-ключ, см. «Только открытые источники»)_

### Фаза 3: PriceScout
- [ ] Скрапер YCLIENTS (Playwright, извлечение прайса из виджета записи)
- [ ] Скрапер Dikidi
- [ ] Автоопределение CRM по домену `online_booking` в команде `collect`
- [ ] Модели ServicePrice, PriceList
- [ ] CLI: `webscout prices fetch ...`, `webscout prices collect ...`
- [ ] Тесты

### Фаза 4: ReviewScout
- [ ] Скрапер Яндекс.Отзывов (из карточки организации)
- [ ] Скрапер Flamp
- [ ] Модели Review, ReviewSummary
- [ ] CLI: `webscout reviews scrape ...`, `webscout reviews enrich ...`
- [ ] Тесты

### Фаза 5: LegalScout
- [ ] Скрапер ЕГРЮЛ / nalog.ru
- [ ] Скрапер Rusprofile
- [ ] Модель LegalEntity
- [ ] CLI: `webscout legal search ...`, `webscout legal enrich ...`
- [ ] Тесты

### Фаза 6: Пайплайны и MCP
- [ ] Команда `webscout pipeline` — запуск цепочки из YAML-файла
- [ ] MCP-сервер со всеми инструментами
- [ ] Документация

---

## Пайплайны (фаза 6)

YAML-файл описывает цепочку шагов:

```yaml
# research.yaml — полное исследование рынка маникюра в Уфе
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

  - tool: legal
    command: enrich
    input: data/json/ufa_manicure.json
    source: egrul
```

Запуск:
```bash
webscout pipeline research.yaml
```

---

## Пример полного цикла исследования

```bash
# 1. Собрать маникюрные салоны Уфы
webscout org scrape yandex-maps --query "маникюр" --city "Уфа" -n 200 -o data/json/studios.json

# 2. Кто из них нанимает сотрудников?
webscout jobs enrich data/json/studios.json --source hh

# 3. Собрать прайсы у тех, кто использует YCLIENTS/Dikidi
webscout prices collect data/json/studios.json

# 4. Юридическая проверка
webscout legal enrich data/json/studios.json --source egrul

# 5. AI-анализ итогового файла
# Claude Code читает studios.json и получает полную картину:
# — 200 студий с контактами и рейтингами
# — 15 из них сейчас ищут администратора (растут)
# — средняя цена маникюра: 1200–2500 ₽
# — 3 студии зарегистрированы менее года назад (новички)
```

---

## MCP-сервер

Единый MCP-сервер предоставляет инструменты всех модулей:

| Инструмент MCP | Описание |
|---------------|---------|
| `scrape_organizations` | Поиск организаций (OrgScout) |
| `fetch_organization` | Карточка организации |
| `search_vacancies` | Поиск вакансий (JobScout) |
| `fetch_prices` | Прайс организации (PriceScout) |
| `scrape_reviews` | Отзывы (ReviewScout) |
| `search_legal` | Юрданные (LegalScout) |

---

## Антидетект и этика

### Меры антидетекта
- Рандомизированные задержки (1–5 сек) между действиями
- Ротация User-Agent из пула реальных браузеров
- Эмуляция viewport, locale, timezone
- Поддержка прокси для ротации IP
- Уважение rate limits API (hh.ru и др.)

### Капча
При обнаружении капчи: уведомление → пауза → ожидание ручного решения → продолжение.
Для ручного решения нужен `headless: false`.

### Этика
- Инструмент для исследования рынка и личного использования
- Задержки между запросами — уважение к серверам
- Используем открытые API где возможно (hh.ru) вместо скрапинга
- Не собираем персональные данные физических лиц
- Не обходим платные API, если они предоставляют те же данные

### Принцип: только открытые источники

На текущем этапе работаем только с данными, доступными без авторизации и API-ключей. Источники, требующие ключей (SuperJob и др.), будут добавлены в будущих фазах как отдельная задача.
