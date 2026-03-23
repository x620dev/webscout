"""Антидетект — рандомизация задержек, ротация user-agent, обработка капчи, retry."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Callable

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Пул реальных user-agent строк (Chrome/Firefox последних версий)
_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
]

# Ключевые слова для обнаружения страниц-капч
_CAPTCHA_KEYWORDS: list[str] = [
    "captcha",
    "capcha",
    "recaptcha",
    "i am not a robot",
    "я не робот",
    "роботов",
    "подтвердите, что вы",
    "проверка безопасности",
    "access denied",
    "robot check",
]


async def random_delay(min_sec: float, max_sec: float) -> None:
    """Случайная задержка в диапазоне [min_sec, max_sec] секунд.

    Используется вместо фиксированной задержки для имитации реального пользователя.
    """
    if max_sec <= min_sec:
        await asyncio.sleep(min_sec)
        return
    delay = random.uniform(min_sec, max_sec)
    logger.debug("Задержка: %.2f сек", delay)
    await asyncio.sleep(delay)


def get_random_user_agent() -> str:
    """Вернуть случайный user-agent из пула реальных браузеров."""
    return random.choice(_USER_AGENTS)


async def human_scroll(
    page: Page,
    distance: int = 600,
    variance: int = 200,
    pause_min: float = 0.05,
    pause_max: float = 0.3,
) -> None:
    """Имитировать человеческую прокрутку: несколько шагов с мини-паузами.

    Args:
        page: Playwright страница.
        distance: Средняя дистанция прокрутки (пикселей).
        variance: Случайное отклонение ±variance пикселей.
        pause_min: Минимальная пауза между шагами (сек).
        pause_max: Максимальная пауза между шагами (сек).
    """
    actual = distance + random.randint(-variance, variance)
    steps = random.randint(2, 5)
    step_size = max(1, actual // steps)
    for _ in range(steps):
        await page.evaluate(f"window.scrollBy(0, {step_size})")
        await asyncio.sleep(random.uniform(pause_min, pause_max))


async def detect_captcha(page: Page) -> bool:
    """Проверить, отображается ли на странице капча.

    Ищет ключевые слова в HTML-контенте страницы.

    Returns:
        True если капча обнаружена.
    """
    try:
        content = (await page.content()).lower()
        return any(kw in content for kw in _CAPTCHA_KEYWORDS)
    except Exception as exc:
        logger.debug("Ошибка при проверке капчи: %s", exc)
        return False


async def wait_for_captcha_solve(
    page: Page,
    timeout_sec: int = 120,
    check_interval: float = 5.0,
    notify_callback: Callable[[], None] | None = None,
) -> bool:
    """Дождаться решения капчи пользователем.

    Уведомляет пользователя и периодически проверяет страницу до исчезновения капчи.
    Требует запуска браузера с headless=false чтобы пользователь мог решить капчу.

    Args:
        page: Playwright страница с капчей.
        timeout_sec: Максимальное время ожидания (сек).
        check_interval: Интервал проверки (сек).
        notify_callback: Функция уведомления. По умолчанию — вывод в stdout.

    Returns:
        True если капча решена, False если превышен таймаут.
    """
    if notify_callback:
        notify_callback()
    else:
        print(
            "\n⚠️  КАПЧА ОБНАРУЖЕНА!\n"
            "Пожалуйста, решите капчу вручную в браузере.\n"
            f"Ожидание до {timeout_sec} секунд...",
            flush=True,
        )
    logger.warning("Капча обнаружена. URL: %s", page.url)

    elapsed = 0.0
    while elapsed < timeout_sec:
        if not await detect_captcha(page):
            logger.info("Капча решена, продолжаем. URL: %s", page.url)
            return True
        await asyncio.sleep(check_interval)
        elapsed += check_interval

    logger.error("Таймаут ожидания капчи (%d сек). URL: %s", timeout_sec, page.url)
    return False


async def with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    backoff: float = 2.0,
    **kwargs: Any,
) -> Any:
    """Выполнить async-функцию с повторными попытками при ошибках.

    Args:
        func: Асинхронная функция для вызова.
        *args: Позиционные аргументы.
        max_attempts: Максимальное число попыток.
        base_delay: Базовая задержка перед первым повтором (сек).
        backoff: Множитель задержки при каждом следующем retry.
        **kwargs: Именованные аргументы.

    Returns:
        Результат функции.

    Raises:
        Exception: Последнее исключение если все попытки не удались.
    """
    last_exc: Exception | None = None
    delay = base_delay

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                logger.warning(
                    "Попытка %d/%d не удалась (%s). Повтор через %.1f сек...",
                    attempt,
                    max_attempts,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= backoff
            else:
                logger.error(
                    "Все %d попытки не удались. Ошибка: %s",
                    max_attempts,
                    exc,
                )

    raise last_exc  # type: ignore[misc]
