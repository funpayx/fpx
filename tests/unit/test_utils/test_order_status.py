"""Тесты классификации локализованных статусов заказа FunPay."""

import pytest

from fpx.utils.order_status import (
    OrderStatusKind,
    classify_order_status,
    is_closed_status,
    is_paid_status,
    is_refunded_status,
    normalize_order_status,
)

PAID_STATUSES = (
    "Оплачен",
    "оплачено",
    "Paid",
    "PAID",
    "Відкрито",
    "открыто",
    "Opened",
    "Заказ #123 / Оплачен",
    "Order #ABC / Paid",
    "Замовлення #1 / Відкрито",
)

CLOSED_STATUSES = (
    "Закрыт",
    "закрыто",
    "Closed",
    "CLOSED",
    "Закрито",
    "Completed",
    "Заказ #123 / Закрыт",
    "Order #ABC / Closed",
    "Замовлення #1 / Закрито",
)

REFUNDED_STATUSES = (
    "Возврат",
    "возвращен",
    "Refund",
    "Refunded",  # основная форма на en-локали FunPay, раньше не матчилась
    "REFUNDED",
    "Повернення",
    "повернуто",
    "Заказ #123 / Возврат",
    "Order #ABC / Refunded",
    "Замовлення #1 / Повернення",
)

UNKNOWN_STATUSES = (
    None,
    "",
    "   ",
    "Unknown",
    "какой-то другой статус",
    "pending",
)


class TestNormalizeOrderStatus:
    def test_none_and_empty(self):
        assert normalize_order_status(None) == ""
        assert normalize_order_status("") == ""
        assert normalize_order_status("   ") == ""

    def test_lower_and_strip(self):
        assert normalize_order_status("  Refunded  ") == "refunded"

    def test_extracts_header_tail(self):
        assert normalize_order_status("Заказ #ABC / Оплачен") == "оплачен"
        assert normalize_order_status("Order #ABC / Refunded") == "refunded"


class TestClassifyOrderStatus:
    @pytest.mark.parametrize("status", PAID_STATUSES)
    def test_paid_locales(self, status):
        assert classify_order_status(status) is OrderStatusKind.PAID
        assert is_paid_status(status)
        assert not is_closed_status(status)
        assert not is_refunded_status(status)

    @pytest.mark.parametrize("status", CLOSED_STATUSES)
    def test_closed_locales(self, status):
        assert classify_order_status(status) is OrderStatusKind.CLOSED
        assert is_closed_status(status)
        assert not is_paid_status(status)
        assert not is_refunded_status(status)

    @pytest.mark.parametrize("status", REFUNDED_STATUSES)
    def test_refunded_locales(self, status):
        assert classify_order_status(status) is OrderStatusKind.REFUNDED
        assert is_refunded_status(status)
        assert not is_paid_status(status)
        assert not is_closed_status(status)

    @pytest.mark.parametrize("status", UNKNOWN_STATUSES)
    def test_unknown_and_empty(self, status):
        assert classify_order_status(status) is None
        assert not is_paid_status(status)
        assert not is_closed_status(status)
        assert not is_refunded_status(status)

    def test_refund_prefix_matches_refunded(self):
        # Регрессия #37: точное вхождение «refund» не ловит «refunded».
        assert classify_order_status("refunded") is OrderStatusKind.REFUNDED

    def test_ru_detection_unchanged(self):
        assert classify_order_status("Оплачен") is OrderStatusKind.PAID
        assert classify_order_status("Закрыт") is OrderStatusKind.CLOSED
        assert classify_order_status("Возврат") is OrderStatusKind.REFUNDED
