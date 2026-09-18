import asyncio
import logging
from typing import Any

from fpx.fsm import FSMContext
from fpx.models.account import Purchase
from fpx.utils.order_status import OrderStatusKind, classify_order_status

logger = logging.getLogger("fpx.purchase_runner")


class PurchaseRunner:
    def __init__(self, runner: Any) -> None:
        # runner: Runner (см. fpx/classes/runner/runner.py). Оставлен как Any,
        # так как сам класс Runner ещё не аннотирован (отдельная задача #17).
        self.runner = runner

    async def _update_purchase_cache(self) -> None:
        """
        Обновляет кеш покупок в раннере
        """
        orders = await self.runner._account.purchase.get_my_purchases(100)
        result = []
        for order in orders:
            o = {
                "order_id": order.order_id,
                "order_time": order.order_time,
                "client_name": order.client_name,
                "price": order.price,
                "name": order.name,
                "status": order.status,
            }
            result.append(o)
        if self.runner._cache["old_purchases"] == []:
            self.runner._cache["old_purchases"] = result
        else:
            self.runner._cache["old_purchases"] = self.runner._cache["purchases"]
        self.runner._cache["purchases"] = result

    def _compare_purchase_cache(self) -> list[Purchase]:
        """
        Сравнивает старый и новый кеш покупок
        """
        result: list[Purchase] = []
        if self.runner._cache["purchases"] != self.runner._cache["old_purchases"]:
            for order in self.runner._cache["purchases"]:
                if order not in self.runner._cache["old_purchases"]:
                    result.append(Purchase(**order))
        return result

    async def _check_handler(self, handler: dict[str, Any], order: Purchase, state_ctx: FSMContext | None) -> bool:
        h_func = handler["function"]
        if handler.get("mapping") is not None:
            msg_text = order.description.lower() if order.description else ""
            matched = False
            for trigger in handler["mapping"]:
                if trigger.lower() in msg_text:
                    order.finded_mapping = trigger
                    matched = True
                    break
            if not matched:
                return False
        await self.runner.router.invoke(h_func, order, state_ctx)
        return True

    async def _trigger_order_handlers(self, order: Purchase) -> None:
        state_ctx = FSMContext(self.runner.storage, order.chat_id) if order.chat_id else None
        kind = classify_order_status(order.status)
        for handler in self.runner.router._handlers["purchase"]:
            if await self._check_handler(handler, order, state_ctx):
                pass
        if kind is OrderStatusKind.CLOSED:
            for handler in self.runner.router._handlers["confirmed_purchase"]:
                if await self._check_handler(handler, order, state_ctx):
                    pass
        elif kind is OrderStatusKind.PAID:
            for handler in self.runner.router._handlers["new_purchase"]:
                if await self._check_handler(handler, order, state_ctx):
                    pass
        elif kind is OrderStatusKind.REFUNDED:
            for handler in self.runner.router._handlers["purchase_refund"]:
                if await self._check_handler(handler, order, state_ctx):
                    pass

    async def _process_single_purchase(self, order: Purchase) -> None:
        try:
            order_info = await self.runner._account.order.get_order_details(order.order_id)
            order.description = order_info.description
            order.chat_id = order_info.chat_id
            order._client = self.runner
            await self._trigger_order_handlers(order)
        except Exception as e:
            logger.debug(f"В процессе обработки заказа произошла ошибка: {e}. Убедитесь что всё хорошо", exc_info=True)
            await self.runner._handle_error(event=order, exception=e)

    async def _check_purchases(self) -> None:
        await self._update_purchase_cache()
        orders = self._compare_purchase_cache()
        if orders:
            tasks = [self._process_single_purchase(order) for order in orders]
            await asyncio.gather(*tasks)
