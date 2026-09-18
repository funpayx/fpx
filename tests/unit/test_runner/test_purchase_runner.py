"""Тесты PurchaseRunner — кеш покупок, диспетчинг по статусам, триггерные команды."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.runner.subclasses._purchase import PurchaseRunner
from fpx.classes.runner.subclasses.router import Router
from fpx.models.account import Purchase


def make_purchase(**overrides):
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
    r._cache = {"purchases": [], "old_purchases": []}
    r.router = Router()
    r.storage = MagicMock()
    r._handle_error = AsyncMock()
    return r


@pytest.fixture
def purchase_runner(runner):
    return PurchaseRunner(runner)


class TestUpdatePurchaseCache:
    @pytest.mark.asyncio
    async def test_first_call_sets_old_purchases_equal_to_new(self, purchase_runner, runner):
        # На самом первом обновлении (old_purchases == []) старый кеш не
        # переносится из purchases, а сразу приравнивается к свежему result -
        # чтобы при старте раннера уже существующие покупки не считались "новыми".
        order = make_purchase()
        runner._account.purchase.get_my_purchases = AsyncMock(return_value=[order])
        assert runner._cache["old_purchases"] == []
        await purchase_runner._update_purchase_cache()
        assert runner._cache["old_purchases"] == runner._cache["purchases"]
        assert runner._cache["purchases"][0]["order_id"] == "1"
        runner._account.purchase.get_my_purchases.assert_awaited_once_with(100)

    @pytest.mark.asyncio
    async def test_subsequent_call_moves_old_cache_and_builds_new(self, purchase_runner, runner):
        order = make_purchase()
        runner._account.purchase.get_my_purchases = AsyncMock(return_value=[order])
        runner._cache["old_purchases"] = [{"existing": True}]
        runner._cache["purchases"] = [{"previous": True}]
        await purchase_runner._update_purchase_cache()
        assert runner._cache["old_purchases"] == [{"previous": True}]
        assert runner._cache["purchases"][0]["order_id"] == "1"
        runner._account.purchase.get_my_purchases.assert_awaited_once_with(100)


class TestComparePurchaseCache:
    def test_no_change_returns_empty(self, purchase_runner, runner):
        order_dict = {
            "order_id": "1",
            "order_time": None,
            "client_name": None,
            "price": None,
            "name": None,
            "status": None,
        }
        runner._cache["purchases"] = runner._cache["old_purchases"] = [order_dict]
        assert purchase_runner._compare_purchase_cache() == []

    def test_new_order_detected(self, purchase_runner, runner):
        order_dict = {
            "order_id": "1",
            "order_time": None,
            "client_name": None,
            "price": None,
            "name": None,
            "status": None,
        }
        runner._cache["old_purchases"] = []
        runner._cache["purchases"] = [order_dict]
        result = purchase_runner._compare_purchase_cache()
        assert len(result) == 1
        assert isinstance(result[0], Purchase)
        assert result[0].order_id == "1"


class TestCheckHandler:
    @pytest.mark.asyncio
    async def test_no_mapping_always_invokes(self, purchase_runner, runner):
        called = []

        async def func(order: Purchase):
            called.append(order)

        handler = {"function": func, "mapping": None}
        order = Purchase(order_id="1", description="описание")
        result = await purchase_runner._check_handler(handler, order, None)
        assert result is True
        assert called == [order]

    @pytest.mark.asyncio
    async def test_mapping_matches_sets_finded_mapping(self, purchase_runner, runner):
        called = []

        async def func(order: Purchase):
            called.append(order)

        handler = {"function": func, "mapping": ["VIP"]}
        order = Purchase(order_id="1", description="Заказ VIP статус")
        result = await purchase_runner._check_handler(handler, order, None)
        assert result is True
        assert order.finded_mapping == "VIP"

    @pytest.mark.asyncio
    async def test_mapping_no_match_returns_false(self, purchase_runner, runner):
        async def func(order: Purchase):
            pass

        handler = {"function": func, "mapping": ["VIP"]}
        order = Purchase(order_id="1", description="Обычный заказ")
        result = await purchase_runner._check_handler(handler, order, None)
        assert result is False


class TestTriggerOrderHandlers:
    @pytest.mark.asyncio
    async def test_closed_status_triggers_confirmed_purchase_handlers(self, purchase_runner, runner):
        called = []

        @runner.router.on_confirmed_purchases()
        async def handler(order: Purchase):
            called.append(order)

        order = Purchase(order_id="1", status="Закрыт")
        await purchase_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_paid_status_triggers_new_purchase_handlers(self, purchase_runner, runner):
        called = []

        @runner.router.on_new_purchase()
        async def handler(order: Purchase):
            called.append(order)

        order = Purchase(order_id="1", status="Оплачен")
        await purchase_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_refund_status_triggers_refund_handlers(self, purchase_runner, runner):
        called = []

        @runner.router.on_refunded_purchase()
        async def handler(order: Purchase):
            called.append(order)

        order = Purchase(order_id="1", status="Возврат")
        await purchase_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.parametrize(
        "status",
        ["Refunded", "refund", "Повернення", "Order #ABC / Refunded", "Заказ #123 / Возврат"],
    )
    @pytest.mark.asyncio
    async def test_refund_locales_trigger_refund_handlers(self, purchase_runner, runner, status):
        called = []

        @runner.router.on_refunded_purchase()
        async def handler(order: Purchase):
            called.append(order)

        order = Purchase(order_id="1", status=status)
        await purchase_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.parametrize("status", ["Paid", "Відкрито", "Order #ABC / Paid"])
    @pytest.mark.asyncio
    async def test_paid_locales_trigger_new_purchase_handlers(self, purchase_runner, runner, status):
        called = []

        @runner.router.on_new_purchase()
        async def handler(order: Purchase):
            called.append(order)

        order = Purchase(order_id="1", status=status)
        await purchase_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.parametrize("status", ["Closed", "Закрито", "Order #ABC / Closed"])
    @pytest.mark.asyncio
    async def test_closed_locales_trigger_confirmed_purchase_handlers(self, purchase_runner, runner, status):
        called = []

        @runner.router.on_confirmed_purchases()
        async def handler(order: Purchase):
            called.append(order)

        order = Purchase(order_id="1", status=status)
        await purchase_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_on_purchases_always_triggered_regardless_of_status(self, purchase_runner, runner):
        called = []

        @runner.router.on_purchases()
        async def handler(order: Purchase):
            called.append(order)

        order = Purchase(order_id="1", status="какой-то другой статус")
        await purchase_runner._trigger_order_handlers(order)
        assert called == [order]

    @pytest.mark.asyncio
    async def test_none_status_does_not_crash(self, purchase_runner, runner):
        order = Purchase(order_id="1", status=None)
        await purchase_runner._trigger_order_handlers(order)


class TestProcessSinglePurchase:
    @pytest.mark.asyncio
    async def test_success_enriches_and_dispatches(self, purchase_runner, runner):
        order_info = MagicMock(description="описание", chat_id="chat-1")
        runner._account.order.get_order_details = AsyncMock(return_value=order_info)
        order = Purchase(order_id="1", status="Оплачен")
        await purchase_runner._process_single_purchase(order)
        assert order.description == "описание"
        assert order.chat_id == "chat-1"
        assert order._client is runner

    @pytest.mark.asyncio
    async def test_exception_is_handled_gracefully(self, purchase_runner, runner):
        runner._account.order.get_order_details = AsyncMock(side_effect=Exception("boom"))
        order = Purchase(order_id="1", status="Оплачен")
        await purchase_runner._process_single_purchase(order)
        runner._handle_error.assert_awaited_once()


class TestCheckPurchases:
    @pytest.mark.asyncio
    async def test_no_new_purchases_no_processing(self, purchase_runner, runner):
        runner._account.purchase.get_my_purchases = AsyncMock(return_value=[])
        await purchase_runner._check_purchases()

    @pytest.mark.asyncio
    async def test_processes_all_new_purchases(self, purchase_runner, runner):
        order = make_purchase(order_id="99")
        runner._account.purchase.get_my_purchases = AsyncMock(return_value=[order])
        order_info = MagicMock(description="d", chat_id="c")
        runner._account.order.get_order_details = AsyncMock(return_value=order_info)
        runner._cache["old_purchases"] = [{"dummy": True}]
        await purchase_runner._check_purchases()
        runner._account.order.get_order_details.assert_awaited_once_with("99")
