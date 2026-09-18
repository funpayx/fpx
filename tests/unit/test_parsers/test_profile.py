"""Тесты ProfileParser — баланс, профиль, продажи, главная."""

import pytest

from fpx._parsers._profile import ProfileParser
from fpx.models.account import Balance
from fpx.utils import errors as fpx_err


class TestProfileParser:
    def test_parse_finanses_success(self):
        """Баланс: рубли, доллары, евро."""
        html = """
        <span class="balances-list">
          <span class="balances-value">1000.50 ₽</span>
          <span class="balances-value">10.20 $</span>
          <span class="balances-value">5.00 €</span>
        </span>
        """
        balance = ProfileParser.parse_finanses(html)
        assert isinstance(balance, Balance)
        assert balance.rub == 1000.50
        assert balance.usd == 10.20
        assert balance.eur == 5.00

    def test_parse_finanses_no_container_raises(self):
        """Нет блока баланса → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            ProfileParser.parse_finanses("<html><body>Пусто</body></html>")

    def test_parse_telegram_connect_url_from_anchor(self):
        html = """
        <html><body>
          <a href="https://t.me/funpaysmartbot?start=token123">Привязать Telegram</a>
        </body></html>
        """
        assert ProfileParser.parse_telegram_connect_url(html) == "https://t.me/funpaysmartbot?start=token123"

    def test_parse_telegram_connect_url_telegram_me(self):
        html = '<a href="https://telegram.me/funpaysmartbot?start=abc">link</a>'
        assert ProfileParser.parse_telegram_connect_url(html) == "https://telegram.me/funpaysmartbot?start=abc"

    def test_parse_telegram_connect_url_empty_raises(self):
        with pytest.raises(fpx_err.FpxNullDataError):
            ProfileParser.parse_telegram_connect_url("   ")

    def test_parse_telegram_connect_url_missing_link_raises(self):
        with pytest.raises(fpx_err.FpxParseError):
            ProfileParser.parse_telegram_connect_url("<html><body>Нет ссылки</body></html>")

    def test_parse_profile_success(self):
        """Профиль: лоты + отзывы."""
        html = """
        <div class="offer">
          <a href="/lots/123"><div class="tc-desc-text">Лот 1</div></a>
          <a href="/lots/offer?id=555"><div class="tc-desc-text">Мой лот</div></a>
        </div>
        <div class="review-item">
          <div class="review-item-text">Хорошо</div>
          <div class="rating"><div class="stars-4"></div></div>
          <div class="media-user-name">Клиент</div>
          <div class="review-item-order"><a href="/orders/789/">Заказ</a></div>
        </div>
        """
        result = ProfileParser.parse_profile(html)
        assert "category-ids" in result
        assert len(result["lots"]) == 1
        assert result["lots"][0]["name"] == "Мой лот"
        assert len(result["reviews"]) == 1
        assert result["reviews"][0]["stars"] == 4
        assert result["reviews"][0]["author"] == "Клиент"
        assert result["reviews"][0]["order_id"] == "789"

    def test_parse_my_sells_success(self):
        """Продажи: парсинг tc-item."""
        html = """
        <a class="tc-item" href="/orders/100/">
          <div class="tc-order">#100</div>
          <div class="tc-date-time">12:00</div>
          <div class="tc-status">Оплачен</div>
          <span class="pseudo-a">Вася</span>
          <div class="tc-price" data-s="99.0">99 ₽</div>
          <div class="order-desc">
            <div>Товар 1 шт., nickname123</div>
            <div>Категория</div>
          </div>
        </a>
        """
        res = ProfileParser.parse_my_sells(html)
        assert len(res) == 1
        result = res["sells"]
        assert result[0]["order-id"] == "100"
        assert result[0]["status"] == "Оплачен"
        assert result[0]["client-name"] == "Вася"
        assert result[0]["price"] == 99.0
        assert result[0]["name"] == "Товар 1 шт., nickname123"
        assert result[0]["category"] == "Категория"
        assert result[0]["amount"] == 1
        assert result[0]["topup_data"] == "nickname123"

    def test_parse_my_sells_empty_raises(self):
        """Пустая страница продаж → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            ProfileParser.parse_my_sells("<html><body>Нет продаж</body></html>")

    def test_parse_main_menu_success(self):
        """Главная страница: user_id, username, csrf_token."""
        html = """
        <html><body data-app-data='{"csrf-token":"token123"}'>
          <a class="user-link-dropdown" href="/users/42/">
            <div class="user-link-name">Админ</div>
          </a>
        </body></html>
        """
        result = ProfileParser.parse_main_menu(html)
        assert result["user-id"] == "42"
        assert result["username"] == "Админ"
        assert result["csrf-token"] == "token123"

    def test_parse_main_menu_no_user_raises(self):
        """Нет ссылки на пользователя → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            ProfileParser.parse_main_menu("<html><body>Пусто</body></html>")
