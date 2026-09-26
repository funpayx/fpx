"""Тесты OrderRunner — кеш заказов, диспетчинг по статусам, триггерные команды."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.runner.subclasses._order import OrderRunner
from fpx.classes.runner.subclasses.router import Router
from fpx.models.account import Order
from fpx.utils import errors as fpx_err


def make_order(**overrides):
    defaults = dict(
        order_id="1",
        order_time="10:00",
        client_name="Bob",
        price=100.0,
        name="Товар",
        status="Оплачен",
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


@pytest.fixture
def runner():
    r = MagicMock()
    r._cache = {"orders": [], "old_orders": []}
    r.router = Router()
    r.storage = MagicMock()
    r._handle_error = AsyncMock()
    return r


@pytest.fixture
def order_runner(runner):
    return OrderRunner(runner)


class TestUpdateOrderCache:
    @pytest.mark.asyncio
    async def test_moves_old_cache_and_builds_new(self, order_runner, runner):
        order = make_order()
        runner._account.profile.get_my_sells = AsyncMock(return_value=[order])
        runner._cache["orders"] = [{"existing": True}]
        await order_runner._update_order_cache()
        assert runner._cache["old_orders"] == [{"existing": True}]
        assert runner._cache["orders"][0]["order_id"] == "1"
        runner._account.profile.get_my_sells.assert_awaited_once_with(100)


class TestCompareOrderCache:
    def test_no_change_returns_empty(self, order_runner, runner):
        order_dict = {
            "order_id": "1",
            "order_time": None,
            "client_name": None,
            "price": None,
            "name": None,
            "status": None,
        }
        runner._cache["orders"] = runner._cache["old_orders"] = [order_dict]
        assert order_runner._compare_order_cache() == []

    def test_new_order_detected(self, order_runner, runner):
        order_dict = {
            "order_id": "1",
            "order_time": None,
            "client_name": None,
            "price": None,
            "name": None,
            "status": None,
        }
        runner._cache["old_orders"] = []
        runner._cache["orders"] = [order_dict]
        result = order_runner._compare_order_cache()
        assert len(result) == 1
        assert isinstance(result[0], Order)
        assert result[0].order_id == "1"


class TestCheckHandler:
    @pytest.mark.asyncio
    async def test_no_mapping_always_invokes(self, order_runner, runner):
        called = []

        async def func(order: Order):
            called.append(order)

        handler = {"function": func, "mapping": None}
        order = Order(order_id="1", description="описание")
        result = await order_runner._check_handler(handler, order, None)
        assert result is True
        assert called == [order]

    @pytest.mark.asyncio
    async def test_mapping_matches_sets_finded_mapping(self, order_runner, runner):
        called = []

        async def func(order: Order):
            called.append(order)

        handler = {"function": func, "mapping": ["VIP"]}
        order = Order(order_id="1", description="Заказ VIP статус")
        result = await order_runner._check_handler(handler, order, None)
        assert result is True
        assert order.finded_mapping == "VIP"

    @pytest.mark.asyncio
    async def test_mapping_no_match_returns_false(self, order_runner, runner):
        async def func(order: Order):
            pass

        handler = {"function": func, "mapping": ["VIP"]}
        order = Order(order_id="1", description="Обычный заказ")
        result = await order_runner._check_handler(handler, order, None)
        assert result is False

    @pytest.mark.asyncio
    async def test_mapping_none_description_returns_false(self, order_runner, runner):
        called = []

        async def func(order: Order):
            called.append(order)

        handler = {"function": func, "mapping": ["VIP"]}
        order = Order(order_id="1", description=None)
        result = await order_runner._check_handler(handler, order, None)
        assert result is False
        assert called == []

    @pytest.mark.asyncio
    async def test_no_mapping_invokes_when_description_is_none(self, order_runner, runner):
        called = []

        async def func(order: Order):
            called.append(order)

        handler = {"function": func, "mapping": None}
        order = Order(order_id="1", description=None)
        result = await order_runner._check_handler(handler, order, None)
        assert result is True
        assert called == [order]


class TestCheckTriggerForCommand:
    @pytest.mark.asyncio
    async def test_no_description_returns_false(self, order_runner, runner):
        order = Order(order_id="1", description=None)
        assert await order_runner._check_trigger_for_command(order, None) is False

    @pytest.mark.asyncio
    async def test_matching_command_invoked(self, order_runner, runner):
        called = []

        async def func(order: Order):
            called.append(order)

        runner.router._handlers["order_command"] = [{"trigger_command": {"моя метка": func}}]
        order = Order(order_id="1", description="описание с моя метка внутри")
        result = await order_runner._check_trigger_for_command(order, None)
        assert result is True
        assert called == [order]
        assert order.finded_mapping == "моя метка"

    @pytest.mark.asyncio
    async def test_no_matching_command_returns_false(self, order_runner, runner):
        async def func(order: Order):
            pass

        runner.router._handlers["order_command"] = [{"trigger_command": {"другая метка": func}}]
        order = Order(order_id="1", description="описание")
        assert await order_runner._check_trigger_for_command(order, None) is False


class TestTriggerOrderHandlers:
    @pytest.mark.asyncio
    async def test_closed_status_triggers_confirmed_order_handlers(self, order_runner, runner):
        called = []

        @runner.router.on_confirmed_orders()
        async def handler(order: Order):
            called.append(order)

        order = Order(order_id="1", status="Закрыт")
        await order_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_paid_status_triggers_new_order_handlers(self, order_runner, runner):
        called = []

        @runner.router.on_new_order()
        async def handler(order: Order):
            called.append(order)

        order = Order(order_id="1", status="Оплачен")
        await order_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_refund_status_triggers_refund_handlers(self, order_runner, runner):
        called = []

        @runner.router.on_refunded_orders()
        async def handler(order: Order):
            called.append(order)

        order = Order(order_id="1", status="Возврат")
        await order_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.parametrize(
        "status",
        ["Refunded", "refund", "Повернення", "Order #ABC / Refunded", "Заказ #123 / Возврат"],
    )
    @pytest.mark.asyncio
    async def test_refund_locales_trigger_refund_handlers(self, order_runner, runner, status):
        called = []

        @runner.router.on_refunded_orders()
        async def handler(order: Order):
            called.append(order)

        order = Order(order_id="1", status=status)
        await order_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.parametrize("status", ["Paid", "Відкрито", "Order #ABC / Paid"])
    @pytest.mark.asyncio
    async def test_paid_locales_trigger_new_order_handlers(self, order_runner, runner, status):
        called = []

        @runner.router.on_new_order()
        async def handler(order: Order):
            called.append(order)

        order = Order(order_id="1", status=status)
        await order_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.parametrize("status", ["Closed", "Закрито", "Order #ABC / Closed"])
    @pytest.mark.asyncio
    async def test_closed_locales_trigger_confirmed_order_handlers(self, order_runner, runner, status):
        called = []

        @runner.router.on_confirmed_orders()
        async def handler(order: Order):
            called.append(order)

        order = Order(order_id="1", status=status)
        await order_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_refunded_does_not_trigger_paid_or_closed(self, order_runner, runner):
        paid, closed, refunded = [], [], []

        @runner.router.on_new_order()
        async def on_paid(order: Order):
            paid.append(order)

        @runner.router.on_confirmed_orders()
        async def on_closed(order: Order):
            closed.append(order)

        @runner.router.on_refunded_orders()
        async def on_refund(order: Order):
            refunded.append(order)

        order = Order(order_id="1", status="Refunded")
        await order_runner._trigger_order_handlers(order)
        assert paid == []
        assert closed == []
        assert refunded == [order]

    @pytest.mark.asyncio
    async def test_on_orders_always_triggered_regardless_of_status(self, order_runner, runner):
        called = []

        @runner.router.on_orders()
        async def handler(order: Order):
            called.append(order)

        order = Order(order_id="1", status="какой-то другой статус")
        await order_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_none_status_does_not_crash(self, order_runner, runner):
        order = Order(order_id="1", status=None)
        await order_runner._trigger_order_handlers(order)


class TestProcessSingleOrder:
    @pytest.mark.asyncio
    async def test_success_enriches_and_dispatches(self, order_runner, runner):
        order_info = MagicMock(description="описание", chat_id="chat-1")
        runner._account.order.get_order_details = AsyncMock(return_value=order_info)
        order = Order(order_id="1", status="Оплачен")
        await order_runner._process_single_order(order)
        assert order.description == "описание"
        assert order.chat_id == "chat-1"
        assert order._client is runner

    @pytest.mark.asyncio
    async def test_exception_is_handled_gracefully(self, order_runner, runner):
        runner._account.order.get_order_details = AsyncMock(side_effect=Exception("boom"))
        order = Order(order_id="1", status="Оплачен")
        await order_runner._process_single_order(order)
        runner._handle_error.assert_awaited_once()


class TestCheckOrders:
    @pytest.mark.asyncio
    async def test_no_new_orders_no_processing(self, order_runner, runner):
        runner._account.profile.get_my_sells = AsyncMock(return_value=[])
        await order_runner._check_orders()

    @pytest.mark.asyncio
    async def test_processes_all_new_orders(self, order_runner, runner):
        order = make_order(order_id="99")
        runner._account.profile.get_my_sells = AsyncMock(return_value=[order])
        order_info = MagicMock(description="d", chat_id="c")
        runner._account.order.get_order_details = AsyncMock(return_value=order_info)
        await order_runner._check_orders()
        runner._account.order.get_order_details.assert_awaited_once_with("99")


def make_sell(order_id, status, date="Сегодня, 12:00"):
    """Строка продажи в том виде, в котором её отдаёт parse_my_sells."""
    return {
        "order-id": order_id,
        "order-time": date,
        "client-name": "Bob",
        "price": 100.0,
        "name": "Товар",
        "status": status,
        "category": "Roblox",
        "amount": 1,
        "topup_data": None,
    }


def cached(order_id, status, date="Сегодня, 12:00"):
    sell = make_sell(order_id, status, date)
    return {
        "order_id": order_id,
        "order_time": date,
        "client_name": sell["client-name"],
        "price": sell["price"],
        "name": sell["name"],
        "status": status,
    }


class TestOrderPage:
    """Первая страница продаж: так раннер /runner/ сверяет заказы по сигналу FunPay."""

    @pytest.mark.asyncio
    async def test_update_builds_cache_from_first_page_only(self, order_runner, runner):
        runner._account._client.get_my_sells = AsyncMock(return_value="<html>")
        runner._account._parser.parse_my_sells = MagicMock(
            return_value={"sells": [make_sell("A1", "Оплачен")], "next_page": "NEXT"}
        )
        runner._account._client.get_next_sells = AsyncMock()
        runner._cache["orders"] = [cached("OLD", "Закрыт")]
        await order_runner._update_order_page_cache()
        assert runner._cache["old_orders"] == [cached("OLD", "Закрыт")]
        assert runner._cache["orders"] == [cached("A1", "Оплачен")]
        runner._account._client.get_next_sells.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_wraps_errors(self, order_runner, runner):
        runner._account._client.get_my_sells = AsyncMock(return_value="<html>")
        runner._account._parser.parse_my_sells = MagicMock(side_effect=fpx_err.FpxNullDataError("пусто"))
        with pytest.raises(fpx_err.FpxGetUserSellsError):
            await order_runner._update_order_page_cache()

    def test_compare_reports_new_orders_and_status_changes_only(self, order_runner, runner):
        runner._cache["old_orders"] = [cached("A1", "Оплачен", "Сегодня, 23:59"), cached("A2", "Оплачен")]
        runner._cache["orders"] = [
            cached("A3", "Оплачен"),
            cached("A1", "Оплачен", "Вчера, 23:59"),
            cached("A2", "Закрыт"),
        ]
        result = order_runner._compare_order_statuses()
        assert [(order.order_id, order.status) for order in result] == [("A3", "Оплачен"), ("A2", "Закрыт")]
        assert all(isinstance(order, Order) for order in result)

    @pytest.mark.asyncio
    async def test_check_processes_changed_orders(self, order_runner, runner):
        runner._cache["orders"] = [cached("A1", "Оплачен")]
        runner._account._client.get_my_sells = AsyncMock(return_value="<html>")
        runner._account._parser.parse_my_sells = MagicMock(
            return_value={"sells": [make_sell("A2", "Оплачен"), make_sell("A1", "Оплачен")]}
        )
        order_runner._process_single_order = AsyncMock()
        await order_runner._check_order_page()
        processed = [call.args[0].order_id for call in order_runner._process_single_order.await_args_list]
        assert processed == ["A2"]
