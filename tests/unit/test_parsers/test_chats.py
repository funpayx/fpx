"""Тесты ChatParser — парсинг списка чатов и переписки."""

import json

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

    def test_parse_chat_real_notification_markup(self):
        """Оповещение и сообщение покупателя в разметке страницы чата FunPay (сентябрь 2026).

        Ники, ID и номер заказа заменены. У оповещения имя FunPay написано текстом,
        без ссылки на профиль, и стоит метка «оповещение»; ссылки на покупателя
        есть только в тексте сообщения. Покупатель, написавший «оплатил заказ»,
        системным не считается.
        """
        html = """
        <html>
        <body data-app-data="{&quot;csrf-token&quot;:&quot;tok&quot;,&quot;userId&quot;:1000}">
        <div class="chat chat-float" data-id="555" data-name="users-1000-2000" data-user="1000">
        <div class="chat-message-container"><div class="chat-message-list">
        <div class="chat-msg-item chat-msg-with-head" id="message-101">
        <div class="chat-message">
        <div class="media-user-name">
                        FunPay
                        <span class="chat-msg-author-label label label-primary">оповещение</span>
        <div class="chat-msg-date" title="26 сентября, 4:09:42">04:09:42</div>
        </div>
        <div class="chat-msg-body">
        <div class="alert alert-with-icon alert-info" role="alert">
        <i class="fas fa-info-circle alert-icon"></i>
        <div class="chat-msg-text">Покупатель <a href="https://funpay.com/users/2000/">Buyer</a> оплатил
        <a href="https://funpay.com/orders/ABCD1234/">заказ #ABCD1234</a>. Roblox, Донат робуксов (паки), 80 робуксов.
        <a href="https://funpay.com/users/2000/">Buyer</a>, не забудьте потом нажать кнопку
        «Подтвердить выполнение заказа».</div>
        </div>
        </div>
        </div>
        </div>
        <div class="chat-msg-item chat-msg-with-head" id="message-102">
        <div class="chat-message">
        <div class="media-user-name">
        <a class="chat-msg-author-link" href="https://funpay.com/users/2000/">Buyer</a>
        <div class="chat-msg-date" title="26 сентября, 4:10:22">04:10:22</div>
        </div>
        <div class="chat-msg-body">
        <div class="chat-msg-text">Я оплатил заказ, где товар?</div>
        </div>
        </div>
        </div>
        </div></div>
        </div>
        </body>
        </html>
        """
        messages = ChatParser.parse_chat(html)["messages"]
        assert [(msg["node_id"], msg["sender"], msg["is_system"]) for msg in messages] == [
            ("101", "FunPay", True),
            ("102", "Buyer", False),
        ]
        assert messages[0]["message"].startswith("Покупатель")

    def test_parse_chat_empty_raises(self):
        """HTML без блока чата → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            ChatParser.parse_chat("<html><body>Нет чата</body></html>")

    def test_parse_chat_invalid_app_data_chains_cause(self):
        """Сломанный data-app-data → FpxParseError с исходным JSONDecodeError в __cause__."""
        html = """
        <html><body data-app-data="not-json">
          <div class="chat" data-name="users-1-2"></div>
        </body></html>
        """
        with pytest.raises(fpx_err.FpxParseError) as exc:
            ChatParser.parse_chat(html)
        assert isinstance(exc.value.__cause__, json.JSONDecodeError)
