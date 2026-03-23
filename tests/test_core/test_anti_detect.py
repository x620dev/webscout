"""Тесты для модуля антидетекта (anti_detect)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.anti_detect import (
    _CAPTCHA_KEYWORDS,
    _USER_AGENTS,
    detect_captcha,
    get_random_user_agent,
    human_scroll,
    random_delay,
    wait_for_captcha_solve,
    with_retry,
)


# ─────────────────────────────────────────────────────────────────────────────
# random_delay
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_random_delay_zero():
    """random_delay с нулевыми значениями не падает."""
    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await random_delay(0.0, 0.0)
        mock_sleep.assert_called_once_with(0.0)


@pytest.mark.asyncio
async def test_random_delay_equal():
    """random_delay с min==max использует фиксированное значение."""
    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await random_delay(1.5, 1.5)
        mock_sleep.assert_called_once_with(1.5)


@pytest.mark.asyncio
async def test_random_delay_range():
    """random_delay вызывает sleep со значением в диапазоне [min, max]."""
    recorded: list[float] = []

    async def fake_sleep(secs: float) -> None:
        recorded.append(secs)

    with patch("src.core.anti_detect.asyncio.sleep", side_effect=fake_sleep):
        await random_delay(1.0, 3.0)

    assert len(recorded) == 1
    assert 1.0 <= recorded[0] <= 3.0


@pytest.mark.asyncio
async def test_random_delay_max_less_than_min():
    """random_delay когда max < min использует min."""
    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await random_delay(2.0, 1.0)
        mock_sleep.assert_called_once_with(2.0)


# ─────────────────────────────────────────────────────────────────────────────
# get_random_user_agent
# ─────────────────────────────────────────────────────────────────────────────


def test_get_random_user_agent_is_string():
    """get_random_user_agent возвращает строку."""
    ua = get_random_user_agent()
    assert isinstance(ua, str)
    assert len(ua) > 0


def test_get_random_user_agent_from_pool():
    """get_random_user_agent возвращает значение из пула."""
    ua = get_random_user_agent()
    assert ua in _USER_AGENTS


def test_get_random_user_agent_variety():
    """get_random_user_agent иногда возвращает разные значения (статистически)."""
    agents = {get_random_user_agent() for _ in range(50)}
    # При 50 попытках из 8 агентов вероятность получить только 1 уникальный ≈ 0
    assert len(agents) > 1


def test_user_agents_pool_not_empty():
    """Пул user-agent не пустой."""
    assert len(_USER_AGENTS) > 0


def test_user_agents_contain_mozilla():
    """Все user-agent содержат 'Mozilla' (реальные браузерные UA)."""
    for ua in _USER_AGENTS:
        assert "Mozilla" in ua


# ─────────────────────────────────────────────────────────────────────────────
# human_scroll
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_human_scroll_calls_evaluate():
    """human_scroll вызывает page.evaluate для прокрутки."""
    page = AsyncMock()
    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock):
        await human_scroll(page, distance=600, variance=0)
    assert page.evaluate.call_count >= 1


@pytest.mark.asyncio
async def test_human_scroll_uses_scroll_by():
    """human_scroll использует window.scrollBy в JavaScript."""
    page = AsyncMock()
    calls: list[str] = []

    async def capture_evaluate(js: str) -> None:
        calls.append(js)

    page.evaluate = capture_evaluate

    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock):
        await human_scroll(page, distance=300, variance=0)

    assert all("scrollBy" in c for c in calls)


# ─────────────────────────────────────────────────────────────────────────────
# detect_captcha
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_captcha_no_captcha():
    """detect_captcha возвращает False для обычной страницы."""
    page = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Обычная страница</body></html>")
    result = await detect_captcha(page)
    assert result is False


@pytest.mark.asyncio
@pytest.mark.parametrize("keyword", _CAPTCHA_KEYWORDS)
async def test_detect_captcha_finds_keywords(keyword: str):
    """detect_captcha обнаруживает страницы с ключевыми словами капчи."""
    page = AsyncMock()
    page.content = AsyncMock(return_value=f"<html><body>Пожалуйста, {keyword}.</body></html>")
    result = await detect_captcha(page)
    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_case_insensitive():
    """detect_captcha нечувствителен к регистру."""
    page = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Please CAPTCHA</body></html>")
    result = await detect_captcha(page)
    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_exception_returns_false():
    """detect_captcha возвращает False при ошибке чтения контента."""
    page = AsyncMock()
    page.content = AsyncMock(side_effect=RuntimeError("page closed"))
    result = await detect_captcha(page)
    assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# wait_for_captcha_solve
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_for_captcha_solve_no_captcha():
    """wait_for_captcha_solve возвращает True если капчи нет сразу."""
    page = AsyncMock()
    page.content = AsyncMock(return_value="<html>Чистая страница</html>")
    page.url = "https://example.com"

    notified = []
    result = await wait_for_captcha_solve(
        page,
        timeout_sec=10,
        check_interval=0.1,
        notify_callback=lambda: notified.append(True),
    )
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_captcha_solve_resolved_after_poll():
    """wait_for_captcha_solve возвращает True когда капча исчезла после опроса."""
    page = AsyncMock()
    page.url = "https://example.com"

    call_count = 0

    async def content_side_effect() -> str:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return "<html>please captcha here</html>"
        return "<html>Чистая страница</html>"

    page.content = content_side_effect

    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock):
        result = await wait_for_captcha_solve(
            page,
            timeout_sec=60,
            check_interval=0.1,
            notify_callback=lambda: None,
        )
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_captcha_solve_timeout():
    """wait_for_captcha_solve возвращает False при истечении таймаута."""
    page = AsyncMock()
    page.url = "https://example.com"
    page.content = AsyncMock(return_value="<html>captcha is here</html>")

    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock):
        result = await wait_for_captcha_solve(
            page,
            timeout_sec=2,
            check_interval=5,  # check_interval > timeout_sec → сразу 1 итерация
            notify_callback=lambda: None,
        )
    assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# with_retry
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_with_retry_success_first_attempt():
    """with_retry возвращает результат при успехе первой попытки."""
    async def func(x: int) -> int:
        return x * 2

    result = await with_retry(func, 5, max_attempts=3)
    assert result == 10


@pytest.mark.asyncio
async def test_with_retry_success_after_failures():
    """with_retry повторяет вызов и возвращает результат после успешной попытки."""
    call_count = 0

    async def flaky() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("временная ошибка")
        return "ok"

    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(flaky, max_attempts=3, base_delay=0.1)

    assert result == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_with_retry_raises_after_all_attempts():
    """with_retry пробрасывает исключение после исчерпания попыток."""
    async def always_fail() -> None:
        raise ValueError("всегда ошибка")

    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ValueError, match="всегда ошибка"):
            await with_retry(always_fail, max_attempts=3, base_delay=0.1)


@pytest.mark.asyncio
async def test_with_retry_correct_attempt_count():
    """with_retry делает ровно max_attempts попыток при постоянных ошибках."""
    call_count = 0

    async def counter() -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("ошибка")

    with patch("src.core.anti_detect.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RuntimeError):
            await with_retry(counter, max_attempts=4, base_delay=0.1)

    assert call_count == 4


@pytest.mark.asyncio
async def test_with_retry_backoff_increases_delay():
    """with_retry увеличивает задержку с каждой попыткой (exponential backoff)."""
    recorded_delays: list[float] = []

    async def fake_sleep(secs: float) -> None:
        recorded_delays.append(secs)

    async def always_fail() -> None:
        raise RuntimeError()

    with patch("src.core.anti_detect.asyncio.sleep", side_effect=fake_sleep):
        with pytest.raises(RuntimeError):
            await with_retry(always_fail, max_attempts=3, base_delay=1.0, backoff=2.0)

    # 2 паузы между 3 попытками: 1.0 и 2.0
    assert len(recorded_delays) == 2
    assert recorded_delays[0] == pytest.approx(1.0)
    assert recorded_delays[1] == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_with_retry_passes_kwargs():
    """with_retry корректно передаёт именованные аргументы."""
    async def func(a: int, b: str = "default") -> str:
        return f"{a}-{b}"

    result = await with_retry(func, 42, max_attempts=1, b="custom")
    assert result == "42-custom"
