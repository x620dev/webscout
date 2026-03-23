"""Тесты моделей ReviewScout."""

import pytest

from src.tools.reviewscout.models import Review, ReviewSummary


def test_review_minimal():
    """Review создаётся с минимальными полями."""
    r = Review(author="Иван Иванов", text="Отличный салон!")
    assert r.author == "Иван Иванов"
    assert r.text == "Отличный салон!"
    assert r.rating is None
    assert r.date is None
    assert r.platform is None


def test_review_full():
    """Review принимает все поля."""
    r = Review(
        author="Мария",
        rating=4.5,
        text="Хороший мастер, рекомендую.",
        date="2024-03-15",
        platform="yandex",
    )
    assert r.rating == 4.5
    assert r.date == "2024-03-15"
    assert r.platform == "yandex"


def test_review_all_optional():
    """Review можно создать без полей вообще."""
    r = Review()
    assert r.author is None
    assert r.text is None
    assert r.rating is None


def test_review_summary_minimal():
    """ReviewSummary создаётся с обязательными полями."""
    s = ReviewSummary(
        source="yandex",
        source_url="https://yandex.ru/maps/org/salon/123456789/",
        org_name="Студия Colorstar",
    )
    assert s.org_name == "Студия Colorstar"
    assert s.reviews == []
    assert s.rating is None
    assert s.reviews_count is None
    assert s.source == "yandex"


def test_review_summary_with_reviews():
    """ReviewSummary хранит список отзывов."""
    reviews = [
        Review(author="Иван", rating=5.0, text="Отлично!"),
        Review(author="Мария", rating=4.0, text="Хорошо"),
    ]
    s = ReviewSummary(
        source="flamp",
        source_url="https://ufa.flamp.ru/firm/salon-123",
        org_name="Nail Bar",
        rating=4.5,
        reviews_count=42,
        reviews=reviews,
    )
    assert len(s.reviews) == 2
    assert s.reviews[0].author == "Иван"
    assert s.reviews[1].rating == 4.0
    assert s.rating == 4.5
    assert s.reviews_count == 42


def test_review_summary_scraped_at_auto():
    """scraped_at заполняется автоматически."""
    s = ReviewSummary(
        source="yandex",
        source_url="https://yandex.ru/maps/org/salon/1/",
        org_name="Тест",
    )
    assert s.scraped_at


def test_review_summary_model_dump():
    """model_dump возвращает корректный словарь."""
    s = ReviewSummary(
        source="yandex",
        source_url="https://yandex.ru/maps/org/salon/1/",
        org_name="Студия",
        rating=4.8,
        reviews=[Review(author="Анна", rating=5.0, text="Супер!")],
    )
    data = s.model_dump(mode="json")
    assert data["org_name"] == "Студия"
    assert data["rating"] == 4.8
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["author"] == "Анна"
    assert "scraped_at" in data
