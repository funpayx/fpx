"""Тесты ProfileParser — баланс, профиль, продажи, главная."""

import pytest

from fpx._parsers._profile import ProfileParser
from fpx.models.account import Balance, TransactionsPage
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

    def test_parse_transactions_order_success(self):
        """Завершённый заказ: тип, сумма, дата, курсор пагинации."""
        html = """
        <div class="tc-item transaction-status-complete" data-transaction="12345">
          <span class="tc-date-time">20 января 2024, 23:11</span>
          <span class="tc-title">Заказ #ABCDEFGH</span>
          <div class="tc-status">Завершено</div>
          <div class="tc-price">+ 1.23 ₽</div>
        </div>
        <input type="hidden" name="user_id" value="99">
        <input type="hidden" name="filter" value="">
        <input type="hidden" name="continue" value="101010">
        """
        page = ProfileParser.parse_transactions(html)
        assert isinstance(page, TransactionsPage)
        assert page.user_id == "99"
        assert page.filter == ""
        assert page.next_transaction_id == "101010"
        tx = page.transactions[0]
        assert tx.transaction_id == "12345"
        assert tx.type == "order"
        assert tx.amount == 1.23
        assert tx.currency == "₽"
        assert tx.date == "20 января 2024, 23:11"
        assert tx.description == "Заказ #ABCDEFGH"
        assert tx.status == "completed"
        assert tx.payment_method is None

    def test_parse_transactions_withdraw_cancelled(self):
        """Отменённый вывод: отрицательная сумма, метод оплаты, номер карты."""
        html = """
        <div class="tc-item transaction-status-cancel" data-transaction="54321">
          <span class="tc-date-time">20 января 2024, 23:11</span>
          <span class="tc-title">Вывод денег #54321</span>
          <span class="tc-payment-number">123456••••••7890</span>
          <span class="payment-logo payment-method-card_rub"></span>
          <div class="tc-status">Отменено</div>
          <div class="tc-price">− 1234.56 ₽</div>
        </div>
        """
        page = ProfileParser.parse_transactions(html)
        tx = page.transactions[0]
        assert tx.type == "withdraw"
        assert tx.amount == -1234.56
        assert tx.status == "cancelled"
        assert tx.payment_method == "card_rub"
        assert tx.withdrawal_number == "123456••••••7890"
        assert page.next_transaction_id is None

    def test_parse_transactions_empty_page(self):
        """Пустая история — валидный результат, не ошибка."""
        page = ProfileParser.parse_transactions("<html><body><div class='tc-finance'></div></body></html>")
        assert page.transactions == []
        assert page.next_transaction_id is None

    def test_parse_transactions_type_locales(self):
        html = """
        <div class="tc-item transaction-status-complete" data-transaction="1">
          <span class="tc-title">Payment #1</span>
          <div class="tc-price">+10 $</div>
        </div>
        <div class="tc-item transaction-status-waiting" data-transaction="2">
          <span class="tc-title">Комиссия сервиса</span>
          <div class="tc-price">−1 €</div>
        </div>
        """
        page = ProfileParser.parse_transactions(html)
        assert page.transactions[0].type == "payment"
        assert page.transactions[0].currency == "$"
        assert page.transactions[0].status == "completed"
        assert page.transactions[1].type == "other"
        assert page.transactions[1].amount == -1.0
        assert page.transactions[1].currency == "€"
        assert page.transactions[1].status == "pending"

    def test_parse_transactions_broken_items_raise(self):
        """Элементы есть, но без id — FpxParseError."""
        html = """
        <div class="tc-item transaction-status-complete">
          <span class="tc-title">Заказ #1</span>
        </div>
        """
        with pytest.raises(fpx_err.FpxParseError):
            ProfileParser.parse_transactions(html)
