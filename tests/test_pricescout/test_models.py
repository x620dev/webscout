"""Тесты моделей PriceScout."""

import pytest

from src.tools.pricescout.models import PriceList, ServicePrice


def test_service_price_minimal():
    """ServicePrice создаётся с обязательным полем name."""
    s = ServicePrice(name="Маникюр без покрытия")
    assert s.name == "Маникюр без покрытия"
    assert s.price is None
    assert s.price_from is None
    assert s.price_to is None
    assert s.duration is None
    assert s.category is None


def test_service_price_full():
    """ServicePrice принимает все поля."""
    s = ServicePrice(
        name="Маникюр с покрытием гель-лак",
        price=None,
        price_from=1_500,
        price_to=2_500,
        duration="60 мин",
        category="Маникюр",
    )
    assert s.price_from == 1_500
    assert s.price_to == 2_500
    assert s.duration == "60 мин"
    assert s.category == "Маникюр"


def test_service_price_exact_price():
    """ServicePrice с точной ценой."""
    s = ServicePrice(name="Стрижка", price=800)
    assert s.price == 800
    assert s.price_from is None
    assert s.price_to is None


def test_price_list_minimal():
    """PriceList создаётся с обязательными полями."""
    pl = PriceList(
        source="yclients",
        source_url="https://yclients.com/company/123/",
        fetched_from="https://yclients.com/company/123/",
        org_name="Студия Colorstar",
    )
    assert pl.org_name == "Студия Colorstar"
    assert pl.services == []
    assert pl.currency == "RUB"
    assert pl.source == "yclients"


def test_price_list_with_services():
    """PriceList хранит список услуг."""
    services = [
        ServicePrice(name="Маникюр", price=800, category="Маникюр"),
        ServicePrice(name="Педикюр", price=1_200, category="Педикюр"),
    ]
    pl = PriceList(
        source="dikidi",
        source_url="https://dikidi.net/salon/456",
        fetched_from="https://dikidi.net/salon/456",
        org_name="Nail Bar",
        services=services,
    )
    assert len(pl.services) == 2
    assert pl.services[0].name == "Маникюр"
    assert pl.services[1].price == 1_200


def test_price_list_scraped_at_auto():
    """scraped_at заполняется автоматически."""
    pl = PriceList(
        source="yclients",
        source_url="https://yclients.com/company/1/",
        fetched_from="https://yclients.com/company/1/",
        org_name="Тест",
    )
    assert pl.scraped_at  # не пустая строка


def test_price_list_model_dump():
    """model_dump возвращает корректный словарь."""
    pl = PriceList(
        source="yclients",
        source_url="https://yclients.com/company/1/",
        fetched_from="https://yclients.com/company/1/",
        org_name="Студия",
        services=[ServicePrice(name="Маникюр", price=800)],
    )
    data = pl.model_dump(mode="json")
    assert data["org_name"] == "Студия"
    assert data["currency"] == "RUB"
    assert len(data["services"]) == 1
    assert data["services"][0]["name"] == "Маникюр"
    assert "scraped_at" in data
