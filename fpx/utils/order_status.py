"""Классификация статусов заказа FunPay по локализованному тексту."""

from __future__ import annotations

import re
from enum import Enum


class OrderStatusKind(str, Enum):
    """Нормализованный статус заказа, независимый от локали аккаунта."""

    PAID = "paid"
    CLOSED = "closed"
    REFUNDED = "refunded"


# Известные подписи FunPay (ru / en / uk) и близкие морфологические формы.
# Сопоставление не требует полного равенства: «Refunded» матчится по префиксу «refund».
_PAID_ALIASES = frozenset(
    {
        "оплачен",
        "оплачено",
        "оплачена",
        "оплачені",
        "оплачений",
        "paid",
        "відкрито",
        "открыт",
        "открыто",
        "open",
        "opened",
    }
)

_CLOSED_ALIASES = frozenset(
    {
        "закрыт",
        "закрыто",
        "закрыта",
        "закрытий",
        "closed",
        "закрито",
        "закрит",
        "закритий",
        "completed",
        "complete",
    }
)

_REFUNDED_ALIASES = frozenset(
    {
        "возврат",
        "возвращен",
        "возвращено",
        "возвращена",
        "возвращений",
        "повернення",
        "повернуто",
        "refund",
        "refunded",
    }
)

# Порядок как в прежних if/elif раннеров: сначала закрыт, затем оплачен, затем возврат.
_KIND_ALIASES: tuple[tuple[OrderStatusKind, frozenset[str]], ...] = (
    (OrderStatusKind.CLOSED, _CLOSED_ALIASES),
    (OrderStatusKind.PAID, _PAID_ALIASES),
    (OrderStatusKind.REFUNDED, _REFUNDED_ALIASES),
)

_TOKEN_SPLIT = re.compile(r"\W+", flags=re.UNICODE)
_MIN_PREFIX_LEN = 4


def normalize_order_status(status: str | None) -> str:
    """Приводит сырой статус к нижнему регистру и выделяет хвост после « / ».

    Парсер страницы заказа склеивает спаны заголовка в строку вида
    ``Заказ #ABC / Оплачен`` / ``Order #ABC / Refunded``.
    """
    if not status:
        return ""
    text = status.strip().lower()
    if " / " in text:
        text = text.rsplit(" / ", 1)[-1].strip()
    return text


def _alias_matches(normalized: str, alias: str) -> bool:
    if not normalized or not alias:
        return False
    if normalized == alias:
        return True
    if len(alias) >= _MIN_PREFIX_LEN and normalized.startswith(alias):
        return True
    for token in _TOKEN_SPLIT.split(normalized):
        if not token:
            continue
        if token == alias:
            return True
        if len(alias) >= _MIN_PREFIX_LEN and token.startswith(alias):
            return True
    return False


def classify_order_status(status: str | None) -> OrderStatusKind | None:
    """Определяет вид статуса по локализованному тексту FunPay.

    Returns:
        OrderStatusKind или None, если статус пустой/неизвестный.
    """
    normalized = normalize_order_status(status)
    if not normalized:
        return None
    for kind, aliases in _KIND_ALIASES:
        if any(_alias_matches(normalized, alias) for alias in aliases):
            return kind
    return None


def is_paid_status(status: str | None) -> bool:
    return classify_order_status(status) is OrderStatusKind.PAID


def is_closed_status(status: str | None) -> bool:
    return classify_order_status(status) is OrderStatusKind.CLOSED


def is_refunded_status(status: str | None) -> bool:
    return classify_order_status(status) is OrderStatusKind.REFUNDED
