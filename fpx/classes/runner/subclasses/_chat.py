import asyncio
import inspect
import logging
import re
from typing import Any, Callable

from fpx.fsm import FSMContext
from fpx.models.chat import Message
from fpx.utils import errors as fpx_err
from fpx.utils.formatting import safe_format

logger = logging.getLogger("fpx.chat_runner")


class ChatRunner:
    def __init__(self, runner: Any) -> None:
        # runner: Runner (см. fpx/classes/runner/runner.py). Оставлен как Any,
        # так как сам класс Runner ещё не аннотирован (отдельная задача #17).
        self.runner = runner
        self._chat_last_ids: dict[str | int, str] = {}

    def _compare_chat_cache(self) -> list[Message]:
        """
        Сравнивает старый кеш сообщений с новым, если находит отличия,
        выносит сообщение в список,
        после чего возвращает полный список.

        Текст превью не фильтруется: по нему не отличить оповещение FunPay
        от сообщения покупателя с теми же словами («я оплатил заказ»).
        Оповещения отсекаются после загрузки чата, по флагу is_system.
        """
        result: list[Message] = []
        if self.runner._cache["msgs"] != self.runner._cache["old_msgs"]:
            for message in self.runner._cache["msgs"]:
                if message not in self.runner._cache["old_msgs"]:
                    result.append(
                        Message(
                            node_msg_id=message["last_msg"]["node_id"],
                            sender=message["sender"],
                            chat_id=message["chat_id"],
                            text=message["last_msg"]["message"],
                            is_system=False,
                        )
                    )
        return result

    async def _update_chat_cache(self) -> None:
        """
        Обновляет кеш последних чатов
        """
        chats = await self.runner._account.chat.get_chats()
        result = []
        for chat in chats:
            chat = {
                "sender": chat.username,
                "chat_id": chat.id,
                "last_msg": {"node_id": chat.node_msg_id, "message": chat.last_msg},
            }
            result.append(chat)
        self.runner._cache["old_msgs"] = self.runner._cache["msgs"]
        self.runner._cache["msgs"] = result

    async def _process_message(self, message: Message, state_ctx: FSMContext) -> bool:
        if not message.text:
            return False
        full_text = message.text.lower().strip()
        for cmd_handler in self.runner.router._handlers["commands"]:
            target_command = cmd_handler["command"]
            for cmd_text, target_function in target_command.items():
                cmd_lower = cmd_text.lower()
                if full_text == cmd_lower or full_text.startswith(cmd_lower + " "):
                    args_str = full_text[len(cmd_lower) :].strip()
                    args = args_str.split() if args_str else []
                    sig = inspect.signature(target_function)
                    text_param_names = [
                        name
                        for name, param in sig.parameters.items()
                        if param.annotation is str and param.default is inspect.Parameter.empty
                    ]
                    if len(args) < len(text_param_names):
                        missing_param = text_param_names[len(args)]
                        await self.runner._handle_error(
                            message, fpx_err.FpxCommandArgsError(target_function.__name__, missing_param)
                        )
                        return False
                    await self.runner.router.invoke(target_function, message, state_ctx, args=args)
                    return True
        return False

    def _check_text_filter(self, msg_text: str, filter_text: str | None, mapping: Any) -> bool:
        if filter_text is None:
            return True
        if isinstance(filter_text, str) and msg_text.startswith(filter_text.lower()):
            return True
        return False

    def _check_contains_filter(self, msg_text: str, h_filter: str | list[str] | None) -> bool:
        if isinstance(h_filter, str):
            h_filter = [h_filter]
        if h_filter is not None:
            for element in h_filter:
                if element.lower() in msg_text:
                    return True
            return False
        return True

    def _check_regex(self, msg_text: str, h_regex: str | list[str] | None) -> bool:
        if isinstance(h_regex, str):
            h_regex = [h_regex]
        if h_regex is not None:
            for element in h_regex:
                if re.search(element, msg_text):
                    return True
            return False
        return True

    def _chat_id_check(self, msg: Message, h_chat_id: str | int | list[str | int] | None) -> bool:
        if isinstance(h_chat_id, str | int):
            h_chat_id = [h_chat_id]
        if h_chat_id is not None:
            for element in h_chat_id:
                if element == msg.chat_id:
                    return False
            return True
        return True

    def _sender_check(self, msg: Message, h_sender: str | int | list[str | int] | None) -> bool:
        if isinstance(h_sender, str | int):
            h_sender = [h_sender]
        if h_sender is not None:
            for element in h_sender:
                if element == msg.sender:
                    return False
            return True
        return True

    async def _custom_check(self, msg: Message, h_custom: Callable[[Message], Any] | None) -> bool:
        if h_custom is not None:
            if asyncio.iscoroutinefunction(h_custom):
                is_match = await h_custom(msg)
            else:
                is_match = h_custom(msg)
            if is_match:
                return True
            return False
        return True

    async def _check_filters(self, message: Message, handler: dict[str, Any]) -> bool:
        msg_text = message.text.lower()
        if not self._check_text_filter(msg_text, handler["filter_text"], handler["mapping"]):
            return False
        if not self._check_contains_filter(msg_text, handler["contains"]):
            return False
        if not self._check_regex(msg_text, handler["regex"]):
            return False
        if not self._chat_id_check(message, handler["ignore_chat_id"]):
            return False
        if not self._sender_check(message, handler["ignore_sender"]):
            return False
        if not await self._custom_check(message, handler["custom"]):
            return False
        return True

    async def _trigger_message_handlers(self, message: Message) -> None:
        if self.runner._account.data.username is None:
            await self.runner._account.profile.get_user_data()
        if self.runner._account.data.username == message.sender:
            return
        msg_text = message.text.lower() if message.text else message.text
        current_state = await self.runner.storage.get_state(message.chat_id)
        state_ctx = FSMContext(storage=self.runner.storage, chat_id=message.chat_id)
        try:
            if await self._process_message(message, state_ctx):
                return
        except Exception as e:
            logger.debug(f"Ошибка при обработке сообщения: {e}", exc_info=True)
            await self.runner._handle_error(event=message, exception=e)
            return
        for handler in self.runner.router._handlers["message"]:
            if handler["state"] != current_state:
                continue
            if not await self._check_filters(message, handler):
                continue
            if handler["mapping"] is not None:
                matched = False
                for trigger, reply in handler["mapping"].items():
                    if msg_text.startswith(trigger.lower()):
                        formatted_reply = safe_format(
                            reply, sender=message.sender, chat_id=message.chat_id, text=message.text
                        )
                        await message.answer(formatted_reply)
                        matched = True
                        break
                if not matched:
                    continue
            await self.runner.router.invoke(handler["function"], message, state_ctx)
            break

    def get_last_id(self, chat_id: str | int) -> str | None:
        return self._chat_last_ids.get(chat_id)

    def _previous_last_ids(self) -> dict[str | int, int]:
        """ID последнего сообщения каждого чата на прошлом тике."""
        return {
            chat["chat_id"]: int(chat["last_msg"]["node_id"])
            for chat in self.runner._cache["old_msgs"]
            if chat["last_msg"]["node_id"]
        }

    async def _check_chats(self) -> None:
        await self._update_chat_cache()
        chats = self._compare_chat_cache()
        if chats:
            previous = self._previous_last_ids()
            # Чата не было в прошлом снимке: новое в нём всё, что новее самого старого
            # известного сообщения. ID сообщений FunPay сквозные, так же считает FunPayCardinal.
            watermark = min(previous.values(), default=0)

            async def process_single_chat(chat_cache_obj: Message) -> None:
                chat_msg = None
                try:
                    chat_id = chat_cache_obj.chat_id
                    last_node_id = self.get_last_id(chat_id) or previous.get(chat_id) or watermark
                    if last_node_id and chat_id not in self._chat_last_ids:
                        # Точка отсчёта запоминается до запроса: если он упадёт, следующая попытка
                        # начнёт с неё, а не со снимка, в котором эти сообщения уже учтены.
                        self._chat_last_ids[chat_id] = str(last_node_id)
                    msg_obj = await self.runner._account.chat.get_chat_data(chat_id, last_node_id)
                    messages = msg_obj.last_messages
                    for message in messages:
                        if message is None:
                            return
                        # Оповещения FunPay (оплата, отзыв, возврат) приходят через раннеры заказов и отзывов.
                        if int(message.node_msg_id) > int(last_node_id) and not message.is_system:
                            # stop_list = ['изображение', 'image', 'зображення']
                            text = message.text
                            chat_msg = Message(
                                node_msg_id=message.node_msg_id,
                                sender=message.sender,
                                chat_id=chat_cache_obj.chat_id,
                                text=text,
                                is_system=message.is_system,
                            )
                            chat_msg._client = self.runner
                            await self._trigger_message_handlers(chat_msg)
                    if messages:
                        new_max_id = max(int(m.node_msg_id) for m in messages)
                        self._chat_last_ids[chat_cache_obj.chat_id] = str(new_max_id)
                except Exception as e:
                    logger.debug(f"Ошибка при параллельной обработке чата {chat_cache_obj.chat_id}: {e}", exc_info=True)
                    await self.runner._handle_error(event=chat_msg, exception=e)

            tasks = [process_single_chat(chat) for chat in chats]
            await asyncio.gather(*tasks)
