import asyncio
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any, Awaitable

from fpx.models.chat import Chat, Message
from fpx.utils import errors as fpx_err

logger = logging.getLogger("fpx.updates_runner")

# FunPay обрабатывает не больше 10 объектов за один запрос /runner/.
_MAX_OBJECTS = 10
# Сколько тиков догружать чат, если в ответе нет сообщения, которое уже видно в списке чатов.
_MAX_CHAT_ATTEMPTS = 3
# Такого тега у FunPay нет, поэтому объект chat_node всегда приходит с данными.
_EMPTY_TAG = "00000000"

_ORDER_HANDLERS = ("order", "new_order", "confirmed_order", "refund", "order_command")
_PURCHASE_HANDLERS = ("purchase", "new_purchase", "confirmed_purchase", "purchase_refund")


def _new_tag() -> str:
    """Случайный тег: FunPay пришлёт объект целиком, как клиенту без кеша."""
    return secrets.token_hex(4)


@dataclass
class _LoadedChat:
    """История чата из chat_node: все полученные сообщения и новые среди них."""

    chat: Chat
    found: bool
    node_name: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    new: list[dict[str, Any]] = field(default_factory=list)


class UpdatesRunner:
    """
    Приём событий через POST /runner/, как у самого сайта FunPay.

    На тике один запрос с объектами orders_counters (счётчики незавершённых продаж
    и покупок) и chat_bookmarks (последние чаты с ID последнего сообщения).
    FunPay возвращает только объекты, у которых сменился тег, поэтому в простое
    тик стоит один лёгкий JSON-запрос. Истории изменившихся чатов загружаются
    пачками chat_node, новые сообщения отбираются по ID.

    Страницы продаж, покупок и профиля загружаются только по сигналу: сменились
    счётчики или в чате появилось оповещение FunPay (оплата, подтверждение,
    возврат, отзыв), и только если на них есть хендлеры.
    """

    def __init__(self, runner: Any) -> None:
        # runner: Runner (см. fpx/classes/runner/runner.py). Оставлен как Any,
        # так как сам класс Runner ещё не аннотирован (отдельная задача #17).
        self.runner = runner
        self._tags: dict[str, str] = {}
        # Чаты, в которых список чатов показал новое сообщение, а история ещё не загружена.
        self._pending: dict[str, Chat] = {}
        self._attempts: dict[str, int] = {}
        # ID самого нового сообщения на момент запуска: всё, что старше, уже не событие.
        self._watermark = 0
        self._ready: set[str] = set()
        self._events_dirty = False

    async def _warm_up(self) -> None:
        """Запоминает текущее состояние чатов и страниц: события до запуска хендлерам не отдаются."""
        self._tags = {"orders_counters": _new_tag(), "chat_bookmarks": _new_tag()}
        self._pending.clear()
        self._attempts.clear()
        self._ready.clear()
        self.runner._chat._chat_last_ids.clear()
        # Страницы загружаются раньше /runner/: заказ, пришедший между запросами,
        # не попадёт в кеш, и повторная сверка на первом тике его найдёт.
        await self._sync_sources()
        _, chats = await self._poll()
        if chats is None:
            raise fpx_err.FpxGetUpdatesError("FunPay не вернул список чатов (chat_bookmarks)")
        for chat in chats:
            self.runner._chat._chat_last_ids[chat.id] = str(chat.node_msg_id)
        self._watermark = max((chat.node_msg_id for chat in chats), default=0)
        self._events_dirty = bool(self._ready)

    async def _check_updates(self) -> None:
        """Один тик: обновления, истории изменившихся чатов, сверка страниц по сигналу, хендлеры."""
        counters_changed, chats = await self._poll()
        if counters_changed:
            self._events_dirty = True
        if chats:
            self._collect_changed(chats)
        loaded = await self._load_pending()
        if any(message["is_system"] for item in loaded for message in item.new):
            self._events_dirty = True
        error: Exception | None = None
        if self._events_dirty:
            try:
                await self._sync_sources()
                self._events_dirty = False
            except Exception as e:
                error = e
        # Заказы раньше сообщений: если хендлер заказа выставит состояние FSM,
        # сообщение, пришедшее вместе с оплатой, обработается уже в нём.
        await asyncio.gather(*(self._dispatch_chat(item) for item in loaded))
        if error is not None:
            raise error

    async def _request(self, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            response = await self.runner._account._client.runner_request(objects)
            received = response["objects"]
            if not isinstance(received, list):
                raise TypeError(f"objects должен быть списком, пришло {type(received).__name__}")
        except fpx_err.FpxAccountError:
            raise
        except Exception as e:
            raise fpx_err.FpxGetUpdatesError(f"Запрос к /runner/ не удался: {e}") from e
        return [obj for obj in received if isinstance(obj, dict)]

    def _base_object(self, obj_type: str) -> dict[str, Any]:
        user_id = int(self.runner._account.data.user_id)
        return {"type": obj_type, "id": user_id, "tag": self._tags[obj_type], "data": False}

    async def _poll(self) -> tuple[bool, list[Chat] | None]:
        """
        Запрашивает счётчики заказов и список чатов.

        Returns:
            tuple: сменились ли счётчики; список чатов, если FunPay его прислал.
        """
        objects = [self._base_object("orders_counters"), self._base_object("chat_bookmarks")]
        counters_changed = False
        chats: list[Chat] | None = None
        for obj in await self._request(objects):
            obj_type = obj.get("type")
            if obj_type not in self._tags:
                continue
            tag = str(obj.get("tag") or "")
            if obj_type == "orders_counters":
                counters_changed = tag != self._tags[obj_type]
            else:
                data = obj.get("data")
                if isinstance(data, dict) and "html" in data:
                    chats = self.runner._account._parser.parse_chat_bookmarks(data["html"] or "")
            self._tags[obj_type] = tag or _new_tag()
        return counters_changed, chats

    def _threshold(self, chat_id: str) -> int:
        """ID сообщения, после которого сообщения чата считаются новыми."""
        last_id = self.runner._chat.get_last_id(chat_id)
        return int(last_id) if last_id else self._watermark

    def _collect_changed(self, chats: list[Chat]) -> None:
        for chat in chats:
            if chat.node_msg_id > self._threshold(chat.id):
                self._pending[chat.id] = chat

    def _chat_node(self, chat: Chat) -> dict[str, Any]:
        node: int | str = int(chat.id) if chat.id.isdigit() else chat.id
        last_id = self.runner._chat.get_last_id(chat.id)
        return {
            "type": "chat_node",
            "id": node,
            "tag": _EMPTY_TAG,
            "data": {"node": node, "last_message": int(last_id) if last_id else -1, "content": ""},
        }

    async def _load_pending(self) -> list[_LoadedChat]:
        """
        Загружает истории изменившихся чатов пачками chat_node.

        Здесь ничего не запоминается: если запрос упадёт, чаты останутся
        в очереди и загрузятся на следующем тике.
        """
        chats = list(self._pending.values())
        loaded: list[_LoadedChat] = []
        for start in range(0, len(chats), _MAX_OBJECTS):
            batch = chats[start : start + _MAX_OBJECTS]
            nodes: dict[str, dict[str, Any]] = {}
            for obj in await self._request([self._chat_node(chat) for chat in batch]):
                data = obj.get("data")
                if obj.get("type") != "chat_node" or not isinstance(data, dict):
                    continue
                node = data.get("node") or {}
                nodes[str(node.get("id", obj.get("id")))] = data
            loaded.extend(self._parse_node(chat, nodes.get(chat.id)) for chat in batch)
        return loaded

    def _parse_node(self, chat: Chat, data: dict[str, Any] | None) -> _LoadedChat:
        if data is None:
            return _LoadedChat(chat=chat, found=False)
        node = data.get("node") or {}
        node_name = str(node.get("name") or "") or None
        account = self.runner._account.data
        my_id = int(account.user_id)
        names = {my_id: account.username or ""}
        # Имя личного чата - users-<ID>-<ID>, второй ID - собеседник из списка чатов.
        for part in (node_name or "").split("-")[1:]:
            if part.isdigit() and int(part) != my_id:
                names[int(part)] = chat.username
        messages = self.runner._account._parser.parse_runner_messages(data.get("messages") or [], names)
        messages.sort(key=lambda message: message["node_id"])
        threshold = self._threshold(chat.id)
        new = [message for message in messages if message["node_id"] > threshold]
        return _LoadedChat(chat=chat, found=True, node_name=node_name, messages=messages, new=new)

    async def _dispatch_chat(self, item: _LoadedChat) -> None:
        chat = item.chat
        last_id = max([self._threshold(chat.id)] + [message["node_id"] for message in item.messages])
        if item.node_name:
            # send_message возьмёт имя отсюда и не будет загружать страницу чата.
            self.runner._account.data._node_names[chat.id] = item.node_name
        if last_id >= chat.node_msg_id:
            self._forget(chat.id)
        else:
            attempts = self._attempts.get(chat.id, 0) + 1
            if attempts < _MAX_CHAT_ATTEMPTS:
                self._attempts[chat.id] = attempts
            else:
                logger.warning(
                    f"В истории чата {chat.id} так и нет сообщения {chat.node_msg_id} из списка чатов, пропускаем его"
                )
                last_id = chat.node_msg_id
                self._forget(chat.id)
        self.runner._chat._chat_last_ids[chat.id] = str(last_id)
        for raw in item.new:
            # Оповещения FunPay (оплата, отзыв, возврат) приходят через хендлеры заказов и отзывов.
            if raw["is_system"]:
                continue
            message = Message(
                node_msg_id=raw["node_id"],
                sender=raw["sender"],
                chat_id=chat.id,
                text=raw["message"],
                is_system=False,
            )
            message._client = self.runner
            try:
                await self.runner._chat._trigger_message_handlers(message)
            except Exception as e:
                logger.debug(f"Ошибка при обработке сообщения в чате {chat.id}: {e}", exc_info=True)
                await self.runner._handle_error(event=message, exception=e)

    def _forget(self, chat_id: str) -> None:
        self._pending.pop(chat_id, None)
        self._attempts.pop(chat_id, None)

    def _sources(self) -> list[str]:
        """Страницы, которые нужны зарегистрированным хендлерам."""
        handlers = self.runner.router._handlers
        sources = []
        if any(handlers[name] for name in _ORDER_HANDLERS):
            sources.append("orders")
        if any(handlers[name] for name in _PURCHASE_HANDLERS):
            sources.append("purchases")
        if handlers["review"]:
            sources.append("reviews")
        return sources

    async def _sync_sources(self) -> None:
        results = await asyncio.gather(*(self._sync(source) for source in self._sources()), return_exceptions=True)
        errors = [result for result in results if isinstance(result, Exception)]
        for error in errors[1:]:
            await self.runner._handle_error(None, error)
        if errors:
            raise errors[0]

    async def _sync(self, source: str) -> None:
        """Сверяет страницу с кешем и отдаёт изменения хендлерам. Первая загрузка только заполняет кеш."""
        await self._source_step(source)
        self._ready.add(source)

    def _source_step(self, source: str) -> Awaitable[None]:
        ready = source in self._ready
        if source == "orders":
            order = self.runner._order
            return order._check_order_page() if ready else order._update_order_page_cache()
        if source == "purchases":
            purchase = self.runner._purchase
            return purchase._check_purchase_page() if ready else purchase._update_purchase_page_cache()
        review = self.runner._review
        return review._check_reviews() if ready else review._update_review_cache()
