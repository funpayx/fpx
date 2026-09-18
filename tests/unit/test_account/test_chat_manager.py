"""Тесты ChatManager — чаты, отправка сообщений и изображений."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.account.subclasses.chat import ChatManager
from fpx.models.chat import Chat, ChatData
from fpx.utils import errors as fpx_err


@pytest.fixture
def account():
    acc = MagicMock()
    acc.data._node_names = {}
    acc.data._csrf_token = None
    acc.data.user_id = None
    acc._client.get_chats_page = AsyncMock()
    acc._client.get_current_chat = AsyncMock()
    acc._client.send_message_request = AsyncMock()
    acc._client.send_image_request = AsyncMock()
    acc._client.ban_chat = AsyncMock()
    acc._parser.parse_chats_list = MagicMock()
    acc._parser.parse_chat = MagicMock()
    return acc


@pytest.fixture
def manager(account):
    return ChatManager(account)


class TestGetChats:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account._client.get_chats_page.return_value = "<html></html>"
        chat = Chat(id="1", node_msg_id=1, username="Bob", last_msg="hi", date="10:00", link="/x", is_unread=False)
        account._parser.parse_chats_list.return_value = [chat]
        result = await manager.get_chats()
        assert result == [chat]

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_chats_page.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetChatsError):
            await manager.get_chats()


class TestGetChatData:
    @pytest.mark.asyncio
    async def test_success_with_messages_no_last_id(self, manager, account):
        account._client.get_current_chat.return_value = "<html></html>"
        account._parser.parse_chat.return_value = {
            "messages": [
                {"node_id": "1", "sender": "A", "message": "msg1", "is_system": False},
                {"node_id": "2", "sender": "A", "message": "msg2", "is_system": False},
            ],
            "data-name": "users-1-2",
            "csrf-token": "tok",
            "user-id": "1",
        }
        result = await manager.get_chat_data("chat-1")
        assert isinstance(result, ChatData)
        assert len(result.last_messages) == 1
        assert result.last_messages[0].text == "msg2"
        assert account.data._node_names["chat-1"] == "users-1-2"
        assert account.data._csrf_token == "tok"
        assert account.data.user_id == "1"

    @pytest.mark.asyncio
    async def test_success_with_last_message_node_id_filter(self, manager, account):
        account._client.get_current_chat.return_value = "<html></html>"
        account._parser.parse_chat.return_value = {
            "messages": [
                {"node_id": "1", "sender": "A", "message": "old", "is_system": False},
                {"node_id": "5", "sender": "A", "message": "new1", "is_system": False},
                {"node_id": "6", "sender": "A", "message": "new2", "is_system": False},
            ],
            "data-name": "users-1-2",
            "csrf-token": "tok",
            "user-id": "1",
        }
        result = await manager.get_chat_data("chat-1", last_message_node_id=2)
        assert [m.text for m in result.last_messages] == ["new1", "new2"]

    @pytest.mark.asyncio
    async def test_no_messages_returns_empty_list(self, manager, account):
        account._client.get_current_chat.return_value = "<html></html>"
        account._parser.parse_chat.return_value = {
            "messages": [],
            "data-name": "users-1-2",
            "csrf-token": "tok",
            "user-id": "1",
        }
        result = await manager.get_chat_data("chat-1")
        assert result.last_messages == []

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_current_chat.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetChatDataError):
            await manager.get_chat_data("chat-1")


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_success_fetches_chat_data_first_time(self, manager, account):
        account._client.get_current_chat.return_value = "<html></html>"
        account._parser.parse_chat.return_value = {
            "messages": [],
            "data-name": "users-1-2",
            "csrf-token": "tok",
            "user-id": "1",
        }
        account._client.send_message_request.return_value = {"error": None}
        result = await manager.send_message("chat-1", "hello")
        assert result == {"error": None}
        account._client.send_message_request.assert_awaited_once_with("users-1-2", -1, "hello")

    @pytest.mark.asyncio
    async def test_success_reuses_cached_node_name(self, manager, account):
        account.data._node_names["chat-1"] = "users-1-2"
        account.data._csrf_token = "tok"
        account._client.send_message_request.return_value = {"error": None}
        result = await manager.send_message("chat-1", "hello")
        assert result == {"error": None}
        account._client.get_current_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_response_raises(self, manager, account):
        account.data._node_names["chat-1"] = "users-1-2"
        account.data._csrf_token = "tok"
        account._client.send_message_request.return_value = {"error": "400", "msg": "bad"}
        with pytest.raises(fpx_err.FpxMessageDeliverError):
            await manager.send_message("chat-1", "hello")

    @pytest.mark.asyncio
    async def test_exception_wrapped(self, manager, account):
        account.data._node_names["chat-1"] = "users-1-2"
        account.data._csrf_token = "tok"
        account._client.send_message_request.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxMessageDeliverError):
            await manager.send_message("chat-1", "hello")


class TestSendImage:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account.data._node_names["chat-1"] = "users-1-2"
        account.data._csrf_token = "tok"
        account._client.send_image_request.return_value = {"error": None}
        result = await manager.send_image("chat-1", "img-1")
        assert result == {"error": None}
        account._client.send_image_request.assert_awaited_once_with("users-1-2", -1, "img-1")

    @pytest.mark.asyncio
    async def test_error_response_raises(self, manager, account):
        account.data._node_names["chat-1"] = "users-1-2"
        account.data._csrf_token = "tok"
        account._client.send_image_request.return_value = {"error": "400", "msg": "bad"}
        with pytest.raises(fpx_err.FpxMessageDeliverError):
            await manager.send_image("chat-1", "img-1")


class TestBanChat:
    @pytest.mark.asyncio
    async def test_success_numeric_id(self, manager, account):
        account._client.ban_chat.return_value = {"error": None}
        result = await manager.ban_chat("257449748")
        assert result is True
        account._client.ban_chat.assert_awaited_once_with("257449748")
        account._client.get_current_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_resolves_users_node_name(self, manager, account):
        account._client.get_current_chat.return_value = "<html></html>"
        account._parser.parse_chat.return_value = {"data-id": "257449748"}
        account._client.ban_chat.return_value = {"error": None}
        result = await manager.ban_chat("users-2700698-19797153")
        assert result is True
        account._client.get_current_chat.assert_awaited_once_with("users-2700698-19797153")
        account._client.ban_chat.assert_awaited_once_with("257449748")

    @pytest.mark.asyncio
    async def test_error_response_raises(self, manager, account):
        account._client.ban_chat.return_value = {"error": "1", "msg": "Нужно авторизоваться"}
        with pytest.raises(fpx_err.FpxBanChatError):
            await manager.ban_chat("123")

    @pytest.mark.asyncio
    async def test_exception_wrapped(self, manager, account):
        account._client.ban_chat.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxBanChatError):
            await manager.ban_chat("123")
