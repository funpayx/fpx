"""Тесты FpxParser — объединяет все парсеры через множественное наследование."""

from fpx._parsers import FpxParser


class TestFpxParser:
    def test_inheritance(self):
        """Проверяем, что все методы доступны."""
        assert hasattr(FpxParser, "parse_chats_list")
        assert hasattr(FpxParser, "parse_chat")
        assert hasattr(FpxParser, "parse_lot_menu")
        assert hasattr(FpxParser, "parse_current_lot_menu")
        assert hasattr(FpxParser, "parse_edit_lot_page")
        assert hasattr(FpxParser, "parse_order_page")
        assert hasattr(FpxParser, "parse_category_page")
        assert hasattr(FpxParser, "parse_profile")
        assert hasattr(FpxParser, "parse_finanses")
        assert hasattr(FpxParser, "parse_telegram_connect_url")
        assert hasattr(FpxParser, "parse_my_sells")
        assert hasattr(FpxParser, "parse_main_menu")

    def test_parse_via_fpx(self):
        """Можно вызывать методы чат-парсера через FpxParser."""
        html = """
        <a class="contact-item" href="/chat/?node=111" data-node-msg="222">
          <div class="media-user-name">Тест</div>
        </a>
        """
        chats = FpxParser.parse_chats_list(html)
        assert len(chats) == 1
        assert chats[0].username == "Тест"
