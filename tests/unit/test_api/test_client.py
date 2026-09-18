"""Тесты FunPayClient — тонкая обёртка над RequestEngine/httpx клиентом."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx._api._client import FunPayClient


def make_response(text=None, json_data=None, status_code=200, headers=None):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    resp.headers = headers or {}
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def account():
    acc = MagicMock()
    acc._request_engine.execute = AsyncMock()
    return acc


@pytest.fixture
def http_client():
    return MagicMock()


@pytest.fixture
def client(account, http_client):
    return FunPayClient(account, http_client)


class TestSimpleGetEndpoints:
    @pytest.mark.asyncio
    async def test_get_chats_page(self, client, account):
        account._request_engine.execute.return_value = make_response(text="<html>chats</html>")
        result = await client.get_chats_page()
        assert result == "<html>chats</html>"
        account._request_engine.execute.assert_awaited_once_with("GET", "/chat/")

    @pytest.mark.asyncio
    async def test_get_finance_page(self, client, account):
        account._request_engine.execute.return_value = make_response(text="balance")
        result = await client.get_finance_page()
        assert result == "balance"
        account._request_engine.execute.assert_awaited_once_with("GET", "/account/balance")

    @pytest.mark.asyncio
    async def test_get_blocked_page(self, client, account):
        response = make_response(status_code=404)
        account._request_engine.execute.return_value = response
        result = await client.get_blocked_page()
        assert result is response
        account._request_engine.execute.assert_awaited_once_with("GET", "/account/blocked")

    @pytest.mark.asyncio
    async def test_get_current_chat(self, client, account):
        account._request_engine.execute.return_value = make_response(text="chat-html")
        result = await client.get_current_chat("123")
        assert result == "chat-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/chat/?node=123")

    @pytest.mark.asyncio
    async def test_get_user_profile(self, client, account):
        account._request_engine.execute.return_value = make_response(text="profile-html")
        result = await client.get_user_profile("42")
        assert result == "profile-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/users/42/")

    @pytest.mark.asyncio
    async def test_lot_menu_by_category(self, client, account):
        account._request_engine.execute.return_value = make_response(text="lots-html")
        result = await client.lot_menu_by_category("77")
        assert result == "lots-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/lots/77/trade")

    @pytest.mark.asyncio
    async def test_get_main_menu(self, client, account):
        account._request_engine.execute.return_value = make_response(text="main-html")
        result = await client.get_main_menu()
        assert result == "main-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/")

    @pytest.mark.asyncio
    async def test_get_lot_info(self, client, account):
        account._request_engine.execute.return_value = make_response(text="lot-html")
        result = await client.get_lot_info("55")
        assert result == "lot-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/lots/offer?id=55")

    @pytest.mark.asyncio
    async def test_get_my_sells(self, client, account):
        account._request_engine.execute.return_value = make_response(text="sells-html")
        result = await client.get_my_sells()
        assert result == "sells-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/orders/trade")

    @pytest.mark.asyncio
    async def test_get_order_info(self, client, account):
        account._request_engine.execute.return_value = make_response(text="order-html")
        result = await client.get_order_info("99")
        assert result == "order-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/orders/99/")

    @pytest.mark.asyncio
    async def test_get_lot_editor_data(self, client, account):
        account._request_engine.execute.return_value = make_response(text="editor-html")
        result = await client.get_lot_editor_data("11")
        assert result == "editor-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/lots/offerEdit?offer=11")

    @pytest.mark.asyncio
    async def test_get_node_editor_data(self, client, account):
        account._request_engine.execute.return_value = make_response(text="node-editor-html")
        result = await client.get_node_editor_data("22")
        assert result == "node-editor-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/lots/offerEdit?node=22")

    @pytest.mark.asyncio
    async def test_get_chip_category(self, client, account):
        account._request_engine.execute.return_value = make_response(text="chip-html")
        result = await client.get_chip_category("5")
        assert result == "chip-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/chips/5/")

    @pytest.mark.asyncio
    async def test_get_lot_category(self, client, account):
        account._request_engine.execute.return_value = make_response(text="lot-cat-html")
        result = await client.get_lot_category("6")
        assert result == "lot-cat-html"
        account._request_engine.execute.assert_awaited_once_with("GET", "/lots/6/")


class TestMessageEndpoints:
    @pytest.mark.asyncio
    async def test_send_message_request_payload_and_headers(self, client, account):
        account._request_engine.execute.return_value = make_response(json_data={"error": None})
        result = await client.send_message_request("users-1-2", -1, "hello")
        assert result == {"error": None}
        args, kwargs = account._request_engine.execute.call_args
        assert args == ("POST", "/runner/")
        assert '"node": "users-1-2"' in kwargs["data"]["request"]
        assert '"content": "hello"' in kwargs["data"]["request"]
        assert kwargs["headers"]["Referer"] == "https://funpay.com/chat/?node=2"

    @pytest.mark.asyncio
    async def test_send_image_request_payload(self, client, account):
        account._request_engine.execute.return_value = make_response(json_data={"error": None})
        result = await client.send_image_request("users-1-2", -1, "img-99")
        assert result == {"error": None}
        _, kwargs = account._request_engine.execute.call_args
        assert '"image_id": "img-99"' in kwargs["data"]["request"]


class TestLotRaising:
    @pytest.mark.asyncio
    async def test_raise_lot_json_response(self, client, account):
        account._request_engine.execute.return_value = make_response(
            json_data={"msg": "raised!"}, headers={"Content-Type": "application/json"}
        )
        result = await client.raise_lot("10", "20")
        assert result == "raised!"
        args, kwargs = account._request_engine.execute.call_args
        assert args == ("POST", "/lots/raise")
        assert kwargs["data"] == {"game_id": "20", "node_id": "10"}

    @pytest.mark.asyncio
    async def test_raise_lot_non_json_response(self, client, account):
        account._request_engine.execute.return_value = make_response(
            status_code=500, headers={"Content-Type": "text/html"}
        )
        result = await client.raise_lot("10", "20")
        assert result == {"error": "not_json", "status": 500}


class TestOrderAndReviewEndpoints:
    @pytest.mark.asyncio
    async def test_refund_order_returns_raw_response(self, client, account):
        response = make_response(status_code=200)
        account._request_engine.execute.return_value = response
        result = await client.refund_order("order-1")
        assert result is response
        args, kwargs = account._request_engine.execute.call_args
        assert args == ("POST", "/orders/refund")
        assert kwargs["data"] == {"id": "order-1"}

    @pytest.mark.asyncio
    async def test_answer_review(self, client, account):
        response = make_response(status_code=200)
        account._request_engine.execute.return_value = response
        result = await client.answer_review("author-1", "спасибо", "order-1")
        assert result is response
        args, kwargs = account._request_engine.execute.call_args
        assert args == ("POST", "/orders/review")
        assert kwargs["data"] == {"authorId": "author-1", "text": "спасибо", "rating": "", "orderId": "order-1"}


class TestEditAndCreateLot:
    @pytest.mark.asyncio
    async def test_edit_lot_builds_payload(self, client, account):
        lot = MagicMock()
        lot.form_created_at = "ts"
        lot.offer_id = "1"
        lot.node_id = "2"
        lot.location = ""
        lot.deleted = ""
        lot.fields = {"price": "100", "query": "should-be-removed"}
        response = make_response(status_code=200)
        account._request_engine.execute.return_value = response
        result = await client.edit_lot(lot, active=True)
        assert result is response
        _, kwargs = account._request_engine.execute.call_args
        assert kwargs["data"]["location"] == "offer"
        assert kwargs["data"]["active"] == "on"
        assert "query" not in kwargs["data"]
        assert kwargs["data"]["price"] == "100"

    @pytest.mark.asyncio
    async def test_edit_lot_active_false_pops_active(self, client, account):
        lot = MagicMock()
        lot.form_created_at = "ts"
        lot.offer_id = "1"
        lot.node_id = "2"
        lot.location = "offer"
        lot.deleted = ""
        lot.fields = {"active": "on"}
        account._request_engine.execute.return_value = make_response(status_code=200)
        await client.edit_lot(lot, active=False)
        _, kwargs = account._request_engine.execute.call_args
        assert "active" not in kwargs["data"]

    @pytest.mark.asyncio
    async def test_create_lot_builds_payload_from_fields_list(self, client, account):
        lot = MagicMock()
        lot._form_created_at = "ts"
        lot._offer_id = "1"
        lot._node_id = "2"
        lot._location = ""
        lot._deleted = ""
        field_a = MagicMock(key="price", value="100")
        field_b = MagicMock(key="query", value="drop-me")
        lot.fields = [field_a, field_b]
        response = make_response(status_code=200)
        account._request_engine.execute.return_value = response
        result = await client.create_lot(lot)
        assert result is response
        _, kwargs = account._request_engine.execute.call_args
        assert kwargs["data"]["active"] == "on"
        assert kwargs["data"]["price"] == "100"
        assert "query" not in kwargs["data"]


class TestDirectHttpClientEndpoints:
    @pytest.mark.asyncio
    async def test_upload_image(self, client, http_client):
        http_client.request = AsyncMock(return_value=make_response(json_data={"fileId": 5}))
        result = await client.upload_image(b"bytes")
        assert result == {"fileId": 5}
        args, kwargs = http_client.request.call_args
        assert args == ("POST", "/file/addChatImage")
        assert kwargs["files"]["file"][0] == "image.png"

    @pytest.mark.asyncio
    async def test_find_category(self, client, http_client):
        http_client.request = AsyncMock(return_value=make_response(json_data={"html": "<div></div>"}))
        result = await client.find_category("minecraft")
        assert result == {"html": "<div></div>"}
        args, kwargs = http_client.request.call_args
        assert args == ("POST", "/games/promoFilter")
        assert kwargs["data"] == {"query": "minecraft"}

    @pytest.mark.asyncio
    async def test_calc_category_price(self, client, http_client):
        http_client.request = AsyncMock(return_value=make_response(json_data={"methods": []}))
        result = await client.calc_category_price(100, "node-1")
        assert result == {"methods": []}
        args, kwargs = http_client.request.call_args
        assert args == ("POST", "/lots/calc")
        assert kwargs["data"] == {"nodeId": "node-1", "price": 100}

    @pytest.mark.asyncio
    async def test_get_next_sells(self, client, http_client):
        http_client.request = AsyncMock(return_value=make_response(text="next-page-html"))
        result = await client.get_next_sells("page-2")
        assert result == "next-page-html"
        args, kwargs = http_client.request.call_args
        assert args == ("POST", "/orders/trade")
        assert kwargs["data"] == {"continue": "page-2"}
