"""Тесты ChatParser — парсинг списка чатов и переписки."""

import pytest

from fpx._parsers._chats import ChatParser
from fpx.models.chat import Chat
from fpx.utils import errors as fpx_err


class TestChatParser:
    def test_parse_chats_list_success(self):
        """Успешный парсинг: 1 чат с полными данными."""
        html = """
        <a class="contact-item" href="/chat/?node=777" data-node-msg="999">
          <div class="media-user-name">Иван</div>
          <div class="contact-item-message">Привет!</div>
          <div class="contact-item-time">10:00</div>
        </a>
        """
        chats = ChatParser.parse_chats_list(html)
        assert len(chats) == 1
        assert isinstance(chats[0], Chat)
        assert chats[0].id == "777"
        assert chats[0].node_msg_id == 999
        assert chats[0].username == "Иван"
        assert chats[0].last_msg == "Привет!"
        assert chats[0].date == "10:00"
        assert chats[0].is_unread is False

    def test_parse_chats_list_unread(self):
        """Чат с классом unread помечается is_unread=True."""
        html = """
        <a class="contact-item unread" href="/chat/?node=888" data-node-msg="1">
          <div class="media-user-name">Петр</div>
        </a>
        """
        chats = ChatParser.parse_chats_list(html)
        assert chats[0].is_unread is True

    def test_parse_chats_list_fallback_links(self):
        """Если нет класса contact-item — fallback по href с node=."""
        html = """<a href="/chat/?node=111">Чат</a>"""
        chats = ChatParser.parse_chats_list(html)
        assert len(chats) == 1
        assert chats[0].id == "111"

    def test_parse_chats_list_empty_raises(self):
        """Пустая страница → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            ChatParser.parse_chats_list("<html><body>Пусто</body></html>")

    def test_parse_chat_success(self):
        """Парсинг конкретного чата: последнее сообщение от пользователя."""
        html = """
        <html><body>
          <div class="chat" data-id="123">
            <div class="chat-msg-item">
              <div class="media-user-name">
                <a class="chat-msg-author-link">Петр</a>
              </div>
              <div class="chat-msg-text">Как дела?</div>
            </div>
          </div>
        </body></html>
        """
        result = ChatParser.parse_chat(html)
        assert result["data-id"] == "123"
        assert "messages" in result
        msgs = result["messages"]
        for msg in msgs:
            assert msg["sender"] == "Петр"
            assert msg["message"] == "Как дела?"
            assert msg["is_system"] is False
            break

    def test_parse_chat_system_notification(self):
        """Системное сообщение: отправитель = FunPay, is_system = True."""
        html = """
        <html><body>
          <div class="chat">
            <div class="chat-msg-item">
              <div class="media-user-name">
                <span class="chat-msg-author-label">Оповещение</span>
              </div>
              <div class="chat-msg-text">Заказ оплачен</div>
            </div>
          </div>
        </body></html>
        """
        result = ChatParser.parse_chat(html)
        msgs = result["messages"]
        for msg in msgs:
            assert msg["sender"] == "FunPay"
            assert msg["is_system"] is True

    def test_parse_chat_empty_raises(self):
        """HTML без блока чата → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            ChatParser.parse_chat("<html><body>Нет чата</body></html>")
