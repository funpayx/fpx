"""Хендлеры из модуля с `from __future__ import annotations`: все аннотации здесь - строки."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.runner.subclasses._chat import ChatRunner
from fpx.classes.runner.subclasses.router import Router, handler_signature
from fpx.fsm import FSMContext
from fpx.models.chat import Message
from fpx.utils import errors as fpx_err
from fpx.utils.dependencies import Dependency
from fpx.utils.storage.memory import MemoryStorage

if TYPE_CHECKING:
    from decimal import Decimal


def make_message(text: str = "hello") -> Message:
    return Message(node_msg_id=1, sender="User", chat_id="chat-1", text=text, is_system=False)


@pytest.fixture
def chat_runner() -> ChatRunner:
    runner = MagicMock()
    runner._handle_error = AsyncMock()
    runner.router = Router()
    return ChatRunner(runner)


class TestRouterInvoke:
    @pytest.mark.asyncio
    async def test_event_is_injected_by_string_annotation(self):
        seen: list[Message] = []

        async def handler(message: Message) -> None:
            seen.append(message)

        message = make_message()
        await Router().invoke(handler, message)
        assert seen == [message]

    @pytest.mark.asyncio
    async def test_fsm_context_is_injected_by_string_annotation(self):
        seen: list[FSMContext] = []

        async def handler(message: Message, state: FSMContext) -> None:
            seen.append(state)

        ctx = FSMContext(storage=MemoryStorage(), chat_id="chat-1")
        await Router().invoke(handler, make_message(), ctx)
        assert seen == [ctx]

    @pytest.mark.asyncio
    async def test_event_is_injected_next_to_type_checking_only_annotation(self):
        """Decimal есть только под TYPE_CHECKING, но message всё равно подставляется."""
        seen: list[tuple[Message, int]] = []

        async def get_balance() -> Decimal:
            return 0

        async def handler(message: Message, balance: Decimal = Dependency(get_balance)) -> None:
            seen.append((message, balance))

        message = make_message()
        await Router().invoke(handler, message)
        assert seen == [(message, 0)]


class TestCommands:
    @pytest.mark.asyncio
    async def test_missing_text_arg_is_reported(self, chat_runner):
        async def greet(message: Message, name: str) -> None:
            pass

        chat_runner.runner.router._handlers["commands"] = [{"command": {"/greet": greet}}]
        result = await chat_runner._process_message(make_message("/greet"), None)
        assert result is False
        error = chat_runner.runner._handle_error.await_args.args[1]
        assert isinstance(error, fpx_err.FpxCommandArgsError)

    @pytest.mark.asyncio
    async def test_text_arg_is_passed(self, chat_runner):
        received: dict[str, str] = {}

        async def greet(message: Message, name: str) -> None:
            received["name"] = name

        chat_runner.runner.router._handlers["commands"] = [{"command": {"/greet": greet}}]
        assert await chat_runner._process_message(make_message("/greet Bob"), None) is True
        assert received == {"name": "bob"}


class TestHandlerSignature:
    def test_unresolvable_annotation_stays_string(self):
        """Невычислимая аннотация остаётся строкой и не мешает остальным параметрам."""

        async def handler(message: Message, extra: NotImportedAnywhere) -> None:  # noqa: F821
            pass

        signature = handler_signature(handler)
        assert signature.parameters["message"].annotation is Message
        assert signature.parameters["extra"].annotation == "NotImportedAnywhere"
