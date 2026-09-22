import asyncio
import logging
from typing import Any

from fpx.fsm import FSMContext
from fpx.models.account import Order
from fpx.utils.order_status import OrderStatusKind, classify_order_status

logger = logging.getLogger("fpx.order_runner")


class OrderRunner:
    def __init__(self, runner: Any) -> None:
        # runner: Runner (см. fpx/classes/runner/runner.py). Оставлен как Any,
        # так как сам класс Runner ещё не аннотирован (отдельная задача #17).
        self.runner = runner

    async def _update_order_cache(self) -> None:
        """
        Обновляет кеш заказов в раннере
        """
        orders = await self.runner._account.profile.get_my_sells(100)
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
        self.runner._cache["old_orders"] = self.runner._cache["orders"]
        self.runner._cache["orders"] = result

    def _compare_order_cache(self) -> list[Order]:
        """
        Сравнивает старый и новый кеш заказов
        """
        result: list[Order] = []
        if self.runner._cache["orders"] != self.runner._cache["old_orders"]:
            for order in self.runner._cache["orders"]:
                if order not in self.runner._cache["old_orders"]:
                    result.append(Order(**order))
        return result

    async def _check_handler(self, handler: dict[str, Any], order: Order, state_ctx: FSMContext | None) -> bool:
        h_func = handler["function"]
        if handler.get("mapping") is not None:
            if order.description is None:
                return False
            msg_text = order.description.lower()
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

    async def _check_trigger_for_command(self, order: Order, state_ctx: FSMContext | None) -> bool:
        if order.description is None:
            return False
        for cmd_handler in self.runner.router._handlers["order_command"]:
            target_command = cmd_handler["trigger_command"]
            target_command_lower = {k.lower(): v for k, v in target_command.items()}
            target_function = None
            for command_name in target_command_lower:
                if command_name in order.description.lower():
                    target_function = target_command_lower[command_name]
                    order.finded_mapping = command_name
                    break
            if target_function is None:
                continue
            await self.runner.router.invoke(target_function, order, state_ctx)
            return True
        return False

    async def _trigger_order_handlers(self, order: Order) -> None:
        state_ctx = FSMContext(self.runner.storage, order.chat_id) if order.chat_id else None
        kind = classify_order_status(order.status)
        for handler in self.runner.router._handlers["order"]:
            if await self._check_handler(handler, order, state_ctx):
                pass
        if kind is OrderStatusKind.CLOSED:
            for handler in self.runner.router._handlers["confirmed_order"]:
                if await self._check_handler(handler, order, state_ctx):
                    pass
        elif kind is OrderStatusKind.PAID:
            for handler in self.runner.router._handlers["new_order"]:
                if await self._check_handler(handler, order, state_ctx):
                    pass
            if await self._check_trigger_for_command(order, state_ctx):
                pass
        elif kind is OrderStatusKind.REFUNDED:
            for handler in self.runner.router._handlers["refund"]:
                if await self._check_handler(handler, order, state_ctx):
                    pass

    async def _process_single_order(self, order: Order) -> None:
        try:
            order_info = await self.runner._account.order.get_order_details(order.order_id)
            order.description = order_info.description
            order.chat_id = order_info.chat_id
            order._client = self.runner
            await self._trigger_order_handlers(order)
        except Exception as e:
            logger.debug(f"В процессе обработки заказа произошла ошибка: {e}. Убедитесь что всё хорошо", exc_info=True)
            await self.runner._handle_error(event=order, exception=e)

    async def _check_orders(self) -> None:
        await self._update_order_cache()
        orders = self._compare_order_cache()
        if orders:
            tasks = [self._process_single_order(order) for order in orders]
            await asyncio.gather(*tasks)
