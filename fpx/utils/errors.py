# Корневой родитель всех ошибок
class FpxError(Exception):
    """Базовое исключение для всего фреймворка."""

    def __init__(self, message: str = "Ошибка вызывана в fpx") -> None:
        self.message = message
        super().__init__(self.message)


# Второй уровень, с сортировкой по группам
class FpxAccountError(FpxError):
    """Ошибки, связанные с действиями аккаунта (запросы, лоты, заказы)."""

    def __init__(self, message: str = "Ошибка аккаунта") -> None:
        super().__init__(message)


class FpxParseError(FpxError):
    """Ошибки парсинга HTML/JSON от фп."""

    def __init__(self, message: str = "Ошибка парсинга данных") -> None:
        super().__init__(message)


class FpxRunnerError(FpxError):
    """Ошибки фонового раннера проверок."""

    def __init__(self, message: str = "Ошибка раннера") -> None:
        super().__init__(message)


class FpxHandlerError(FpxError):
    """Ошибки хендлера."""

    def __init__(self, message: str = "Ошибка хендлера") -> None:
        super().__init__(message)


# Третий уровень, конкретные ошибки


# аккаунт


class FpxRefreshCookieError(FpxAccountError):
    """Ошибка обновления куков"""

    def __init__(self, message: str = "Ошибка обновления куков") -> None:
        super().__init__(message)


class FpxValidateError(FpxAccountError):
    """Неверный объект"""

    def __init__(self, message: str = "Неверный объект.") -> None:
        super().__init__(message)


class FpxLotCreateError(FpxAccountError):
    """Не удалось создать лот"""

    def __init__(self, message: str = "Не удалось создать лот.") -> None:
        super().__init__(message)


class FpxAuthError(FpxAccountError):
    """Переданы неверные куки"""

    def __init__(self, message: str = "Переданы неверные куки.") -> None:
        super().__init__(message)


class FpxGetChatsError(FpxAccountError):
    """Не удалось запросить чаты."""

    def __init__(self, message: str = "Не удалось запросить чаты.") -> None:
        super().__init__(message)


class FpxMessageDeliverError(FpxAccountError):
    """Сообщение не было доставлено."""

    def __init__(self, message: str = "Сообщение не было доставлено") -> None:
        super().__init__(message)


class FpxRaisingLotError(FpxAccountError):
    """Ошибка при поднятии лотов."""

    def __init__(self, message: str = "Ошибка при поднятии лотов") -> None:
        super().__init__(message)


class FpxRefundError(FpxAccountError):
    """Ошибка при возврате денег за заказ."""

    def __init__(self, message: str = "Ошибка при возврате денег за заказ") -> None:
        super().__init__(message)


class FpxRequestError(FpxAccountError):
    """Превышено количество попыток запроса или сервер упал."""

    def __init__(self, message: str = "Превышено количество попыток запроса или сервер упал") -> None:
        super().__init__(message)


class FpxLotEditingError(FpxAccountError):
    """Ошибка при редактировании лота."""

    def __init__(self, message: str = "Ошибка при редактировании лота") -> None:
        super().__init__(message)


class FpxAnswerReviewError(FpxAccountError):
    """Ошибка при ответе на отзыв."""

    def __init__(self, message: str = "Ошибка ответа на отзыв") -> None:
        super().__init__(message)


class FpxDeleteReviewError(FpxAccountError):
    """Ошибка при удалении отзыва или ответа на отзыв."""

    def __init__(self, message: str = "Ошибка удаления отзыва") -> None:
        super().__init__(message)


class FpxClientNotAttachedError(FpxAccountError):
    """Объект контекста не привязан к главному клиенту fpx."""

    def __init__(self, message: str = "Объект не привязан к клиенту fpx и не может выполнять действия") -> None:
        super().__init__(message)


class FpxGetGameIDError(FpxAccountError):
    """Ошибка запроса айди игры"""

    def __init__(self, message: str = "Ошибка запроса айди игры") -> None:
        super().__init__(message)


class FpxGetLastCategoryLotError(FpxAccountError):
    """Ошибка запроса последнего лота в категории"""

    def __init__(self, message: str = "Ошибка запроса последнего лота в категории") -> None:
        super().__init__(message)


class FpxGetChatDataError(FpxAccountError):
    """Ошибка запроса данных чата"""

    def __init__(self, message: str = "Ошибка запроса данных чата") -> None:
        super().__init__(message)


class FpxBanChatError(FpxAccountError):
    """Ошибка при блокировке чата."""

    def __init__(self, message: str = "Не удалось заблокировать чат") -> None:
        super().__init__(message)


class FpxGetLotEditorInfoError(FpxAccountError):
    """Ошибка запроса данных редактора лота"""

    def __init__(self, message: str = "Ошибка запроса данных редактора лота") -> None:
        super().__init__(message)


class FpxGetLotInfoError(FpxAccountError):
    """Ошибка запроса данных лота"""

    def __init__(self, message: str = "Ошибка запроса данных лота") -> None:
        super().__init__(message)


class FpxGetOrderInfoError(FpxAccountError):
    """Ошибка запроса данных заказа"""

    def __init__(self, message: str = "Ошибка запроса данных заказа") -> None:
        super().__init__(message)


class FpxGetPurchaseInfoError(FpxAccountError):
    """Ошибка запроса данных покупки"""

    def __init__(self, message: str = "Ошибка запроса данных покупки") -> None:
        super().__init__(message)


class FpxGetUserDataError(FpxAccountError):
    """Ошибка запроса данных юзера"""

    def __init__(self, message: str = "Ошибка запроса данных юзера") -> None:
        super().__init__(message)


class FpxGetUserSellsError(FpxAccountError):
    """Ошибка запроса данных продаж юзера"""

    def __init__(self, message: str = "Ошибка запроса данных продаж юзера") -> None:
        super().__init__(message)


class FpxGetUserPurchasesError(FpxAccountError):
    """Ошибка запроса данных покупок юзера"""

    def __init__(self, message: str = "Ошибка запроса данных покупок юзера") -> None:
        super().__init__(message)


class FpxGetProfileError(FpxAccountError):
    """Ошибка запроса данных профиля юзера"""

    def __init__(self, message: str = "Ошибка запроса данных профиля юзера") -> None:
        super().__init__(message)


class FpxPostProfileError(FpxAccountError):
    """Ошибка отправки данных на профиль"""

    def __init__(self, message: str = "Не удалось отправить данные в профиль") -> None:
        super().__init__(message)


# --- Ошибки парсера ---
class FpxNullDataError(FpxParseError):
    """Парсер ожидал данные, но пришёл пустой тег или скелет страницы."""

    def __init__(self, message: str = "Парсер ожидал данные, но пришёл пустой тег или скелет страницы") -> None:
        super().__init__(message)


# --- Ошибки раннера ---
class FpxCriticalRunnerError(FpxRunnerError):
    """Критический сбой раннера, требующий остановки или жесткого перезапуска."""

    def __init__(self, message: str = "Критический сбой раннера, требующий остановки или жесткого перезапуска") -> None:
        super().__init__(message)


# --- Ошибки хендлера ---


class FpxAttributeError(FpxHandlerError):
    """Неправильно переданы аттрибуты."""

    def __init__(self, message: str = "Неправильно переданы аттрибуты") -> None:
        super().__init__(message)


class FpxCommandArgsError(FpxHandlerError):
    """Вызывается, когда функция команды ожидает аргументы, но в сообщении их передали меньше, чем нужно."""

    def __init__(self, function_name: str, missing_arg: str) -> None:
        self.function_name = function_name
        self.missing_arg = missing_arg
        super().__init__(f"Команда '{function_name}' ожидает аргумент '{missing_arg}', но он не был передан в чате.")
