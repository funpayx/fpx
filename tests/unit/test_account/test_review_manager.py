"""Тесты ReviewManager — получение отзыва заказа и ответ на отзыв."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.account.subclasses.review import ReviewManager
from fpx.models.account import Order, Review
from fpx.utils import errors as fpx_err


@pytest.fixture
def account():
    acc = MagicMock()
    acc.data.user_id = "1"
    acc.order.get_order_details = AsyncMock()
    acc._client.answer_review = AsyncMock()
    acc.profile.get_user_data = AsyncMock()
    return acc


@pytest.fixture
def manager(account):
    return ReviewManager(account)


class TestGetReview:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account.order.get_order_details.return_value = Order(review={"text": "Круто", "stars": 5, "answer": "Спасибо"})
        result = await manager.get_review("order-1")
        assert isinstance(result, Review)
        assert result.text == "Круто"
        assert result.stars == 5
        assert result.answer == "Спасибо"


class TestReviewAnswer:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        response = MagicMock()
        response.json.return_value = {"content": "Спасибо за отзыв!"}
        account._client.answer_review.return_value = response
        result = await manager.review_answer("order-1", "Спасибо за отзыв!")
        assert result is True

    @pytest.mark.asyncio
    async def test_fetches_user_id_if_missing(self, manager, account):
        account.data.user_id = None

        async def fake_get_user_data():
            account.data.user_id = "42"

        account.profile.get_user_data.side_effect = fake_get_user_data
        response = MagicMock()
        response.json.return_value = {"content": "Ответ"}
        account._client.answer_review.return_value = response
        await manager.review_answer("order-1", "Ответ")
        account.profile.get_user_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_json_decode_error_raises(self, manager, account):
        import json

        response = MagicMock()
        response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
        account._client.answer_review.return_value = response
        with pytest.raises(fpx_err.FpxAnswerReviewError):
            await manager.review_answer("order-1", "text")

    @pytest.mark.asyncio
    async def test_text_not_in_response_content_raises(self, manager, account):
        response = MagicMock()
        response.json.return_value = {"content": "другой текст"}
        account._client.answer_review.return_value = response
        with pytest.raises(fpx_err.FpxAnswerReviewError) as exc:
            await manager.review_answer("order-1", "мой текст")
        assert exc.value.message == "Ответ не сохранился"

    @pytest.mark.asyncio
    async def test_error_response_with_msg_raises_with_msg(self, manager, account):
        response = MagicMock()
        response.json.return_value = {"msg": "Нельзя отвечать повторно"}
        account._client.answer_review.return_value = response
        with pytest.raises(fpx_err.FpxAnswerReviewError) as exc:
            await manager.review_answer("order-1", "текст")
        assert exc.value.message == "Нельзя отвечать повторно"
