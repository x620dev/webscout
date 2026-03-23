"""Тесты моделей JobScout."""

import pytest

from src.tools.jobscout.models import Vacancy


def test_vacancy_minimal():
    """Vacancy создаётся с обязательными полями."""
    v = Vacancy(source="hh", source_url="https://hh.ru/vacancy/1", title="Мастер маникюра")
    assert v.title == "Мастер маникюра"
    assert v.source == "hh"
    assert v.company_name is None
    assert v.salary_from is None


def test_vacancy_full():
    """Vacancy принимает все опциональные поля."""
    v = Vacancy(
        source="hh",
        source_url="https://hh.ru/vacancy/123",
        title="Мастер маникюра",
        company_name="Студия Colorstar",
        salary_from=40_000,
        salary_to=60_000,
        salary_currency="RUR",
        city="Уфа",
        address="ул. Ленина, 1",
        description="Обязанности: маникюр и педикюр",
        requirements="Опыт от 1 года",
        published_at="2026-03-01T10:00:00+0000",
        experience="1–3 года",
        employment="Полная занятость",
        schedule="Полный день",
    )
    assert v.company_name == "Студия Colorstar"
    assert v.salary_from == 40_000
    assert v.salary_to == 60_000
    assert v.salary_currency == "RUR"
    assert v.experience == "1–3 года"


def test_vacancy_scraped_at_auto():
    """scraped_at заполняется автоматически."""
    v = Vacancy(source="avito", source_url="https://avito.ru/1", title="Тест")
    assert v.scraped_at  # не пустая строка


def test_vacancy_model_dump():
    """model_dump возвращает корректный словарь."""
    v = Vacancy(
        source="hh",
        source_url="https://hh.ru/vacancy/1",
        title="Администратор",
        company_name="Nail Bar",
    )
    data = v.model_dump(mode="json")
    assert data["title"] == "Администратор"
    assert data["company_name"] == "Nail Bar"
    assert "scraped_at" in data
