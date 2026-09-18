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

    async def get_telegram_connect_url(self) -> str:
        """
        Возвращает ссылку привязки Telegram-уведомлений (@funpaysmartbot).

        FunPay: GET /account/linkTelegram — обычно редирект на t.me.

        Returns:
            str: URL привязки Telegram (после редиректа или из HTML).
        Raises:
            FpxAuthError: Неверные куки
            FpxGetProfileError: Ошибка запроса ссылки привязки
        """
        try:
            step = "запроса данных FunPay"
            response = await self._account._client.get_telegram_connect_page()
            step = "извлечения ссылки"
            url = self._extract_telegram_connect_url(response)
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetProfileError(f"При получении ссылки Telegram, выполняя {step} произошла ошибка: {e}")
        return url

    async def update_notice_channel(self, channel: int | str, enabled: bool) -> bool:
        """
        Включает или выключает канал уведомлений аккаунта.

        FunPay: POST /account/noticeChannel
        (``channel``: 1 email / 2 push / 3 telegram, ``active``: 1/0).

        Args:
            channel (int | str): Канал — 1/2/3 или ``email`` / ``push`` / ``telegram``.
            enabled (bool): True — включить, False — выключить.
        Returns:
            bool: True если запрос успешен.
        Raises:
            FpxValidateError: Неизвестный канал
            FpxAuthError: Неверные куки
            FpxGetProfileError: Ошибка обновления канала уведомлений
        """
        channel_id = _resolve_notice_channel(channel)
        try:
            step = "запроса данных FunPay"
            response = await self._account._client.update_notice_channel(channel_id, bool(enabled))
            if getattr(response, "status_code", None) == 200:
                return True
            raise fpx_err.FpxRequestError(
                f"Сервер не ответил успешно. Код ошибки: {getattr(response, 'status_code', 'unknown')}"
            )
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetProfileError(
                f"При обновлении канала уведомлений, выполняя {step} произошла ошибка: {e}"
            )

    def _extract_telegram_connect_url(self, response: Any) -> str:
        url = str(getattr(response, "url", "") or "")
        location = _header_value(getattr(response, "headers", None), "Location")
        for candidate in (url, location):
            if candidate and _is_telegram_connect_url(candidate):
                return candidate
        html = getattr(response, "text", "") or ""
        try:
            return cast(str, self._account._parser.parse_telegram_connect_url(html))
        except (fpx_err.FpxNullDataError, fpx_err.FpxParseError):
            if url:
                return url
            raise


_NOTICE_CHANNEL_ALIASES: dict[str, int] = {
    "email": 1,
    "push": 2,
    "telegram": 3,
}


def _resolve_notice_channel(channel: int | str) -> int:
    if isinstance(channel, bool):
        raise fpx_err.FpxValidateError(f"Неизвестный канал уведомлений: {channel}")
    if isinstance(channel, int):
        if channel in (1, 2, 3):
            return channel
        raise fpx_err.FpxValidateError(f"Неизвестный канал уведомлений: {channel}")
    key = str(channel).strip().lower()
    if key.isdigit():
        return _resolve_notice_channel(int(key))
    if key in _NOTICE_CHANNEL_ALIASES:
        return _NOTICE_CHANNEL_ALIASES[key]
    raise fpx_err.FpxValidateError(f"Неизвестный канал уведомлений: {channel}")


def _is_telegram_connect_url(url: str) -> bool:
    lowered = url.lower()
    return "t.me/" in lowered or "telegram.me/" in lowered or "telegram.org/" in lowered


def _header_value(headers: Any, name: str) -> str:
    if not headers:
        return ""
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    return str(getter(name) or getter(name.lower()) or "")
