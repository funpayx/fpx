from typing import Any

from fpx.models.lots import CurrentLotInfo, FieldOptions, LotCreationFields, LotEditor, LotField
from fpx.utils import errors as fpx_err


class LotManager:
    def __init__(self, account: Any) -> None:
        # account: Account (см. fpx/classes/account/account.py). Оставлен как Any,
        # так как типизация здесь через реальный класс Account создала бы
        # циклический импорт (Account -> LotManager -> Account).
        self._account = account

    async def _get_lot_editor_details(self, lot_id: int | str) -> LotEditor:
        """
        Не для обычного использования! (функция для изменения лота)
        Получает данные для изменения лота с https://funpay.com/lots/offerEdit?offer={lot_id}.

        Args:
            lot_id (str | int): Айди лота
        Returns:
            LotEditor: Возвращает объект с:
                - csrf_token (str): нужен для любого post запроса.
                - form_created_at (str): время создания формы изменения лота.
                - offer_id (str): Айди оффера(лота).
                - node_id (str): Айди нода.
                - location (str): Обычно пустой.
                - deleted (str): Обычно пустой.
                - fields (dict): Словарь с филдами, нет фиксированного кол-ва филдов, просто отправляйте все.
        Raises:
            FpxGetLotEditorInfoError: ошибка поулучения данных редактора
        """
        try:
            stage = "запроса данных с FunPay"
            html = await self._account._client.get_lot_editor_data(lot_id)
            stage = "парсинга данных"
            data = self._account._parser.parse_edit_lot_page(html)
        except Exception as e:
            raise fpx_err.FpxGetLotEditorInfoError(f"При выполнении {stage} произошла ошибка: {e}")
        base_fields = ["csrf_token", "form_created_at", "offer_id", "node_id", "location", "deleted"]
        main_data = {k: v for k, v in data.items() if k in base_fields}
        other_fields = {k: v for k, v in data.items() if k not in base_fields}
        lot = LotEditor(**main_data, fields=other_fields)
        return lot

    async def get_lot_secrets(self, lot_id: int | str) -> list[str]:
        """
        Запрос данных автовыдачи лота.

        Args:
            lot_id (int | str): ID лота
        Returns:
            list[str]: Список строк товаров автовыдачи.
        Raises:
            FpxGetLotInfoError: Ошибка запроса данных лота
        """
        try:
            stage = "запросе данных"
            data = await self._get_lot_editor_details(lot_id)
        except Exception as e:
            raise fpx_err.FpxGetLotInfoError(f"При {stage} произошла ошибка: {e}")
        return str(data.fields["secrets"]).split("\n")

    async def get_lot_info(self, lot_id: int | str) -> CurrentLotInfo:
        """
        Собирает данные лота.

        Args:
            lot_id (str | int): ID лота.
        Returns:
            CurrentLotInfo: Объект с этими данными:
                - short_desc (str): Краткое описание.
                - description (str): Полное описание.
                - price (float): Цена лота.
        Raises:
            FpxGetLotInfoError: Ошибка запроса данных лота
        """
        try:
            stage = "запроса данных"
            html = await self._account._client.get_lot_info(lot_id)
            stage = "парсинга данных"
            data = self._account._parser.parse_current_lot_menu(html)
            stage = "типизации данных"
            lot = CurrentLotInfo(
                id=str(lot_id),
                short_desc=data["short_desc"],
                description=data["description"],
                price=float(data["price"]),
            )
            lot._client = self._account
        except Exception as e:
            raise fpx_err.FpxGetLotInfoError(f"При выполнении {stage} произошла ошибка: {e}")
        return lot

    async def raise_lots(self) -> list[Any]:
        """
        Поднимает все лоты.

        Returns:
            list: Ответы от сервера.
        Raises:
            FpxRaisingLotError: Лот не поднят.
        """
        if not self._account.data._csrf_token:
            await self._account.profile.get_user_data()
        try:
            profile = await self._account.profile.profile()
            category_list = profile.category_ids
            if not category_list:
                raise fpx_err.FpxRaisingLotError("Нам нечего поднимать")
            response = []
            for node_id in category_list:
                game_id = await self._account.addons.get_game_id(node_id)
                response.append(await self._account._client.raise_lot(node_id, game_id))
            return response
        except Exception as e:
            raise fpx_err.FpxRaisingLotError(message=str(e))

    async def get_node_editor_data(self, node_id: int | str) -> LotCreationFields:
        """
        Запрос нужных филдов для создания лота

        Args:
            node_id (int | str): Айди категории лота
        Returns:
            LotCreationFields: Объект, который нужно редактировать
                встроенными в него функциями
                подробнее в https://fpx.readthedocs.io/ru/latest/lot_creator/
        Raises:
            FpxGetLotEditorInfoError: Ошибка запроса данных редактора лота
        """
        try:
            stage = "запроса данных с FunPay"
            html = await self._account._client.get_node_editor_data(node_id)
            stage = "парсинга данных"
            data = self._account._parser.parse_create_lot_page(html)
        except Exception as e:
            raise fpx_err.FpxGetLotEditorInfoError(f"При выполнении {stage} произошла ошибка: {e}")
        base_fields = ["csrf_token", "form_created_at", "offer_id", "node_id", "location", "deleted"]
        main_data = {f"_{k}": v for k, v in data.items() if k in base_fields}
        other_fields: list[LotField] = []
        for k, v in data.items():
            if k not in base_fields:
                field_options: list[FieldOptions] | None = None
                if v:
                    field_options = []
                    for option in v:
                        field_options.append(FieldOptions(key=list(option.values())[0], value=list(option.keys())[0]))
                other_fields.append(LotField(key=k, options=field_options))
        lot = LotCreationFields(fields=other_fields, **main_data)
        return lot

    async def create_lot(self, lot_creation_fields: LotCreationFields) -> bool:
        """
        Создание лота.
        Args:
            lot_creation_fields (LotCreationFields): Объект,
                получаемый в self.get_node_editor_data,
                и настраиваемый там же, подробнее о настройке
                в https://fpx.readthedocs.io/ru/latest/lot_creator/
        Returns:
            bool: True если всё удалось
        Raises:
            FpxLotCreateError: Создание лота не удалось
        """
        try:
            if not lot_creation_fields.validate():
                raise fpx_err.FpxValidateError(
                    "Не удалось валидировать объект,"
                    "Вы не передали что-то из этого списка:"
                    "self.price, self.amount, self.short_desc_ru, self.short_desc_en"
                    "где self это ваш объект LotCreationFields"
                )
            response = await self._account._client.create_lot(lot_creation_fields)
            if response.status_code == 200:
                return True
            else:
                raise fpx_err.FpxRequestError(f"Сервер не ответил успешно. Код ошибки: {response.status_code}")
        except Exception as e:
            raise fpx_err.FpxLotCreateError(f"При создании лота произошла ошибка: {e}")

    async def set_offers_hidden(self, hidden: bool) -> bool:
        """
        Массово скрывает или показывает все лоты аккаунта.

        FunPay: POST /trade/tradeLockSettings
        (`userId` текущего аккаунта, `mode=1` скрыть / `mode=0` показать).

        Args:
            hidden (bool): True — скрыть все лоты, False — показать.
        Returns:
            bool: True если запрос успешен.
        Raises:
            FpxAuthError: Неверные куки
            FpxLotEditingError: Не удалось изменить видимость лотов
        """
        if not self._account.data.user_id:
            await self._account.profile.get_user_data()
        user_id = self._account.data.user_id
        if not user_id:
            raise fpx_err.FpxLotEditingError("Не удалось получить ID пользователя")
        try:
            response = await self._account._client.set_offers_hidden(user_id, hidden)
            if response.status_code == 200:
                return True
            raise fpx_err.FpxRequestError(f"Сервер не ответил успешно. Код ошибки: {response.status_code}")
        except fpx_err.FpxAuthError:
            raise
        except Exception as e:
            raise fpx_err.FpxLotEditingError(f"При изменении видимости лотов произошла ошибка: {e}")
