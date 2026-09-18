"""Тесты OrderManager — детали заказа, поиск по имени, возврат."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.account.subclasses.order import OrderManager
from fpx.models.account import Order
from fpx.utils import errors as fpx_err


@pytest.fixture
def account():
    acc = MagicMock()
    acc._client.get_order_info = AsyncMock()
    acc._client.refund_order = AsyncMock()
    acc._parser.parse_order_page = MagicMock()
    acc.profile.get_my_sells = AsyncMock()
    return acc


@pytest.fixture
def manager(account):
    return OrderManager(account)


class TestGetOrderDetails:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account._client.get_order_info.return_value = "<html></html>"
        account._parser.parse_order_page.return_value = {
            "status": "Оплачен",
            "review": {"text": "", "stars": 0, "answer": ""},
            "desc": "Описание",
            "chat_id": "chat-1",
        }
        result = await manager.get_order_details("order-1")
        assert isinstance(result, Order)
        assert result.status == "Оплачен"
        assert result.chat_id == "chat-1"

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_order_info.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetOrderInfoError):
            await manager.get_order_details("order-1")


def make_order(**overrides):
    defaults = dict(
        order_id="1",
        client_name="Bob",
        name="Товар А",
        chat_id=None,
        description=None,
        review=None,
    )
    defaults.update(overrides)
    return Order(**defaults)


class TestFindOrdersByBuyerName:
    @pytest.mark.asyncio
    async def test_filters_by_buyer_name(self, manager, account):
        account.profile.get_my_sells.return_value = [make_order(client_name="Bob"), make_order(client_name="Alice")]
        result = await manager.find_orders_by_buyer_name(buyer_name="Bob", full_info=False)
        assert len(result) == 1
        assert result[0].client_name == "Bob"

    @pytest.mark.asyncio
    async def test_filters_by_order_name_partial(self, manager, account):
        account.profile.get_my_sells.return_value = [make_order(name="Золото WoW"), make_order(name="Ключ Steam")]
        result = await manager.find_orders_by_buyer_name(order_name="wow", full_info=False)
        assert len(result) == 1
        assert result[0].name == "Золото WoW"

    @pytest.mark.asyncio
    async def test_filters_by_order_name_exact(self, manager, account):
        account.profile.get_my_sells.return_value = [make_order(name="Ключ"), make_order(name="Ключ Steam")]
        result = await manager.find_orders_by_buyer_name(order_name="ключ", search_mode="exact", full_info=False)
        assert len(result) == 1
        assert result[0].name == "Ключ"

    @pytest.mark.asyncio
    async def test_filters_by_order_name_keywords(self, manager, account):
        account.profile.get_my_sells.return_value = [
            make_order(name="Золото и ключ WoW"),
            make_order(name="Ключ Steam"),
        ]
        result = await manager.find_orders_by_buyer_name(
            order_name="золото ключ", search_mode="keywords", full_info=False
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_no_criteria_returns_empty(self, manager, account):
        account.profile.get_my_sells.return_value = [make_order()]
        result = await manager.find_orders_by_buyer_name(full_info=False)
        assert result == []

    @pytest.mark.asyncio
    async def test_full_info_enriches_orders(self, manager, account):
        order = make_order(client_name="Bob")
        account.profile.get_my_sells.return_value = [order]
        full_order = Order(order_id="1", chat_id="chat-99", description="Full desc", review={"a": 1})
        manager.get_order_details = AsyncMock(return_value=full_order)
        result = await manager.find_orders_by_buyer_name(buyer_name="Bob", full_info=True)
        assert result[0].chat_id == "chat-99"
        assert result[0].description == "Full desc"

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account.profile.get_my_sells.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetOrderInfoError):
            await manager.find_orders_by_buyer_name(buyer_name="Bob")


class TestRefundOrder:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.refund_order.return_value = response
        manager.get_order_details = AsyncMock(return_value=Order(status="Возврат"))
        result = await manager.refund_order("order-1")
        assert result is True

    @pytest.mark.parametrize("status", ["Refunded", "Повернення", "Заказ #123 / Возврат", "Order #ABC / Refunded"])
    @pytest.mark.asyncio
    async def test_success_localized_refund_status(self, manager, account, status):
        response = MagicMock()
        response.status_code = 200
        account._client.refund_order.return_value = response
        manager.get_order_details = AsyncMock(return_value=Order(status=status))
        result = await manager.refund_order("order-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_wrong_status_after_refund_raises(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.refund_order.return_value = response
        manager.get_order_details = AsyncMock(return_value=Order(status="Оплачен"))
        with pytest.raises(fpx_err.FpxRefundError):
            await manager.refund_order("order-1")

    @pytest.mark.asyncio
    async def test_non_200_returns_none(self, manager, account):
        response = MagicMock()
        response.status_code = 500
        account._client.refund_order.return_value = response
        result = await manager.refund_order("order-1")
        assert result is None
