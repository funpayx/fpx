from typing import Any, cast

from fpx.models.chat import Chat, ChatData, Message
from fpx.utils import errors as fpx_err


class ChatManager:
    def __init__(self, account: Any) -> None:
        # account: Account (см. fpx/classes/account/account.py). Оставлен как Any,
        # так как сам класс Account ещё не аннотирован (отдельная задача #20).
        self._account = account

    async def get_chats(self) -> list[Chat]:
        """
        Собирает все чаты на аккаунте.

        Returns:
            list[Chat]: Список объектов чатов. Каждый содержит:
                - id (str): ID чата (node_id).
                - username (str): Имя клиента.
                - last_msg (str): Последнее сообщение в чате.
                - date (str): Дата последнего сообщения.
                - link (str): Полная ссылка на чат.
                - is_unread (bool): Прочитано или нет (True, если не прочитано).

        Raises:
            FpxGetChatsError: Ошибка получения чатов FunPay

        """
        step = "запрос страницы чатов с FunPay"
        try:
            html = await self._account._client.get_chats_page()
            step = "парсинг данных чатов"
            chats = self._account._parser.parse_chats_list(html)
        except Exception as e:
            raise fpx_err.FpxGetChatsError(f"Не удалось выполнить {step}. Ошибка: {e}")
        return cast(list[Chat], chats)

    async def send_message(self, chat_id: str, text: str, with_nodes: bool = False) -> dict[str, Any]:
        """
        Отправляет сообщение.

        Args:
            chat_id (str): ID чата
            text (str): Текст сообщения
        Returns:
            dict: Словарь, которым отвечает фанпей
                в формате {'objects': [], 'response': {'error': None}},
                если требуется, можно проверять if .send_message() / if not .send_message
                при ошибке пункт Raises
        Raises:
            FpxMessageNotDelivered: Если не удалось отправить сообщение.

        """
        step = f"запрос данных чата ID {chat_id}"
        try:
            if chat_id not in self._account.data._node_names or not self._account.data._csrf_token:
                await self.get_chat_data(chat_id)
            step = f"POST запрос на отправку сообщения {text} в чат ID {chat_id}"
            response = await self._account._client.send_message_request(
                self._account.data._node_names[chat_id], -1, text
            )
        except Exception as e:
            raise fpx_err.FpxMessageDeliverError(f"Не удалось выполнить {step}. Ошибка: {e}")
        if response.get("error") is None:
            return cast(dict[str, Any], response)
        else:
            error_code = response.get("error", "400")
            error_msg = response.get("msg", "Неизвестная ошибка")
            raise fpx_err.FpxMessageDeliverError(f"Сервер вернул ошибку: {error_code} - {error_msg}")

    async def get_chat_data(self, chat_id: int | str, last_message_node_id: int | str | None = None) -> ChatData:
        """
        Получает данные чата.

        Args:
            chat_id (int | str): Айди чата

        Returns:
            ChatData: Объект с тех. данными чата:
                - node_name (str): Полный ID переписки, нужный для отправки сообщения (users-8778502-19903068)
                - csrf_token (str): Нужен для post запросов, сохраняется в кеш self.account._csrf_token
                - user_id (str): твой ID
                - Message: Объект, содержащий последнее сообщение в чате:
                    - chat_id (str): ID чата
                    - is_system (bool): Системное ли сообщение
                    - sender (str): Отправитель сообщения
                    - text (str): Текст сообщения
        Raises:
            FpxGetChatDataError: Ошибка запроса данных чата
        """
        try:
            stage = "запроса данных FunPay"
            html = await self._account._client.get_current_chat(chat_id)
            stage = "парсинга данных"
            data = self._account._parser.parse_chat(html)
        except Exception as e:
            raise fpx_err.FpxGetChatDataError(f"При выполнении {stage} произошла ошибка: {e}")
        good_msg_list: list[Message] = []
        if data.get("messages"):
            message_list = []
            for msg in data.get("messages"):
                message_list.append(
                    Message(
                        node_msg_id=msg.get("node_id"),
                        sender=msg.get("sender"),
                        text=msg.get("message"),
                        is_system=msg.get("is_system"),
                        chat_id=chat_id,
                    )
                )
            if not last_message_node_id:
                good_msg_list.append(message_list[-1])
            else:
                for msg in message_list:
                    if int(msg.node_msg_id) > int(last_message_node_id):
                        good_msg_list.append(msg)
        else:
            good_msg_list = []
        chat = ChatData(
            node_name=data["data-name"],
            csrf_token=data["csrf-token"],
            user_id=data["user-id"],
            last_messages=good_msg_list,
        )
        self._account.data._node_names[chat_id] = chat.node_name
        self._account.data._csrf_token = chat.csrf_token
        self._account.data.user_id = chat.user_id
        return chat

    async def send_image(self, chat_id: str | int, image_id: str | int) -> dict[str, Any]:
        """
        Отправка изображения в чат
        Args:
            chat_id (str): ID чата
            image_id (str): ID изображения на фанпей
                получить на fp.account.upload_image
        Returns:
            dict: Словарь, которым отвечает фанпей
                в формате {'objects': [], 'response': {'error': None}},
                если требуется, можно проверять if .send_message() / if not .send_message
                при ошибке пункт Raises
        Raises:
            FpxMessageNotDelivered: Если не удалось отправить сообщение.
        """
        step = f"запрос данных чата ID {chat_id}"
        try:
            if chat_id not in self._account.data._node_names or not self._account.data._csrf_token:
                await self.get_chat_data(chat_id)
            step = f"POST запрос на отправку изображения {image_id} в чат ID {chat_id}"
            response = await self._account._client.send_image_request(
                self._account.data._node_names[chat_id], -1, image_id
            )
        except Exception as e:
            raise fpx_err.FpxMessageDeliverError(f"Не удалось выполнить {step}. Ошибка: {e}")
        if response.get("error") is None:
            return cast(dict[str, Any], response)
        else:
            error_code = response.get("error", "400")
            error_msg = response.get("msg", "Неизвестная ошибка")
            raise fpx_err.FpxMessageDeliverError(f"Сервер вернул ошибку: {error_code} - {error_msg}")

    async def ban_chat(self, chat_id: int | str) -> bool:
        """
        Блокирует чат (кнопка «Заблокировать» в шапке чата FunPay).

        FunPay выполняет блокировку через ``POST /chat/mute`` с ``mute=1``.

        Args:
            chat_id (int | str): ID чата (node / data-id). Если передан
                системный ``users-...``, числовой ``data-id`` берётся со страницы чата.
        Returns:
            bool: True если чат заблокирован.
        Raises:
            FpxBanChatError: Не удалось заблокировать чат.
        """
        node_id = str(chat_id)
        step = f"блокировка чата ID {chat_id}"
        try:
            if not node_id.isdigit():
                step = f"запрос данных чата ID {chat_id}"
                html = await self._account._client.get_current_chat(chat_id)
                data = self._account._parser.parse_chat(html)
                parsed_id = data.get("data-id")
                if parsed_id:
                    node_id = str(parsed_id)
            step = f"POST запрос на блокировку чата ID {node_id}"
            response = await self._account._client.ban_chat(node_id)
        except Exception as e:
            raise fpx_err.FpxBanChatError(f"Не удалось выполнить {step}. Ошибка: {e}")
        if response.get("error") is None:
            return True
        error_code = response.get("error", "400")
        error_msg = response.get("msg", "Неизвестная ошибка")
        raise fpx_err.FpxBanChatError(f"Сервер вернул ошибку: {error_code} - {error_msg}")
