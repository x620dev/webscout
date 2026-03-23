"""Нечёткий матчинг названий организаций — общая core-утилита для merge и enrich."""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

# Юридические формы для удаления при нормализации
_LEGAL_FORMS = re.compile(
    r"\b(ооо|ао|пао|зао|оао|ип|фгуп|мбу|гуп|нко|тд|тоо|сп|кп|фгбу|фку)\b",
    re.IGNORECASE,
)
_QUOTES = re.compile(r'["\'\u00ab\u00bb\u201e\u201c]')  # «», "", „"
_NON_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Нормализовать название организации для нечёткого сравнения.

    Убирает кавычки, организационно-правовые формы (ООО, ИП, и т.п.),
    знаки пунктуации и приводит к нижнему регистру.

    Examples:
        >>> normalize_name('ООО "Колорстар"')
        'колорстар'
        >>> normalize_name('ИП Иванов И.И.')
        'иванов ии'
        >>> normalize_name('Colorstar Nail Studio')
        'colorstar nail studio'
    """
    text = _QUOTES.sub("", name)
    text = _LEGAL_FORMS.sub("", text)
    text = _NON_WORD.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text.lower()


def find_best_match(
    query: str,
    candidates: list[str],
    threshold: float = 70.0,
) -> tuple[int, float] | None:
    """Найти наилучшее совпадение для запроса среди кандидатов.

    Использует ``fuzz.token_set_ratio`` — устойчив к перестановке слов
    и различию в длине строк (например, «Colorstar» vs «Colorstar Nail Studio»).

    Args:
        query: Нормализованное название для поиска.
        candidates: Нормализованные названия-кандидаты.
        threshold: Минимальный порог схожести (0–100).

    Returns:
        Кортеж ``(индекс_кандидата, score)`` или ``None`` если нет совпадения.

    Examples:
        >>> find_best_match("colorstar", ["kolорстар", "colorstar nail studio"])
        (1, 100.0)
    """
    if not candidates:
        return None

    result = process.extractOne(
        query,
        candidates,
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold,
    )
    if result is None:
        return None

    _value, score, index = result
    return index, float(score)


def find_matches(
    query: str,
    candidates: list[str],
    threshold: float = 70.0,
    limit: int = 5,
) -> list[tuple[int, float]]:
    """Найти несколько совпадений для запроса среди кандидатов.

    Args:
        query: Нормализованное название.
        candidates: Нормализованные кандидаты.
        threshold: Минимальный порог схожести.
        limit: Максимальное число результатов.

    Returns:
        Список ``(индекс, score)`` отсортированный по убыванию score.
    """
    results = process.extract(
        query,
        candidates,
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold,
        limit=limit,
    )
    return [(index, float(score)) for _value, score, index in results]


def deduplicate(
    records: list[dict],
    name_key: str = "name",
    city_key: str = "city",
    threshold: float = 80.0,
) -> list[dict]:
    """Дедуплицировать список записей по нечёткому совпадению названий.

    При обнаружении дублей сохраняется запись с большим числом заполненных полей.
    Дополнительный фильтр по городу снижает число ложных срабатываний.

    Args:
        records: Список словарей с данными организаций.
        name_key: Ключ поля с названием организации.
        city_key: Ключ поля с городом (None-значения игнорируются).
        threshold: Порог схожести для определения дублей.

    Returns:
        Список записей без дублей.
    """
    if not records:
        return []

    # Нормализованные названия для сравнения
    norm_names = [normalize_name(r.get(name_key, "") or "") for r in records]
    kept: list[int] = []      # индексы записей, которые мы оставляем
    merged_into: dict[int, int] = {}  # i → j: запись i дублирует kept[j]

    for i, record in enumerate(records):
        query_name = norm_names[i]
        query_city = (record.get(city_key) or "").lower().strip()

        found_dup = False
        for j in kept:
            if j == i:
                continue
            # Фильтр по городу: если оба поля заполнены и города не совпадают — пропуск
            kept_city = (records[j].get(city_key) or "").lower().strip()
            if query_city and kept_city and query_city != kept_city:
                continue

            score = fuzz.token_set_ratio(query_name, norm_names[j])
            if score >= threshold:
                # Дублируется: выбираем запись с большим числом заполненных полей
                if _filled_count(record) > _filled_count(records[j]):
                    kept[kept.index(j)] = i
                merged_into[i] = j
                found_dup = True
                break

        if not found_dup:
            kept.append(i)

    return [records[i] for i in kept]


def _filled_count(record: dict) -> int:
    """Подсчитать число непустых полей в записи."""
    count = 0
    for v in record.values():
        if v is None or v == "" or v == [] or v == {}:
            continue
        count += 1
    return count
