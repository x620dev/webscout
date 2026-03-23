"""Тесты для модуля автоименования (naming.py)."""

import re
from pathlib import Path

import pytest

from src.output.naming import auto_path, slugify, transliterate


# ─────────────────────────────────────────────────────────────────────────────
# transliterate
# ─────────────────────────────────────────────────────────────────────────────


def test_transliterate_city():
    """Транслитерация города."""
    assert transliterate("Уфа") == "ufa"


def test_transliterate_query():
    """Транслитерация запроса."""
    assert transliterate("маникюр") == "manikyur"


def test_transliterate_uppercase():
    """Заглавные кириллические буквы также транслитерируются."""
    assert transliterate("Москва") == "moskva"


def test_transliterate_latin_unchanged():
    """Латинские символы не изменяются."""
    assert transliterate("hello") == "hello"


def test_transliterate_mixed():
    """Смешанный текст."""
    result = transliterate("hello мир")
    assert "hello" in result
    assert "mir" in result


def test_transliterate_special_chars():
    """Специальные кириллические буквы (ё, ж, ш и т.п.)."""
    assert "yo" in transliterate("ёж")
    assert "zh" in transliterate("жара")
    assert "sh" in transliterate("шина")
    assert "ch" in transliterate("чай")
    assert "yu" in transliterate("юмор")
    assert "ya" in transliterate("яма")


def test_transliterate_soft_hard_signs():
    """Мягкий и твёрдый знак превращаются в пустую строку (без разделителя)."""
    assert transliterate("объект") == "obekt"  # ъ → ''
    assert transliterate("деньги") == "dengi"  # ь → ''


# ─────────────────────────────────────────────────────────────────────────────
# slugify
# ─────────────────────────────────────────────────────────────────────────────


def test_slugify_cyrillic():
    """slugify транслитерирует кириллицу."""
    assert slugify("Уфа") == "ufa"


def test_slugify_spaces_to_underscore():
    """Пробелы заменяются на подчёркивания."""
    result = slugify("маникюр и педикюр")
    assert " " not in result
    assert "_" in result


def test_slugify_latin_only_chars():
    """Только буквы, цифры и подчёркивания."""
    result = slugify("маникюр «эксклюзив»")
    assert re.match(r"^[a-z0-9_]+$", result)


def test_slugify_no_leading_trailing_underscores():
    """Нет подчёркиваний в начале и конце."""
    result = slugify("  маникюр  ")
    assert not result.startswith("_")
    assert not result.endswith("_")


def test_slugify_digits_preserved():
    """Цифры сохраняются."""
    assert "2025" in slugify("студия 2025")


# ─────────────────────────────────────────────────────────────────────────────
# auto_path
# ─────────────────────────────────────────────────────────────────────────────


def test_auto_path_returns_path():
    """auto_path возвращает Path."""
    result = auto_path("orgscout", "Уфа", "маникюр")
    assert isinstance(result, Path)


def test_auto_path_json_format():
    """JSON формат → data/json/*.json."""
    result = auto_path("orgscout", "Уфа", "маникюр", fmt="json")
    assert result.parent.parent.name == "data"
    assert result.parent.name == "json"
    assert result.suffix == ".json"


def test_auto_path_csv_format():
    """CSV формат → data/csv/*.tsv."""
    result = auto_path("orgscout", "Уфа", "маникюр", fmt="csv")
    assert result.parent.name == "csv"
    assert result.suffix == ".tsv"


def test_auto_path_ai_format():
    """AI-summary формат → data/ai/*.md."""
    result = auto_path("orgscout", "Уфа", "маникюр", fmt="ai-summary")
    assert result.parent.name == "ai"
    assert result.suffix == ".md"


def test_auto_path_contains_tool():
    """Путь содержит название инструмента."""
    result = auto_path("orgscout", "Уфа", "маникюр")
    assert "orgscout" in result.name


def test_auto_path_contains_transliterated_city():
    """Путь содержит транслитерированный город."""
    result = auto_path("orgscout", "Уфа", "маникюр")
    assert "ufa" in result.name


def test_auto_path_contains_transliterated_query():
    """Путь содержит транслитерированный запрос."""
    result = auto_path("orgscout", "Уфа", "маникюр")
    assert "manikyur" in result.name


def test_auto_path_contains_timestamp():
    """Путь содержит временную метку формата YYYYMMDD_HHMM."""
    result = auto_path("orgscout", "Уфа", "маникюр")
    assert re.search(r"\d{8}_\d{4}", result.name)
