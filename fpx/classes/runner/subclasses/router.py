import asyncio
import inspect
from typing import Any, Awaitable, Callable, Optional, get_origin

from fpx.fsm import FSMContext
from fpx.models.chat import Message
from fpx.utils.dependencies import Dependency

HandlerFunc = Callable[..., Any]
Decorator = Callable[[HandlerFunc], HandlerFunc]
Middleware = Callable[[Any, Callable[[Any], Awaitable[Any]]], Awaitable[Any]]


def _call_dependency(dep_func: Callable[..., Any], ev: Any) -> Any:
    """Вызывает зависимость: без аргументов, если сигнатура пустая, иначе с event."""
    if len(inspect.signature(dep_func).parameters) == 0:
        return dep_func()
    return dep_func(ev)


class Router:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Any]] = {
            "message": [],
            "order": [],
            "confirmed_order": [],
            "new_order": [],
            "refund": [],
            "review": [],
            "lot_category": [],
            "chip_category": [],
            "commands": [],
            "error": [],
            "order_command": [],
            "purchase": [],
            "confirmed_purchase": [],
            "new_purchase": [],
            "purchase_refund": [],
            # системные
            "startup": [],
            "flood": [],
        }
        self._middlewares: list[Middleware] = []

    def middleware(self) -> Callable[[Middleware], Middleware]:
        """Декоратор регистрации мидлваря"""

        def decorator(func: Middleware) -> Middleware:
            self._middlewares.append(func)
            return func

        return decorator

    async def invoke(
        self,
        h_func: HandlerFunc,
        event: Any,
        state_ctx: Optional[FSMContext] = None,
        args: Optional[list[Any]] = None,
    ) -> None:
        """Вызывает хендлер"""
        generators_to_close: list[Any] = []

        async def endpoint(ev: Any) -> None:
            sig = inspect.signature(h_func)
            kwargs: dict[str, Any] = {}
            arg_index = 0
            nonlocal generators_to_close
            for param_name, param in sig.parameters.items():
                annotation = param.annotation
                # get_origin() is not None for list[str], Optional[X], Message | None, etc.
                # isinstance() still TypeError-s on typing.Any and other special forms.
                if annotation is not inspect.Parameter.empty and get_origin(annotation) is None:
                    try:
                        matches_event = isinstance(ev, annotation)
                    except TypeError:
                        matches_event = False
                    if matches_event:
                        kwargs[param_name] = ev
                        continue
                if state_ctx and param.annotation == FSMContext:
                    kwargs[param_name] = state_ctx
                    continue
                if isinstance(param.default, Dependency):
                    dep_func = param.default.dependency
                    if inspect.isasyncgenfunction(dep_func):
                        gen = _call_dependency(dep_func, ev)
                        try:
                            resolved_val = await anext(gen)
                            kwargs[param_name] = resolved_val
                            generators_to_close.append(gen)
                        except StopAsyncIteration:
                            pass
                    elif asyncio.iscoroutinefunction(dep_func):
                        kwargs[param_name] = await _call_dependency(dep_func, ev)
                    else:
                        kwargs[param_name] = _call_dependency(dep_func, ev)
                    continue
                if args and param.default is inspect.Parameter.empty:
                    if arg_index < len(args):
                        kwargs[param_name] = args[arg_index]
                        arg_index += 1
            await h_func(**kwargs)

        call_next: Callable[[Any], Awaitable[Any]] = endpoint
        for mw in reversed(self._middlewares):

            async def make_next(
                mw: Middleware = mw, next_: Callable[[Any], Awaitable[Any]] = call_next
            ) -> Callable[[Any], Awaitable[Any]]:
                async def call(ev: Any) -> Any:
                    return await mw(ev, next_)

                return call

            call_next = await make_next()
        try:
            await call_next(event)
        finally:
            for gen in generators_to_close:
                try:
                    await gen.aclose()
                except Exception:
                    pass

    def include_router(self, router: "Router") -> None:
        """Метод для подключения плагинов и сторонних роутеров"""
        for event_type, funcs in router._handlers.items():
            if event_type in self._handlers:
                self._handlers[event_type].extend(funcs)

    def order_targets(self, target_dict: dict[str, Any]) -> None:
        """
        Метод для регистрации команд автоматизации новых заказов.

        Args:
            target_dict (dict): Словарь вида {'target': answer_new_def, 'моя пометка в описании': another_func}
        """
        self._handlers["order_command"].append({"trigger_command": target_dict})

    def message_commands(self, command_dict: dict[str, Any]) -> None:
        """
        Метод для регистрации команд автоматизации сообщений.

        Args:
            target_dict (dict): Словарь вида {'command': answer_new_def, '!start': another_func}
        """
        self._handlers["commands"].append({"command": command_dict})

    def on_error(self) -> Decorator:
        """Декоратор для отлова ошибок"""

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["error"].append(func)
            return func

        return decorator

    def on_message(
        self,
        text: str | None = None,
        contains: str | list[str] | None = None,
        regex: str | list[str] | None = None,
        custom: Callable[["Message"], bool | Awaitable[bool]] | None = None,
        mapping: dict[str, str] | None = None,
        state: str | None = None,
        ignore_chat_id: str | int | list[str | int] | None = None,
        ignore_sender: str | list[str] | None = None,
        priority: int = 0,
    ) -> Decorator:
        r"""Декоратор отслеживает новые сообщения.
        Важно что если сделать несколько хендлеров с одинаковыми фильтрами, то подходящее
        сообщение будет вызвано только под первый хендлер.

        Внимание: если пользователь отправит два одинаковых сообщения подряд -
        второе детектировано не будет, так как кеш не изменился. Это намеренное
        поведение для защиты от спама.

        Args:
            - text (str | None): Срабатывает, если сообщение НАЧИНАЕТСЯ с этого текста.
                Регистр игнорируется - 'Привет' и 'привет' равнозначны.
            - contains (str | list | None): Срабатывает, если в сообщении
                есть эти ключевые слова (можно строку или список слов).
            - regex (str | list | None): Фильтр по регуляркам (re.search).
                Ест сырые строки типа r'^id\d+$' или список паттернов.
            - custom (Callable | None): Твоя кастомная проверка.
                Сюда можно закинуть лямбду или синхронную/асинхронную функцию, которая возвращает True/False.
            - mapping (dict | None): Умный автоответчик.
                Передаешь словарь {'триггер': 'ответ'}, и скрипт сам ответит за тебя, подставив переменные.
            - state (str | None): Фильтр по состоянию FSM.
                Хендлер сработает только если текущий стейт чата совпадает с этим.
            - ignore_chat_id (str | int | list | None): Черный список для чатов.
                Айдишники отсюда скрипт будет просто игнорить (одиночный ID или список).
            - ignore_sender (str | list | None): Черный список для юзеров. Скрипт проигнорит сообщения от них.
            - priority (int | None): Приоритет декоратора, чем выше тем раньше проверяется (12 проверит раньше чем 11)

        Returns:
            Message: Объект, содержащий:
                - sender (str): Имя отправителя
                - chat_id (str): Айди чата (node id)
                - text (str): Сообщение, которое было отправлено в этом чате
                - is_system (bool): Системное ли сообщение
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["message"].append(
                {
                    "function": func,
                    "filter_text": text,
                    "contains": contains,
                    "regex": regex,
                    "custom": custom,
                    "mapping": mapping,
                    "state": state,
                    "ignore_chat_id": ignore_chat_id,
                    "ignore_sender": ignore_sender,
                    "priority": priority,
                }
            )
            self._handlers["message"].sort(key=lambda h: h["priority"], reverse=True)
            return func

        return decorator

    def on_orders(self, mapping: list[str] | None = None) -> Decorator:
        """
        Декоратор отслеживает все события заказов.
        Не рекомендуется использовать вместе с on_cofirmed_orders, on_new_order, on_refunded_orders
        во избежание дублирования событий.

        Returns:
            Order: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - description (str): Описание лота
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        if isinstance(mapping, str):
            mapping = [mapping]

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["order"].append({"function": func, "mapping": mapping})
            return func

        return decorator

    def on_confirmed_orders(self, mapping: list[str] | str | None = None) -> Decorator:
        """
        Декоратор, который отслеживает только событие подтверждёния заказа.

        Returns:
            Order: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        mapping = [mapping] if isinstance(mapping, str) else mapping

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["confirmed_order"].append({"function": func, "mapping": mapping})
            return func

        return decorator

    def on_new_order(self, mapping: list[str] | str | None = None) -> Decorator:
        """
        Декоратор, который отслеживает только новые заказы.

        Returns:
            Order: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        mapping = [mapping] if isinstance(mapping, str) else mapping

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["new_order"].append({"function": func, "mapping": mapping})
            return func

        return decorator

    def on_new_review(self, stars: int | None = None) -> Decorator:
        """Декоратор отслеживает новые отзывы.

        Args:
            - stars (int | None): Количество звёзд, на которое хендлер будет реагировать (не обязательно передавать).

        Returns:
            CurReview: Объект, содержащий:
                - text (str): Текст отзыва
                - stars (int): Кол-во звёзд, оставленных под отзывом
                - author (str): Автор отзыва
                - item_name (str): Заказ, под которым оставлен отзыв
        """

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["review"].append({"function": func, "stars": stars})
            return func

        return decorator

    def on_refunded_orders(self, mapping: list[str] | str | None = None) -> Decorator:
        """
        Декоратор отслеживает события возврата заказов.

        Returns:
            Order: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        mapping = [mapping] if isinstance(mapping, str) else mapping

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["refund"].append({"function": func, "mapping": mapping})
            return func

        return decorator

    def on_lot_category(self) -> Decorator:
        """
        Декоратор отслеживает снижение цен на лоты.

        Returns:
            CategoryLastLot: Объект, содержащий:
                - price (float): Цена лота
                - offer_id (str): Айди лота
        """

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["lot_category"].append(func)
            return func

        return decorator

    def on_chip_category(self) -> Decorator:
        """
        Декоратор отслеживает снижение цен на чипсах(коротких лотов под валюты).

        Returns:
            CategoryLastLot: Объект, содержащий:
                - price (float): Цена лота
                - offer_id (str): Айди лота
        """

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["chip_category"].append(func)
            return func

        return decorator

    def on_startup(self) -> Decorator:
        """Декоратор отслеживает запуск раннера"""

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["startup"].append(func)
            return func

        return decorator

    def on_flood(self) -> Decorator:
        """Декоратор отслеживает флуд в системе"""

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["flood"].append(func)
            return func

        return decorator

    def on_purchases(self, mapping: list[str] | None = None) -> Decorator:
        """
        Декоратор отслеживает все события покупок.
        Не рекомендуется использовать вместе с on_cofirmed_purchases, on_new_purchase, on_refunded_purchases
        во избежание дублирования событий.

        Returns:
            Purchase: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - description (str): Описание лота
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        if isinstance(mapping, str):
            mapping = [mapping]

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["purchase"].append({"function": func, "mapping": mapping})
            return func

        return decorator

    def on_confirmed_purchases(self, mapping: list[str] | str | None = None) -> Decorator:
        """
        Декоратор, который отслеживает только событие подтверждёния покупки.

        Returns:
            Purchase: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        mapping = [mapping] if isinstance(mapping, str) else mapping

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["confirmed_purchase"].append({"function": func, "mapping": mapping})
            return func

        return decorator

    def on_new_purchase(self, mapping: list[str] | str | None = None) -> Decorator:
        """
        Декоратор, который отслеживает только новые покупки.

        Returns:
            Purchase: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        mapping = [mapping] if isinstance(mapping, str) else mapping

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["new_purchase"].append({"function": func, "mapping": mapping})
            return func

        return decorator

    def on_refunded_purchase(self, mapping: list[str] | str | None = None) -> Decorator:
        """
        Декоратор отслеживает события возврата покупок.

        Purchase:
            Order: Объект, содержащий:
                - order_id (str): Уникальный ID заказа
                - order_time (str): Время оплаты заказа
                - client_name (str): Имя клиента
                - price (str): Цена товара
                - status (str): Статус заказа
                - name (str): Название товара
                - answer (method): При указании текста в аргументах, отвечает на сообщение
        """
        mapping = [mapping] if isinstance(mapping, str) else mapping

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers["purchase_refund"].append({"function": func, "mapping": mapping})
            return func

        return decorator
