import asyncio
import logging
from typing import Any, Optional

import httpx

from fpx.classes.runner.subclasses._category import CategoryRunner
from fpx.classes.runner.subclasses._chat import ChatRunner
from fpx.classes.runner.subclasses._order import OrderRunner
from fpx.classes.runner.subclasses._purchase import PurchaseRunner
from fpx.classes.runner.subclasses._review import ReviewRunner
from fpx.classes.runner.subclasses.router import Router
from fpx.utils import errors as fpx_err

logger = logging.getLogger("fpx.runner")


class Runner:
    def __init__(self, account: Any) -> None:
        # account: Account (см. fpx/classes/account/account.py). Оставлен как Any,
        # так как типизация здесь через реальный класс Account создала бы
        # циклический импорт (Account -> Runner -> Account).
        self._account = account
        self._chat = ChatRunner(self)
        self._order = OrderRunner(self)
        self._review = ReviewRunner(self)
        self._category = CategoryRunner(self)
        self._purchase = PurchaseRunner(self)
        self.router = Router()
        self.storage: Optional[Any] = None
        self._cache: dict[str, list[Any]] = {
            "msgs": [],
            "old_msgs": [],
            "orders": [],
            "old_orders": [],
            "reviews": [],
            "old_reviews": [],
            "lot_categories": [],
            "old_lot_categories": [],
            "chip_categories": [],
            "old_chip_categories": [],
            "purchases": [],
            "old_purchases": [],
        }
        self._cache_is_updated = False
        self.is_running = True
        self._polling_task: asyncio.Task[None] | None = None
        self._polling_error_reported = False

    async def idle(self) -> None:
        """
        Зацикливает выполнение программы, чтобы фоновые задачи не закрылись.
        Если не использовать, код не будет работать.
        """
        while True:
            await asyncio.sleep(3600)

    async def _run_loop(
        self,
        timer: float,
        watch_lots: list[str | int] | None = None,
        watch_chips: list[str | int] | None = None,
    ) -> None:
        while self.is_running:
            try:
                await self._cache_runner(watch_lots, watch_chips)
                await asyncio.sleep(timer)
            except fpx_err.FpxRequestError:
                await asyncio.sleep(60)
            except fpx_err.FpxAccountError:
                await asyncio.sleep(5)
                continue
            except (httpx.HTTPError, httpx.NetworkError):
                await asyncio.sleep(timer)
            except Exception as e:
                critical = await self._report_critical_failure(e)
                if e is critical:
                    raise
                raise critical from e

    @property
    def polling_task(self) -> asyncio.Task[None] | None:
        """Фоновая задача polling, если `start_polling` запущен с `is_background=True`."""
        return self._polling_task

    async def start_polling(
        self,
        timer: float = 3,
        is_background: bool = True,
        watch_lots: list[str | int] | None = None,
        watch_chips: list[str | int] | None = None,
    ) -> Optional["asyncio.Task[None]"]:
        """
        Запускает поиск новых событий.

        Args:
            timer (str): Задержка в секундах, раз в которую будет происходить обновление кеша (рекомендуемо 3-5 сек).
            is_background (bool): По дефолту True(в фоне).
                Определяет, будет ли функция запущена в фоне
                или нет (если не в фоне, блокирует остальные процессы).
            watch_lots (list): Можно не передавать.
                Список категорий лотов, которые будет проверять скрипт.
            watch_chips (list): Можно не передавать.
                Список категорий чипсов(коротких лотов под валюты),
                которые будет проверять скрипт.

        Returns:
            asyncio.Task | None: Фоновая задача (сохраняется в `polling_task`)
                либо None, если polling запущен в текущей корутине.

        Note:
            Неизвестные ошибки оборачиваются в `FpxCriticalRunnerError`,
            прокидываются в `on_error` и логируются. Повторный вызов
            при уже работающей фоновой задаче возвращает её же.
        """
        if is_background and self._polling_task is not None and not self._polling_task.done():
            return self._polling_task

        self.is_running = True
        self._polling_error_reported = False
        if is_background:
            task = asyncio.create_task(
                self._run_loop(timer, watch_lots, watch_chips),
                name="fpx-polling",
            )
            self._polling_task = task
            task.add_done_callback(self._on_polling_done)
            return task
        await self._run_loop(timer, watch_lots, watch_chips)
        return None

    async def stop_polling(self) -> None:
        """Останавливает цикл polling и отменяет фоновую задачу, если она есть."""
        self.is_running = False
        task = self._polling_task
        if task is None:
            return
        if not task.done():
            task.cancel()
        try:
            await task
        except (asyncio.CancelledError, fpx_err.FpxCriticalRunnerError):
            pass
        except Exception:
            logger.exception("Ошибка при ожидании остановки polling")

    def _on_polling_done(self, task: asyncio.Task[None]) -> None:
        """Забирает исключение у фоновой задачи, чтобы оно не терялось в asyncio."""
        self.is_running = False
        if task.cancelled():
            logger.debug("Фоновая задача polling отменена")
            return
        exc = task.exception()
        if exc is not None and not self._polling_error_reported:
            logger.error(
                "Фоновая задача polling завершилась с необработанным исключением: %s",
                exc,
                exc_info=exc,
            )

    async def _report_critical_failure(self, exc: Exception) -> fpx_err.FpxCriticalRunnerError:
        """Логирует критический сбой и отдаёт его в on_error, затем возвращает обёртку."""
        self.is_running = False
        self._polling_error_reported = True
        logger.error("Критическая ошибка polling: %s", exc, exc_info=exc)
        if isinstance(exc, fpx_err.FpxCriticalRunnerError):
            critical = exc
        else:
            critical = fpx_err.FpxCriticalRunnerError(message=str(exc))
            critical.__cause__ = exc
        try:
            await self._handle_error(None, critical)
        except Exception:
            logger.exception("Не удалось прокинуть ошибку polling в on_error")
        return critical

    async def _warm_up(self, watch_lots: list[str | int] | None, watch_chips: list[str | int] | None) -> None:
        """Прогрев кеша"""
        await self._account.profile.get_user_data()
        tasks = []
        if watch_lots is not None:
            tasks.append(self._category._check_lot_categories(watch_lots))
        if watch_chips is not None:
            tasks.append(self._category._check_chip_categories(watch_chips))
        tasks.extend(
            [self._chat._update_chat_cache(), self._order._update_order_cache(), self._review._update_review_cache()]
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        is_good = True
        to_raise = None
        for result in results:
            if isinstance(result, Exception):
                await self._handle_error(None, result)
                if isinstance(result, (fpx_err.FpxRequestError, fpx_err.FpxAccountError)) and to_raise is None:
                    to_raise = result
                is_good = False
        if to_raise:
            raise to_raise
        if is_good:
            self._cache_is_updated = True
            for handler in self.router._handlers["startup"]:
                try:
                    await handler()
                except Exception as e:
                    await self._handle_error(None, e)
        else:
            self._cache_is_updated = False

    async def _cache_runner(self, watch_lots: list[str | int] | None, watch_chips: list[str | int] | None) -> None:
        """Управляет кешем"""
        if not self._cache_is_updated:
            await self._warm_up(watch_lots, watch_chips)
            return
        tasks = []
        if watch_lots is not None:
            tasks.append(self._category._check_lot_categories(watch_lots))
        if watch_chips is not None:
            tasks.append(self._category._check_chip_categories(watch_chips))
        tasks.extend(
            [
                self._chat._check_chats(),
                self._order._check_orders(),
                self._review._check_reviews(),
                self._purchase._check_purchases(),
            ]
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        to_raise = None
        for result in results:
            if isinstance(result, Exception):
                await self._handle_error(None, result)
                if isinstance(result, (fpx_err.FpxRequestError, fpx_err.FpxAccountError)) and to_raise is None:
                    to_raise = result
        if to_raise:
            raise to_raise

    async def _handle_error(self, event: Any, exception: Exception) -> None:
        """Централизованная обработка любых ошибок.
        event может быть Message, Order, Review или None.
        Советую проверять через if isinstanse(exception, fpx_err...)
        Ошибка в самом on_error-хендлере логируется и не валит цикл polling.
        """
        error_handlers = self.router._handlers.get("error", [])
        for handler in error_handlers:
            if not handler:
                continue
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, exception)
                else:
                    handler(event, exception)
            except Exception:
                logger.exception("Ошибка в on_error хендлере")
