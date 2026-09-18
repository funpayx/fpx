import asyncio
from typing import Any, cast

from fpx.models.account import (
    Balance,
    CurReview,
    Order,
    Profile,
    Transaction,
    TransactionsPage,
    UserData,
)
from fpx.models.lots import LotInfo
from fpx.utils import errors as fpx_err


class ProfileManager:
    def __init__(self, account: Any) -> None:
        # account: Account (см. fpx/classes/account/account.py). Оставлен как Any,
        # так как сам класс Account ещё не аннотирован (отдельная задача #20).
        self._account = account

    async def get_user_data(self) -> UserData:
        """
        Запрашивает данные юзера, сохраняет их в кеш.

        Returns:
            UserData: Объект с данными юзера:
                - user_id (str): ID юзера.
                - csrf_token (str): Нужен для любого post запроса на funpay.
        Raises:
            FpxGetUserDataError: ошибка запроса данных юзера
        """
        try:
            stage = "запроса данных FunPay"
            html = await self._account._client.get_main_menu()
            stage = "парсинга данных"
            data = self._account._parser.parse_main_menu(html)
            stage = "типизации данных"
            self._account.data.username = data["username"]
            self._account.data.user_id = data["user-id"]
            self._account.data._csrf_token = data["csrf-token"]
            user_data = UserData(csrf_token=data["csrf-token"], user_id=data["user-id"])
        except Exception as e:
            raise fpx_err.FpxGetUserDataError(f"При выполнении {stage} произошла ошибка: {e}")
        return user_data

    async def get_my_sells(self, limit: int = 0) -> list[Order]:
        """
        Запрашивает страницу продаж юзера.

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
            FpxGetUserSellsError: Ошибка запроса продаж
        """
        counter = 0
        try:
            next_stage = True
            count_of_sells = 0
            data = []
            stage = "запроса данных FunPay"
            html = await self._account._client.get_my_sells()
            next_page_id = ""
            while next_stage:
                if next_page_id:
                    html = await self._account._client.get_next_sells(next_page_id)
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
            raise fpx_err.FpxGetUserSellsError(f"При выполнении {stage} произошла ошибка: {e}")
        if limit > 0:
            counter += 1
        result: list[Order] = []
        for i in data:
            if limit != 0 and counter > limit:
                break
            order = Order(
                order_id=i["order-id"],
                order_time=i["order-time"],
                client_name=i["client-name"],
                price=i["price"],
                status=i["status"],
                name=i["name"],
                category=i["category"],
                amount=i["amount"],
                topup_data=i.get("topup_data"),
            )
            result.append(order)
            counter += 1
        return result

    async def profile(self, user_id: str | int | None = None) -> Profile:
        """
        Запрашивает профиль юзера.
        Args:
            user_id (str | int): Можно не передавать, если None,
            сама узнает айди владельца сессии и запросит данные о нём.
            Айди юзера.
        Returns:
            Profile: Объект, с данными:
                - category_ids (list): ID категорий, в которых у юзера выставлены лоты.
                - lots (list): Список объектов LotInfo с лотами юзера .
                - reviews (list): Список объектов отзыва CurReview с данными:
                    - text (str): Текст отзыва.
                    - stars (int): Кол-во звёзд в отзыве (1-5).
                    - author (str): Автор отзыва.
                    - item_name (str): Название заказа, под которым оставлен отзыв.
        Raises:
            FpxGetProfileError: Ошибка запроса профиля
        """
        target_id = user_id or self._account.data.user_id
        if not target_id:
            target = await self.get_user_data()
            target_id = target.user_id
        try:
            step = "запроса данных FunPay"
            html = await self._account._client.get_user_profile(target_id)
            step = "парсинга данных"
            data = self._account._parser.parse_profile(html)
            step = "типизации данных"
            lots_list = [LotInfo(name=lot["name"], id=lot["id"]) for lot in data["lots"]]
            reviews = [
                CurReview(text=rev["text"], stars=rev["stars"], author=rev["author"], order_id=rev["order_id"])
                for rev in data["reviews"]
            ]
            profile = Profile(category_ids=data["category-ids"], lots=lots_list, reviews=reviews)
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При выполнении {step} произошла ошибка: {e}")
        return profile

    async def get_balance(self) -> Balance:
        """
        Собирает баланс аккаунта.

        Returns:
            Balance: Объект с валютами:
                - rub (float): Баланс в рублях
                - usd (float): Баланс в долларах
                - eur (float): Баланс в евро
        Raises:
            FpxGetProfileError: Ошибка сбора баланса
        """
        try:
            step = "запрос данных FunPay"
            html = await self._account._client.get_finance_page()
            step = "парсинг данных"
            balance = self._account._parser.parse_finanses(html)
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При сборе баланса, выполняя {step} произошла ошибка: {e}")
        return cast(Balance, balance)

    async def get_transactions_page(
        self,
        from_transaction_id: str | int | None = None,
        filter: str = "",
    ) -> TransactionsPage:
        """
        Одна страница истории транзакций.

        Без фильтра и курсора — ``GET /account/balance`` (первая пачка).
        Иначе — ``POST /users/transactions`` (как FunPay API).

        Args:
            from_transaction_id (str | int | None): Курсор ``continue`` для следующей пачки.
            filter (str): Фильтр FunPay: ``""``, ``payment``, ``withdraw``, ``order``, ``other``.
        Returns:
            TransactionsPage: Пачка транзакций и курсор ``next_transaction_id``.
        Raises:
            FpxAuthError: Неверные куки
            FpxGetProfileError: Ошибка запроса истории транзакций
        """
        needs_post = bool(filter) or (from_transaction_id not in (None, "", 0, "0"))
        user_id = None
        if needs_post:
            user_id = self._account.data.user_id
            if not user_id:
                user_data = await self.get_user_data()
                user_id = user_data.user_id
        try:
            step = "запроса данных FunPay"
            if needs_post:
                html = await self._account._client.get_transactions(
                    user_id=user_id,
                    filter=filter,
                    from_transaction_id=from_transaction_id or "",
                )
            else:
                html = await self._account._client.get_transactions_page()
            step = "парсинга данных"
            page = self._account._parser.parse_transactions(html)
            if page.user_id and not self._account.data.user_id:
                self._account.data.user_id = page.user_id
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При получении транзакций, выполняя {step} произошла ошибка: {e}")
        return cast(TransactionsPage, page)

    async def get_transactions(
        self,
        limit: int = 0,
        filter: str = "",
        from_transaction_id: str | int | None = None,
    ) -> list[Transaction]:
        """
        История транзакций аккаунта. Пагинирует страницы FunPay.

        Args:
            limit (int): Сколько операций вернуть (0 — все доступные).
            filter (str): Фильтр FunPay: ``""``, ``payment``, ``withdraw``, ``order``, ``other``.
            from_transaction_id (str | int | None): Начать с этой пачки (курсор ``continue``).
        Returns:
            list[Transaction]: Список операций (тип, сумма, дата и др.).
        Raises:
            FpxAuthError: Неверные куки
            FpxGetProfileError: Ошибка запроса истории транзакций
        """
        collected: list[Transaction] = []
        cursor = from_transaction_id
        first = True
        while True:
            if not first:
                await asyncio.sleep(3)
            first = False
            page = await self.get_transactions_page(from_transaction_id=cursor, filter=filter)
            collected.extend(page.transactions)
            if limit != 0 and len(collected) >= limit:
                return collected[:limit]
            next_id = page.next_transaction_id
            if not next_id or str(next_id) == str(cursor or ""):
                return collected
            cursor = next_id
