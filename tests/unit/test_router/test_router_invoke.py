"""Доп. тесты Router.invoke: Dependency Injection и цепочка middleware."""

from typing import Any, Optional

import pytest

from fpx.classes.runner.subclasses.router import Router
from fpx.fsm import FSMContext
from fpx.models.chat import Message
from fpx.utils.dependencies import Dependency
from fpx.utils.storage.memory import MemoryStorage


@pytest.fixture
def router():
    return Router()


def make_message(text="hi"):
    return Message(node_msg_id=1, sender="User", chat_id="chat-1", text=text, is_system=False)


class TestInvokeEventBinding:
    @pytest.mark.asyncio
    async def test_binds_event_by_annotation(self, router):
        received = {}

        async def handler(msg: Message):
            received["msg"] = msg

        message = make_message()
        await router.invoke(handler, message)
        assert received["msg"] is message

    @pytest.mark.asyncio
    async def test_binds_fsm_context_by_annotation(self, router):
        received = {}
        storage = MemoryStorage()
        state_ctx = FSMContext(storage=storage, chat_id="chat-1")

        async def handler(msg: Message, state: FSMContext):
            received["state"] = state

        await router.invoke(handler, make_message(), state_ctx)
        assert received["state"] is state_ctx

    @pytest.mark.asyncio
    async def test_positional_args_fill_unannotated_params(self, router):
        received = {}

        async def handler(msg: Message, name, age):
            received["name"] = name
            received["age"] = age

        await router.invoke(handler, make_message(), None, args=["Bob", "25"])
        assert received == {"name": "Bob", "age": "25"}

    @pytest.mark.asyncio
    async def test_list_str_annotation_does_not_crash_invoke(self, router):
        received = {}

        async def handler(msg: Message, tags: list[str] | None = None):
            received["msg"] = msg
            received["tags"] = tags

        message = make_message()
        await router.invoke(handler, message)
        assert received["msg"] is message
        assert received["tags"] is None

    @pytest.mark.asyncio
    async def test_dict_annotation_is_filled_from_args(self, router):
        received = {}

        async def handler(msg: Message, meta: dict[str, int]):
            received["msg"] = msg
            received["meta"] = meta

        message = make_message()
        payload = {"n": 1}
        await router.invoke(handler, message, None, args=[payload])
        assert received["msg"] is message
        assert received["meta"] is payload

    @pytest.mark.asyncio
    async def test_optional_annotation_does_not_crash_invoke(self, router):
        received = {}

        async def handler(msg: Message, extra: Optional[str] = None):
            received["msg"] = msg
            received["extra"] = extra

        message = make_message()
        await router.invoke(handler, message)
        assert received["msg"] is message
        assert received["extra"] is None

    @pytest.mark.asyncio
    async def test_union_none_annotation_does_not_crash_invoke(self, router):
        received = {}

        async def handler(msg: Message, extra: Message | None = None):
            received["msg"] = msg
            received["extra"] = extra

        message = make_message()
        await router.invoke(handler, message)
        assert received["msg"] is message
        assert received["extra"] is None

    @pytest.mark.asyncio
    async def test_only_parameterized_annotations_do_not_crash_invoke(self, router):
        received = {}

        async def handler(tags: list[str] | None = None, extra: Optional[Message] = None):
            received["tags"] = tags
            received["extra"] = extra

        await router.invoke(handler, make_message())
        assert received == {"tags": None, "extra": None}

    @pytest.mark.asyncio
    async def test_typing_any_annotation_does_not_crash_invoke(self, router):
        received = {}

        async def handler(msg: Message, payload: Any = None):
            received["msg"] = msg
            received["payload"] = payload

        message = make_message()
        await router.invoke(handler, message)
        assert received["msg"] is message
        assert received["payload"] is None


class TestInvokeDependencyInjection:
    @pytest.mark.asyncio
    async def test_sync_one_arg_dependency_is_called_with_event(self, router):
        def get_service(ev):
            return f"service-for-{ev.sender}"

        received = {}

        async def handler(msg: Message, service=Dependency(get_service)):
            received["service"] = service

        await router.invoke(handler, make_message())
        assert received["service"] == "service-for-User"

    @pytest.mark.asyncio
    async def test_async_one_arg_dependency_is_called_with_event(self, router):
        async def get_service(ev):
            return f"async-{ev.sender}"

        received = {}

        async def handler(msg: Message, service=Dependency(get_service)):
            received["service"] = service

        await router.invoke(handler, make_message())
        assert received["service"] == "async-User"

    @pytest.mark.asyncio
    async def test_dependency_receiving_event(self, router):
        def get_sender(ev):
            return ev.sender

        received = {}

        async def handler(msg: Message, sender=Dependency(get_sender)):
            received["sender"] = sender

        await router.invoke(handler, make_message())
        assert received["sender"] == "User"

    @pytest.mark.asyncio
    async def test_sync_zero_arg_dependency_is_called_without_event(self, router):
        def get_config():
            return "plain-config"

        received = {}

        async def handler(msg: Message, config=Dependency(get_config)):
            received["config"] = config

        await router.invoke(handler, make_message())
        assert received["config"] == "plain-config"

    @pytest.mark.asyncio
    async def test_async_zero_arg_dependency_is_called_without_event(self, router):
        async def get_config():
            return "async-config"

        received = {}

        async def handler(msg: Message, config=Dependency(get_config)):
            received["config"] = config

        await router.invoke(handler, make_message())
        assert received["config"] == "async-config"

    @pytest.mark.asyncio
    async def test_zero_arg_dependency_does_not_raise_typeerror(self, router):
        """0-arg зависимость не должна получать event — иначе TypeError."""
        calls = []

        def get_token():
            calls.append("called")
            return "secret"

        received = {}

        async def handler(msg: Message, token=Dependency(get_token)):
            received["token"] = token

        await router.invoke(handler, make_message())
        assert received["token"] == "secret"
        assert calls == ["called"]

    @pytest.mark.asyncio
    async def test_async_gen_dependency_is_closed_after_call(self, router):
        closed = {"value": False}

        async def get_resource(ev):
            try:
                yield "resource"
            finally:
                closed["value"] = True

        received = {}

        async def handler(msg: Message, res=Dependency(get_resource)):
            received["res"] = res

        await router.invoke(handler, make_message())
        assert received["res"] == "resource"
        assert closed["value"] is True

    @pytest.mark.asyncio
    async def test_async_gen_zero_arg_dependency_is_called_without_event(self, router):
        closed = {"value": False}

        async def get_resource():
            try:
                yield "zero-arg-resource"
            finally:
                closed["value"] = True

        received = {}

        async def handler(msg: Message, res=Dependency(get_resource)):
            received["res"] = res

        await router.invoke(handler, make_message())
        assert received["res"] == "zero-arg-resource"
        assert closed["value"] is True


class TestMiddlewareChain:
    @pytest.mark.asyncio
    async def test_middleware_wraps_handler_call(self, router):
        call_order = []

        @router.middleware()
        async def logging_mw(event, call_next):
            call_order.append("before")
            result = await call_next(event)
            call_order.append("after")
            return result

        async def handler(msg: Message):
            call_order.append("handler")

        await router.invoke(handler, make_message())
        assert call_order == ["before", "handler", "after"]

    @pytest.mark.asyncio
    async def test_multiple_middlewares_run_in_registration_order(self, router):
        call_order = []

        @router.middleware()
        async def mw1(event, call_next):
            call_order.append("mw1-before")
            await call_next(event)
            call_order.append("mw1-after")

        @router.middleware()
        async def mw2(event, call_next):
            call_order.append("mw2-before")
            await call_next(event)
            call_order.append("mw2-after")

        async def handler(msg: Message):
            call_order.append("handler")

        await router.invoke(handler, make_message())
        assert call_order == ["mw1-before", "mw2-before", "handler", "mw2-after", "mw1-after"]

    @pytest.mark.asyncio
    async def test_middleware_can_short_circuit(self, router):
        called = {"handler": False}

        @router.middleware()
        async def blocking_mw(event, call_next):
            return None  # не вызываем call_next

        async def handler(msg: Message):
            called["handler"] = True

        await router.invoke(handler, make_message())
        assert called["handler"] is False


class TestIncludeRouterUnknownEventTypeIgnored:
    def test_unknown_event_types_are_skipped(self, router):
        sub = Router()
        sub._handlers["unknown_type"] = ["whatever"]
        router.include_router(sub)
        assert "unknown_type" not in router._handlers
