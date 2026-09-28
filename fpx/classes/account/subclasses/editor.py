import asyncio
from typing import Any

from fpx.models.lots import LotEditor
from fpx.utils import errors as fpx_err


class FunPayEditor:
    def __init__(self, account: Any) -> None:
        # account: Account (см. fpx/classes/account/account.py). Оставлен как Any,
        # так как типизация здесь через реальный класс Account создала бы
        # циклический импорт (Account -> FunPayEditor -> Account).
        self._account = account

    async def _changing_lot_base(
        self, lot_id: int | str, lot: LotEditor, fining_fields: str | None, new_fields: str | int | None
    ) -> bool:
        response = await self._account._client.edit_lot(lot)
        if response.status_code == 200:
            await asyncio.sleep(0.5)
            try:
                new_lot = await self._account.lot._get_lot_editor_details(lot_id)
            except fpx_err.FpxGetLotEditorInfoError:
                if not fining_fields:
                    return True
                raise
            if str(new_lot.fields[fining_fields]) == str(new_fields):
                return True
            raise fpx_err.FpxLotEditingError("Данные лота на сайте остались старыми")
        raise fpx_err.FpxRequestError(f"Ошибка изменения лота. Статус: {response.json()}")

    async def change_lot_short_desc(self, lot_id: int | str, short_desc_ru: str, short_desc_en: str) -> bool:
        """
        Изменить краткое описание (название) лота.

        Args:
            lot_id (int | str): ID лота
            short_desc_ru (str): Название лота на русском
            short_desc_en (str): Название лота на английском
        Returns:
            bool: True если всё прошло успешно
        Raises:
            FpxLotEditingError: Название не изменилось
            FpxRequestError: Плохое соединение с интернетом/сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        lot.fields["fields[summary][ru]"] = short_desc_ru
        lot.fields["fields[summary][en]"] = short_desc_en
        return await self._changing_lot_base(lot_id, lot, "fields[summary][ru]", short_desc_ru)

    async def delete_lot(self, lot_id: str | int) -> bool:
        """
        Удаляет лот.

        Args:
            lot_id (str | int): ID лота

        Returns:
            bool: True если удалено успешно
        Raises:
            FpxLotEditingError: Лот не удалился
            FpxRequestError: Плохое соединение с интернетом/сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        lot.deleted = 1
        return await self._changing_lot_base(lot_id, lot, None, None)

    async def change_lot_desc(self, lot_id: str | int, description_ru: str, description_en: str) -> bool:
        """
        Изменить подробное описание лота.

        Args:
            lot_id (int | str): ID лота
            description_ru (str): Описание лота на русском
            description_en (str): Описание лота на английском
        Returns:
            bool: True если всё прошло успешно
        Raises:
            FpxLotEditingError: Описание не изменилось
            FpxRequestError: Плохое соединение с интернетом/сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        lot.fields["fields[desc][ru]"] = description_ru
        lot.fields["fields[desc][en]"] = description_en
        return await self._changing_lot_base(lot_id, lot, "fields[desc][ru]", description_ru)

    async def change_lot_amount(self, lot_id: int | str, new_amount: int | str) -> bool:
        """
        Меняет количество доступного товара в лоте

        Args:
            lot_id (str | int): ID лота
            new_amount (int | str): Новое кол-во лота
        Returns:
            bool: True если изменено успешно
        Raises:
            FpxLotEditingError: Наличие не изменилось
            FpxRequestError: Плохое соединение с интернетом/сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        lot.fields["amount"] = new_amount
        return await self._changing_lot_base(lot_id, lot, "amount", new_amount)

    async def change_payment_msg(self, lot_id: int | str, payment_msg_ru: str, payment_msg_en: str) -> bool:
        """
        Меняет сообщение после оплаты лота.

        Args:
            lot_id (str | int): ID лота
            payment_msg_ru (str): Новое сообщение после оплаты на русском
            payment_msg_en (str): Новое сообщение после оплаты на английском
        Returns:
            bool: True если изменено успешно
        Raises:
            FpxLotEditingError: Не удалось поменять лот
            FpxRequestError: Плохое соединение с интернетом/сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        lot.fields["fields[payment_msg][ru]"] = payment_msg_ru
        lot.fields["fields[payment_msg][en]"] = payment_msg_en
        return await self._changing_lot_base(lot_id, lot, "fields[payment_msg][ru]", payment_msg_ru)

    async def set_lot_secrets(self, lot_id: int | str, secrets: list[str], rewrite: bool = False) -> bool:
        """
        Обновить/Перезаписать данные автовыдачи лота.
        Посмотреть текущие данные можно FunPayTools.account.lot.get_lot_secrets().

        Args:
            lot_id (int | str): ID лота
            secrets (list[str]): Список товаров автовыдачи
            rewrite (bool) = False: False если добавить к текущей автовыдаче
                новый товар, True если перезаписать полностью
        Returns:
            bool: True - Данные обновлены.
        Raises:
            FpxLotEditingError: Секреты не изменились
            FpxRequestError: Плохое соединение с интернетом/сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        lot.fields["auto_delivery"] = "on"
        secret_str = "\n".join(secrets)
        if rewrite:
            lot.fields["secrets"] = secret_str
        else:
            secret_str = lot.fields.get("secrets", "") + "\n" + secret_str
            lot.fields["secrets"] = secret_str
        return await self._changing_lot_base(lot_id, lot, "secrets", secret_str)

    async def change_lot_price(self, lot_id: int | str, new_price: str) -> bool:
        """
        Изменяет цену лота.

        Args:
            lot_id (str | int): Айди лота
            new_price (str): Новая цена лота
        Returns:
            bool: True - цена изменилась.
        Raises:
            FpxLotEditingError: Цена не изменилась
            FpxRequestError: Плохое соединение с интернетом/сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        lot.fields["price"] = new_price
        return await self._changing_lot_base(lot_id, lot, "price", new_price)

    async def toggle_off_lot(self, lot_id: int | str) -> bool:
        """
        Выключает лот.

        Args:
            lot_id (str | int): Айди лота
        Returns:
            bool: True - лот выключен
        Raises:
            FpxRequestError: Сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        response = await self._account._client.edit_lot(lot, active=False)
        if response.status_code == 200:
            return True
        raise fpx_err.FpxRequestError("Ошибка отправки запроса на изменение деталей лота")

    async def toggle_on_lot(self, lot_id: int | str) -> bool:
        """
        Включает лот.

        Args:
            lot_id (str | int): Айди лота
        Returns:
            bool: True - лот включен
        Raises:
            FpxRequestError: Сервер не ответил
        """
        lot = await self._account.lot._get_lot_editor_details(lot_id)
        response = await self._account._client.edit_lot(lot, active=True)
        if response.status_code == 200:
            return True
        raise fpx_err.FpxRequestError("Ошибка отправки запроса на изменение деталей лота")
