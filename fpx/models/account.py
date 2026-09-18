from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, cast

from fpx.models.lots import LotInfo
from fpx.utils import errors as fpx_err
from fpx.utils.formatting import safe_format


@dataclass
class Balance:
    rub: float = 0.0
    usd: float = 0.0
    eur: float = 0.0


@dataclass
class Calc:
    type_name: str
    price: str
    unit: str
    pos: str


@dataclass
class CurReview:
    text: str
    stars: int
    author: str
    order_id: str
    order: Optional[Order] = None
    _client: Any = field(init=False, repr=False, default=None)

    async def answer(self, answer_text: str) -> bool:
        """Ответить на отзыв"""
        if not self._client:
            raise fpx_err.FpxClientNotAttachedError("Объект CurReview не привязан к клиенту fpx")
        if not self.order:
            raise fpx_err.FpxAttributeError("В объект не передан аттрибут Order")
        formatted_reply = safe_format(
            answer_text,
            author=self.author,
            order_id=self.order_id,
            order_name=self.order.name,
            order_time=self.order.order_time,
            stars=self.stars,
        )
        return cast(bool, await self._client._account.review.review_answer(self.order_id, formatted_reply))

    async def message_author(self, message_text: str) -> bool:
        """Ответить на отзыв в чате"""
        if not self._client:
            raise fpx_err.FpxClientNotAttachedError("Объект CurReview не привязан к клиенту fpx")
        if not self.order:
            raise fpx_err.FpxAttributeError("В объект не передан аттрибут Order")
        formatted_reply = safe_format(
            message_text,
            author=self.author,
            order_id=self.order_id,
            order_name=self.order.name,
            order_time=self.order.order_time,
            stars=self.stars,
        )
        return cast(bool, await self._client._account.chat.send_message(self.order.chat_id, formatted_reply))

    async def delete(self) -> bool:
        """Удалить отзыв или ответ на отзыв"""
        if not self._client:
            raise fpx_err.FpxClientNotAttachedError("Объект CurReview не привязан к клиенту fpx")
        return cast(bool, await self._client._account.review.delete_review(self.order_id))


@dataclass
class Profile:
    category_ids: list[str]
    lots: list[LotInfo] = field(default_factory=list)
    reviews: list[CurReview] = field(default_factory=list)


@dataclass
class UserData:
    csrf_token: str
    user_id: str


@dataclass
class Order:
    order_id: Optional[str] = None
    chat_id: Optional[str] = None
    order_time: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    price: Optional[float] = None
    amount: Optional[int] = None
    topup_data: Optional[str] = None
    finded_mapping: Optional[str] = None
    status: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    review: Optional[dict[str, Any]] = None
    _client: Any = field(init=False, repr=False, default=None)

    async def answer(self, answer_text: str) -> bool:
        """Ответить в этот же чат"""
        if not self._client:
            raise fpx_err.FpxClientNotAttachedError("Объект Order не привязан к клиенту fpx")
        formatted_reply = safe_format(
            answer_text,
            order_id=self.order_id,
            order_time=self.order_time,
            client_name=self.client_name,
            order_name=self.name,
        )
        return cast(bool, await self._client._account.chat.send_message(self.chat_id, formatted_reply))

    async def refund(self) -> bool:
        """Вернуть заказ"""
        if not self._client:
            raise fpx_err.FpxClientNotAttachedError("Объект Order не привязан к клиенту fpx")
        return cast(bool, await self._client._account.order.refund_order(self.order_id))


@dataclass
class Purchase:
    order_id: Optional[str] = None
    chat_id: Optional[str] = None
    order_time: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    price: Optional[float] = None
    amount: Optional[int] = None
    topup_data: Optional[str] = None
    finded_mapping: Optional[str] = None
    status: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    review: Optional[dict[str, Any]] = None
    _client: Any = field(init=False, repr=False, default=None)

    async def answer(self, answer_text: str) -> bool:
        """Ответить в этот же чат"""
        if not self._client:
            raise fpx_err.FpxClientNotAttachedError("Объект Purchase не привязан к клиенту fpx")
        formatted_reply = safe_format(
            answer_text,
            order_id=self.order_id,
            order_time=self.order_time,
            client_name=self.client_name,
            order_name=self.name,
        )
        return cast(bool, await self._client._account.chat.send_message(self.chat_id, formatted_reply))


@dataclass
class Review:
    text: str
    stars: int
    answer: str


@dataclass
class GameTitle:
    id: int
    name: str


@dataclass
class GameSubCategory:
    id: int
    sub_name: str


@dataclass
class Game:
    title: GameTitle
    subcategories: list[GameSubCategory] = field(default_factory=list)
