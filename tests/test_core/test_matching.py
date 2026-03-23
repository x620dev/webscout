"""Тесты для core/matching.py — нечёткий матчинг и дедупликация."""

import pytest

from src.core.matching import (
    _filled_count,
    deduplicate,
    find_best_match,
    find_matches,
    normalize_name,
)


# ─── normalize_name ───────────────────────────────────────────────────────────


def test_normalize_removes_legal_forms():
    """Убирает ООО, ИП и другие юр. формы."""
    assert normalize_name('ООО "Колорстар"') == "колорстар"
    assert normalize_name("ИП Иванов") == "иванов"
    assert normalize_name("ЗАО Авторитет") == "авторитет"
    assert normalize_name("ПАО Сбербанк") == "сбербанк"


def test_normalize_removes_quotes():
    """Убирает кавычки разных типов."""
    assert normalize_name('"Студия"') == "студия"
    assert normalize_name("«Маникюр»") == "маникюр"
    assert normalize_name("\u201eColorstar\u201c") == "colorstar"


def test_normalize_lowercases():
    """Приводит к нижнему регистру."""
    assert normalize_name("Colorstar Nail Studio") == "colorstar nail studio"
    assert normalize_name("СТУДИЯ МАНИКЮРА") == "студия маникюра"


def test_normalize_removes_punctuation():
    """Убирает знаки пунктуации."""
    result = normalize_name("ИП Иванов И.И.")
    assert "." not in result
    assert "иванов" in result


def test_normalize_empty_string():
    """Не падает на пустой строке."""
    assert normalize_name("") == ""


def test_normalize_only_legal_form():
    """Если только юр. форма — возвращает пустую строку."""
    assert normalize_name("ООО") == ""


def test_normalize_preserves_latin():
    """Латинские символы не изменяются."""
    assert normalize_name("Colorstar") == "colorstar"


# ─── find_best_match ──────────────────────────────────────────────────────────


def test_find_best_match_exact():
    """Находит точное совпадение."""
    result = find_best_match("colorstar", ["другое", "colorstar", "третье"])
    assert result is not None
    idx, score = result
    assert idx == 1
    assert score == pytest.approx(100.0)


def test_find_best_match_partial():
    """Находит частичное совпадение (colorstar vs colorstar nail studio)."""
    result = find_best_match("colorstar", ["colorstar nail studio"])
    assert result is not None
    idx, score = result
    assert idx == 0
    assert score >= 70.0


def test_find_best_match_below_threshold():
    """Возвращает None если совпадение ниже порога."""
    result = find_best_match("маникюр", ["педикюр", "стрижка"], threshold=80.0)
    assert result is None


def test_find_best_match_empty_candidates():
    """Возвращает None для пустого списка кандидатов."""
    assert find_best_match("тест", []) is None


def test_find_best_match_cyrillic():
    """Работает с кириллицей."""
    result = find_best_match("колорстар", ["другое", "колорстар студия", "что-то"])
    assert result is not None
    assert result[1] >= 70.0


def test_find_best_match_custom_threshold():
    """Учитывает кастомный порог."""
    # С низким порогом — находит частичное совпадение
    r1 = find_best_match("nail", ["nail art studio красоты"], threshold=30.0)
    assert r1 is not None
    # С очень высоким порогом — полностью разные строки не совпадают
    r2 = find_best_match("маникюр", ["парикмахерская"], threshold=95.0)
    assert r2 is None


# ─── find_matches ─────────────────────────────────────────────────────────────


def test_find_matches_returns_list():
    """find_matches возвращает список совпадений."""
    candidates = ["colorstar", "colorstar nail", "что-то другое"]
    results = find_matches("colorstar", candidates, threshold=70.0)
    assert isinstance(results, list)
    assert len(results) >= 1


def test_find_matches_sorted_by_score():
    """Результаты отсортированы по убыванию score."""
    candidates = ["colorstar nail studio ufa", "colorstar", "колорстар"]
    results = find_matches("colorstar", candidates, threshold=50.0)
    if len(results) > 1:
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)


def test_find_matches_limit():
    """Не превышает limit результатов."""
    candidates = [f"студия {i}" for i in range(20)]
    results = find_matches("студия", candidates, threshold=50.0, limit=3)
    assert len(results) <= 3


def test_find_matches_empty_candidates():
    """Возвращает пустой список для пустых кандидатов."""
    assert find_matches("тест", []) == []


# ─── deduplicate ──────────────────────────────────────────────────────────────


def test_deduplicate_removes_exact_duplicates():
    """Дедупликация убирает точные дубли по названию."""
    records = [
        {"name": "Colorstar", "city": "Уфа"},
        {"name": "Colorstar", "city": "Уфа"},
        {"name": "Другая студия", "city": "Уфа"},
    ]
    result = deduplicate(records, threshold=90.0)
    assert len(result) == 2


def test_deduplicate_removes_fuzzy_duplicates():
    """Дедупликация убирает нечёткие дубли."""
    records = [
        {"name": "Colorstar Nail Studio", "city": "Уфа"},
        {"name": "Colorstar", "city": "Уфа"},
    ]
    result = deduplicate(records, threshold=80.0)
    assert len(result) == 1


def test_deduplicate_different_cities_kept():
    """Записи из разных городов не считаются дублями."""
    records = [
        {"name": "Colorstar", "city": "Уфа"},
        {"name": "Colorstar", "city": "Казань"},
    ]
    result = deduplicate(records, threshold=90.0, city_key="city")
    assert len(result) == 2


def test_deduplicate_empty_list():
    """Пустой список возвращается без изменений."""
    assert deduplicate([]) == []


def test_deduplicate_single_record():
    """Один элемент остаётся без изменений."""
    records = [{"name": "Студия", "city": "Уфа"}]
    assert len(deduplicate(records)) == 1


def test_deduplicate_keeps_richer_record():
    """При дубле оставляется запись с большим числом заполненных полей."""
    records = [
        {"name": "Colorstar", "city": "Уфа", "phone": None, "website": None},
        {"name": "Colorstar", "city": "Уфа", "phone": "+79991234567", "website": "https://ex.com"},
    ]
    result = deduplicate(records, threshold=90.0)
    assert len(result) == 1
    assert result[0].get("phone") == "+79991234567"


def test_deduplicate_no_city_field():
    """Дедупликация работает если поле city отсутствует."""
    records = [
        {"name": "Студия"},
        {"name": "Студия"},
    ]
    result = deduplicate(records, threshold=90.0)
    assert len(result) == 1


# ─── _filled_count ────────────────────────────────────────────────────────────


def test_filled_count_empty():
    """Пустая запись даёт 0."""
    assert _filled_count({}) == 0


def test_filled_count_with_nones():
    """None-значения не считаются заполненными."""
    assert _filled_count({"a": None, "b": "", "c": [], "d": {}}) == 0


def test_filled_count_filled():
    """Заполненные значения считаются."""
    assert _filled_count({"a": "значение", "b": 42, "c": [1, 2]}) == 3
