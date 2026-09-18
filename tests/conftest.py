"""Общая конфигурация pytest для тестов fpx."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_client():
    """Мок fpx-клиента (используется для тестирования методов моделей типа Order.answer)."""
    client = MagicMock()
    client._account.chat.send_message = AsyncMock(return_value=True)
    client._account.review.review_answer = AsyncMock(return_value=True)
    client._account.review.delete_review = AsyncMock(return_value=True)
    client._account.order.refund_order = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_account():
    """Мок объекта Account с замоканными менеджерами (chat/profile/order/lot/...)."""
    account = MagicMock()
    account.data.username = None
    account.data.user_id = None
    account.data._csrf_token = None
    account.data._node_names = {}
    for manager in ("chat", "profile", "order", "lot", "editor", "review", "category", "addons"):
        setattr(account, manager, MagicMock())
    account._client = MagicMock()
    account._parser = MagicMock()
    account._request_engine = MagicMock()
    return account
