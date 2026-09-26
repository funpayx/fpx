import json
from typing import Any

from fpx.models.account import Review
from fpx.utils import errors as fpx_err


class ReviewManager:
    def __init__(self, account: Any) -> None:
        # account: Account (см. fpx/classes/account/account.py). Оставлен как Any,
        # так как сам класс Account ещё не аннотирован (отдельная задача #20).
        self._account = account

    async def get_review(self, order_id: str | int) -> Review:
        """
        Забирает отзыв от заказа.

        Args:
            order_id (str | int): Айди заказа.
        Returns:
            Review: Объект с данными отзыва:
                - text (str): Текст отзыва.
                - stars (int): Количество звёзд в отзыве.
                - answer (str): Ваш ответ на отзыв, может быть пустой строкой.
        """
        r = await self._account.order.get_order_details(order_id)
        rev = r.review or {}
        review = Review(text=rev.get("text"), stars=rev.get("stars"), answer=rev.get("answer"))
        return review

    async def review_answer(self, order_id: str | int, text: str) -> bool:
        """
        Отвечает на отзыв, оставленный покупателем.

        Args:
            order_id (str | int): ID заказа, на отзыв которого хотите ответить,
            text (str): Текст, которым вы хотите ответить на отзыв.
        Returns:
            bool: True при успехе
        Raises:
            FpxAnswerReviewError: При ошибке (ответ не совпадает заданному/сервер не вернул ничего).
        """
        if self._account.data.user_id is None:
            await self._account.profile.get_user_data()
        r = await self._account._client.answer_review(self._account.data.user_id, text, order_id)
        try:
            response = r.json()
        except json.JSONDecodeError as e:
            raise fpx_err.FpxAnswerReviewError("Сервер не вернул ничего") from e

        if "msg" in response:
            raise fpx_err.FpxAnswerReviewError(message=response["msg"])

        content = response.get("content", "")
        if text in content:
            return True

        raise fpx_err.FpxAnswerReviewError(message="Ответ не сохранился")

    async def delete_review(self, order_id: str | int) -> bool:
        """
        Удаляет отзыв или ответ на отзыв.

        Args:
            order_id (str | int): ID заказа, отзыв (или ответ на отзыв) которого хотите удалить.
        Returns:
            bool: True при успехе
        Raises:
            FpxDeleteReviewError: При ошибке (сервер не вернул виджет отзыва / сервер не вернул ничего).
        """
        if self._account.data.user_id is None:
            await self._account.profile.get_user_data()
        r = await self._account._client.delete_review(self._account.data.user_id, order_id)
        try:
            response = r.json()
        except json.JSONDecodeError as e:
            raise fpx_err.FpxDeleteReviewError("Сервер не вернул ничего") from e
        try:
            if "content" in response:
                return True
            raise fpx_err.FpxDeleteReviewError(message="Отзыв не удалён")
        except Exception as e:
            raise fpx_err.FpxDeleteReviewError(message=response.get("msg") if response.get("msg") else response) from e
