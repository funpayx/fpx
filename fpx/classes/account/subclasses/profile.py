import asyncio
from typing import Any, cast

from fpx.models.account import Balance, CurReview, Order, Profile, UserData
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
        stage = "запроса данных FunPay"
        try:
            html = await self._account._client.get_main_menu()
            stage = "парсинга данных"
            data = self._account._parser.parse_main_menu(html)
            stage = "типизации данных"
            self._account.data.username = data["username"]
            self._account.data.user_id = data["user-id"]
            self._account.data._csrf_token = data["csrf-token"]
            user_data = UserData(csrf_token=data["csrf-token"], user_id=data["user-id"])
        except Exception as e:
            raise fpx_err.FpxGetUserDataError(f"При выполнении {stage} произошла ошибка: {e}") from e
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
        stage = "запроса данных FunPay"
        try:
            next_stage = True
            count_of_sells = 0
            data = []
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
            raise fpx_err.FpxGetUserSellsError(f"При выполнении {stage} произошла ошибка: {e}") from e
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
        step = "запроса данных FunPay"
        try:
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
            raise fpx_err.FpxGetProfileError(f"При выполнении {step} произошла ошибка: {e}") from e
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
        step = "запрос данных FunPay"
        try:
            html = await self._account._client.get_finance_page()
            step = "парсинг данных"
            balance = self._account._parser.parse_finanses(html)
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При сборе баланса, выполняя {step} произошла ошибка: {e}") from e
        return cast(Balance, balance)

    async def check_banned(self) -> bool:
        """
        Проверяет, заблокирован ли текущий аккаунт.

        FunPay отвечает на GET /account/blocked статусом 200, если аккаунт в бане,
        и 404, если бана нет.

        Returns:
            bool: True если аккаунт заблокирован, иначе False.
        Raises:
            FpxAuthError: Неверные куки
            FpxGetProfileError: Ошибка проверки бана
        """
        step = "запроса данных FunPay"
        try:
            response = await self._account._client.get_blocked_page()
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При проверке бана, выполняя {step} произошла ошибка: {e}") from e
        return response.status_code == 200

    async def get_2fa_status(self) -> bool:
        """
        Проверяет, включена ли двухфакторная аутентификация на аккаунте.

        Returns:
            bool: True если 2FA включена, False если выключена.
        Raises:
            FpxGetProfileError: Ошибка запроса статуса 2FA
        """
        step = "запроса данных FunPay"
        try:
            html = await self._account._client.get_2fa_settings_page()
            step = "парсинг данных"
            enabled = self._account._parser.parse_2fa_status(html)
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При сборе статуса 2FA, выполняя {step} произошла ошибка: {e}") from e
        return bool(enabled)

    async def get_telegram_connect_url(self) -> str:
        """
        Запрашивает ссылку для подключения Telegram.

        Returns:
            str: Ссылка на телеграм бота для подключения тг
        Raises:
            FpxGetProfileError: Ошибка запроса статуса 2FA
        """
        step = "запроса данных FunPay"
        try:
            tg_link = await self._account._client.get_tg_conn_link()
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При сборе статуса 2FA, выполняя {step} произошла ошибка: {e}") from e
        return tg_link

    async def update_notice_channel(self, channel_id: list[int | str] | int | str, enable: bool) -> bool | list[bool]:
        """
        Обновляет канал уведомлений.
        ID каналов:
            1) 'email'
            2) 'push'
            3) 'telegram'
        Args:
            channel_id (list[int | str] | int | str): ID/Список ID каналов, которые надо подключить.
                Можно передать как числом, так и текстовым значением, выше список каналов.
            enable (bool): True если включить, False если выключить переданное в channel_id.
        Returns:
            list[bool] | bool: True если удалось обновить канал
        Raises:
            FpxAttributeError: Неизвестный канал
            FpxPostProfileError: Ошибка обновления канала уведомлений
        """
        return_single: bool = False
        result_list = []
        if not isinstance(channel_id, list) and isinstance(channel_id, int | str):
            channel_id = [channel_id]
            return_single = True
        elif not isinstance(channel_id, list):
            raise fpx_err.FpxAttributeError("Вы должны передать аргументы типа int | str | list в channel_id!")
        for channel in channel_id:
            cid: int | None = self._find_notice_channel(channel)
            try:
                result_list.append(await self._account._client.update_notice_channel(cid, enable))
            except Exception as e:
                raise fpx_err.FpxPostProfileError("Не удалось обновить канал уведомлений") from e
        return result_list[0] if return_single else result_list

    def _find_notice_channel(self, channel: int | str) -> int:
        if channel == 1 or channel == "email":
            return 1
        elif channel == 2 or channel == "push":
            return 2
        elif channel == 3 or channel == "telegram":
            return 3
        raise fpx_err.FpxAttributeError("Вы должны передать аргументы типа int | str | list в channel_id!")
