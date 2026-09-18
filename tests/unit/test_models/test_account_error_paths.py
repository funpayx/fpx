"""Доп. тесты моделей аккаунта: обработка ошибок Order/CurReview без клиента/заказа."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.models.account import CurReview, Order
from fpx.utils import errors as fpx_err


class TestOrderErrorPaths:
    @pytest.mark.asyncio
    async def test_answer_without_client_raises(self):
        order = Order(order_id="1")
        with pytest.raises(fpx_err.FpxClientNotAttachedError):
            await order.answer("текст")

    @pytest.mark.asyncio
    async def test_refund_without_client_raises(self):
        order = Order(order_id="1")
        with pytest.raises(fpx_err.FpxClientNotAttachedError):
            await order.refund()

    @pytest.mark.asyncio
    async def test_refund_with_client_delegates_to_order_manager(self):
        order = Order(order_id="1")
        client = MagicMock()
        client._account.order.refund_order = AsyncMock(return_value=True)
        order._client = client
        result = await order.refund()
        assert result is True
        client._account.order.refund_order.assert_awaited_once_with("1")


class TestCurReviewErrorPaths:
    @pytest.mark.asyncio
    async def test_answer_without_client_raises(self):
        review = CurReview(text="OK", stars=5, author="A", order_id="1")
        with pytest.raises(fpx_err.FpxClientNotAttachedError):
            await review.answer("текст")

    @pytest.mark.asyncio
    async def test_answer_without_order_raises(self):
        review = CurReview(text="OK", stars=5, author="A", order_id="1")
        review._client = MagicMock()
        with pytest.raises(fpx_err.FpxAttributeError):
            await review.answer("текст")

    @pytest.mark.asyncio
    async def test_message_author_without_client_raises(self):
        review = CurReview(text="OK", stars=5, author="A", order_id="1")
        with pytest.raises(fpx_err.FpxClientNotAttachedError):
            await review.message_author("текст")

    @pytest.mark.asyncio
    async def test_message_author_without_order_raises(self):
        review = CurReview(text="OK", stars=5, author="A", order_id="1")
        review._client = MagicMock()
        with pytest.raises(fpx_err.FpxAttributeError):
            await review.message_author("текст")

    @pytest.mark.asyncio
    async def test_delete_without_client_raises(self):
        review = CurReview(text="OK", stars=5, author="A", order_id="1")
        with pytest.raises(fpx_err.FpxClientNotAttachedError):
            await review.delete()

    @pytest.mark.asyncio
    async def test_delete_with_client_delegates_to_review_manager(self):
        review = CurReview(text="OK", stars=5, author="A", order_id="1")
        client = MagicMock()
        client._account.review.delete_review = AsyncMock(return_value=True)
        review._client = client
        result = await review.delete()
        assert result is True
        client._account.review.delete_review.assert_awaited_once_with("1")

    @pytest.mark.asyncio
    async def test_message_author_with_client_and_order_sends_message(self):
        order = Order(order_id="1", name="Товар", order_time="12:00", chat_id="chat-1")
        review = CurReview(text="OK", stars=5, author="A", order_id="1", order=order)
        client = MagicMock()
        client._account.chat.send_message = AsyncMock(return_value=True)
        review._client = client
        result = await review.message_author("Привет, {author}!")
        assert result is True
        client._account.chat.send_message.assert_awaited_once_with("chat-1", "Привет, A!")

    @pytest.mark.asyncio
    async def test_message_author_keeps_literal_braces(self):
        order = Order(order_id="1", name="Товар", order_time="12:00", chat_id="chat-1")
        review = CurReview(text="OK", stars=5, author="A", order_id="1", order=order)
        client = MagicMock()
        client._account.chat.send_message = AsyncMock(return_value=True)
        review._client = client
        result = await review.message_author('{author}, промо {SALE50}, json {"n":1}')
        assert result is True
        client._account.chat.send_message.assert_awaited_once_with("chat-1", 'A, промо {SALE50}, json {"n":1}')
