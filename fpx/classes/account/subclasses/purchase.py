import asyncio
from dataclasses import asdict
from typing import Any

from fpx.classes.account.subclasses.order import OrderManager
from fpx.models.account import Order, Purchase
from fpx.utils import errors as fpx_err


class PurchaseManager:
    def __init__(self, account: Any):
        self._account = account

    async def get_purchase_details(self, order_id: str | int) -> Purchase:
        """
        Функция запрашивает детали покупки из /orders/{order_id}/.

        Args:
            order_id (str | int): ID заказа
        Returns:
            Purchase: Объект с данными:
                - order_id (str): ID заказа
                - status (str): Статус заказа.
                - review (dict): Словарь с данными отзыва, который оставили к заказу.
                - description (str): Строка с подробным описанием заказа
                - chat_id (str): ID чата
        Raises:
            FpxGetPurchaseInfoError: Ошибка запроса данных покупки
        """
        try:
            order_manager = OrderManager(self._account)
            order: Order = await order_manager.get_order_details(order_id)
            order_args = asdict(order)
            order_args.pop("_client")
            purchase = Purchase(**order_args)
        except Exception as e:
            raise fpx_err.FpxGetPurchaseInfoError(str(e)) from e
        return purchase

    async def get_my_purchases(self, limit: int = 0) -> list[Order]:
        """
        Запрашивает страницу покупок юзера.

        Args:
            limit (int): Лимит заказов, которые нужно вернуть(если 0, то вернёт все заказы).
        Returns:
            list: Список объектов, каждый содержит в себе:
                - order_id (str): ID заказа.
                - order_time (str): Время создания заказа.
                - client_name (str): Имя клиента.
                - price (float): Сумма заказа.
                - amount (int): Кол-во штук заказа (1 по дефолту).
                - topup_nickname (str): Данные, на которые отправлять пополнение. (ник, ссылка игрока и тд.)
                - status (str): Статус заказа.
                - name (str): Название заказа.
                - category (str): Категория заказа.
        Raises:
            FpxGetUserPurchasesError: Ошибка запроса покупок
        """
        counter = 0
        try:
            next_stage = True
            count_of_sells = 0
            data = []
            stage = "запроса данных FunPay"
            html = await self._account._client.get_my_purchases()
            next_page_id = ""
            while next_stage:
                if next_page_id:
                    html = await self._account._client.get_next_purchases(next_page_id)
                stage = "парсинга данных"
                new_data = self._account._parser.parse_my_sells(html)
                next_page_id = new_data.get("next_page")
                if not next_page_id:
                    next_stage = False
                    break
                for i in new_data["sells"]:
                    data.append(i)
                count_of_sells += len(new_data["sells"])
                if limit != 0 and count_of_sells >= limit:
                    next_stage = False
                    break
                await asyncio.sleep(3)
        except Exception as e:
            raise fpx_err.FpxGetUserPurchasesError(f"При выполнении {stage} произошла ошибка: {e}") from e
        if limit > 0:
            counter += 1
        result: list[Order] = []
        for i in data:
            if limit != 0 and counter > limit:
                break
            order = Purchase(
                order_id=i["order-id"],
                order_time=i["order-time"],
                client_name=i["client-name"],
                price=i["price"],
                status=i["status"],
                name=i["name"],
                category=i["category"],
                amount=i["amount"],
                topup_data=i.get("topup_data"),
                order_datetime=i.get('order_datetime')
            )
            result.append(order)
            counter += 1
        return result
