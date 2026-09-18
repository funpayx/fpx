"""Тесты Runner — оркестрация фонового опроса, кеш, обработка ошибок."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from fpx.classes.runner.runner import Runner
from fpx.utils import errors as fpx_err


@pytest.fixture
def account():
    return MagicMock()


@pytest.fixture
def runner(account):
    return Runner(account)


class TestRunnerInit:
    def test_default_cache_shape(self, runner):
        assert runner._cache["msgs"] == []
        assert runner._cache["orders"] == []
        assert runner._cache["reviews"] == []
        assert runner.is_running is True
        assert runner._cache_is_updated is False
        assert runner.storage is None
        assert runner.polling_task is None

    def test_subrunners_reference_self(self, runner):
        assert runner._chat.runner is runner
        assert runner._order.runner is runner
        assert runner._review.runner is runner
        assert runner._category.runner is runner


class TestWarmUp:
    @pytest.mark.asyncio
    async def test_success_marks_cache_updated_and_runs_startup_handlers(self, runner, account):
        account.profile.get_user_data = AsyncMock()
        runner._chat._update_chat_cache = AsyncMock()
        runner._order._update_order_cache = AsyncMock()
        runner._review._update_review_cache = AsyncMock()
        started = []

        @runner.router.on_startup()
        async def on_start():
            started.append(True)

        await runner._warm_up(None, None)
        assert runner._cache_is_updated is True
        assert started == [True]

    @pytest.mark.asyncio
    async def test_watch_lots_and_chips_are_checked(self, runner, account):
        account.profile.get_user_data = AsyncMock()
        runner._category._check_lot_categories = AsyncMock()
        runner._category._check_chip_categories = AsyncMock()
        runner._chat._update_chat_cache = AsyncMock()
        runner._order._update_order_cache = AsyncMock()
        runner._review._update_review_cache = AsyncMock()
        await runner._warm_up(["cat-1"], ["chip-1"])
        runner._category._check_lot_categories.assert_awaited_once_with(["cat-1"])
        runner._category._check_chip_categories.assert_awaited_once_with(["chip-1"])

    @pytest.mark.asyncio
    async def test_failure_marks_cache_not_updated_and_calls_error_handler(self, runner, account):
        account.profile.get_user_data = AsyncMock()
        runner._chat._update_chat_cache = AsyncMock(side_effect=Exception("boom"))
        runner._order._update_order_cache = AsyncMock()
        runner._review._update_review_cache = AsyncMock()
        runner._handle_error = AsyncMock()
        await runner._warm_up(None, None)
        assert runner._cache_is_updated is False
        runner._handle_error.assert_awaited_once()


class TestCacheRunner:
    @pytest.mark.asyncio
    async def test_calls_warm_up_when_not_updated(self, runner):
        runner._warm_up = AsyncMock()
        await runner._cache_runner(None, None)
        runner._warm_up.assert_awaited_once_with(None, None)

    @pytest.mark.asyncio
    async def test_checks_updates_when_cache_already_warm(self, runner):
        runner._cache_is_updated = True
        runner._chat._check_chats = AsyncMock()
        runner._order._check_orders = AsyncMock()
        runner._review._check_reviews = AsyncMock()
        runner._purchase._check_purchases = AsyncMock()
        await runner._cache_runner(None, None)
        runner._chat._check_chats.assert_awaited_once()
        runner._order._check_orders.assert_awaited_once()
        runner._purchase._check_purchases.assert_awaited_once()
        runner._review._check_reviews.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_failure_still_calls_others_and_reports_error(self, runner):
        runner._cache_is_updated = True
        runner._chat._check_chats = AsyncMock(side_effect=Exception("boom"))
        runner._order._check_orders = AsyncMock()
        runner._review._check_reviews = AsyncMock()
        runner._purchase._check_purchases = AsyncMock()
        runner._handle_error = AsyncMock()
        await runner._cache_runner(None, None)
        runner._order._check_orders.assert_awaited_once()
        runner._purchase._check_purchases.assert_awaited_once()
        runner._handle_error.assert_awaited_once()


class TestHandleError:
    @pytest.mark.asyncio
    async def test_calls_async_error_handlers(self, runner):
        called = []

        @runner.router.on_error()
        async def on_error(event, exc):
            called.append((event, exc))

        exc = ValueError("boom")
        await runner._handle_error("event", exc)
        assert called == [("event", exc)]

    @pytest.mark.asyncio
    async def test_calls_sync_error_handlers(self, runner):
        called = []

        @runner.router.on_error()
        def on_error(event, exc):
            called.append((event, exc))

        await runner._handle_error(None, ValueError("boom"))
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_no_handlers_does_not_raise(self, runner):
        await runner._handle_error(None, ValueError("boom"))

    @pytest.mark.asyncio
    async def test_handler_exception_is_logged_and_does_not_raise(self, runner, caplog):
        @runner.router.on_error()
        async def on_error(event, exc):
            raise RuntimeError("handler crashed")

        await runner._handle_error(None, ValueError("boom"))
        assert "on_error" in caplog.text


class TestRunLoop:
    @pytest.mark.asyncio
    async def test_stops_when_is_running_false(self, runner, monkeypatch):
        runner.is_running = False
        runner._cache_runner = AsyncMock()
        await runner._run_loop(1)
        runner._cache_runner.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_error_sleeps_60_then_stops(self, runner, monkeypatch):
        sleep_mock = AsyncMock()
        monkeypatch.setattr("asyncio.sleep", sleep_mock)

        call_count = {"n": 0}

        async def cache_runner(*args):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise fpx_err.FpxRequestError("boom")
            runner.is_running = False

        runner._cache_runner = cache_runner
        await runner._run_loop(3)
        sleep_mock.assert_any_call(60)

    @pytest.mark.asyncio
    async def test_account_error_sleeps_5_and_continues(self, runner, monkeypatch):
        sleep_mock = AsyncMock()
        monkeypatch.setattr("asyncio.sleep", sleep_mock)
        call_count = {"n": 0}

        async def cache_runner(*args):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise fpx_err.FpxAccountError("boom")
            runner.is_running = False

        runner._cache_runner = cache_runner
        await runner._run_loop(3)
        sleep_mock.assert_any_call(5)

    @pytest.mark.asyncio
    async def test_httpx_error_sleeps_timer(self, runner, monkeypatch):
        sleep_mock = AsyncMock()
        monkeypatch.setattr("asyncio.sleep", sleep_mock)
        call_count = {"n": 0}

        async def cache_runner(*args):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise httpx.ConnectError("boom")
            runner.is_running = False

        runner._cache_runner = cache_runner
        await runner._run_loop(7)
        sleep_mock.assert_any_call(7)

    @pytest.mark.asyncio
    async def test_unknown_exception_wrapped_in_critical_error(self, runner):
        async def cache_runner(*args):
            raise ValueError("unexpected")

        runner._cache_runner = cache_runner
        with pytest.raises(fpx_err.FpxCriticalRunnerError) as exc_info:
            await runner._run_loop(1)
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert runner.is_running is False

    @pytest.mark.asyncio
    async def test_unknown_exception_goes_to_on_error_and_is_logged(self, runner, caplog):
        seen = []

        @runner.router.on_error()
        async def on_error(event, exc):
            seen.append((event, exc, exc.__cause__))

        async def cache_runner(*args):
            raise TypeError("parser broken")

        runner._cache_runner = cache_runner
        with pytest.raises(fpx_err.FpxCriticalRunnerError):
            await runner._run_loop(1)

        assert len(seen) == 1
        event, exc, cause = seen[0]
        assert event is None
        assert isinstance(exc, fpx_err.FpxCriticalRunnerError)
        assert isinstance(cause, TypeError)
        assert "parser broken" in str(exc)
        assert "Критическая ошибка polling" in caplog.text

    @pytest.mark.asyncio
    async def test_critical_error_is_not_rewrapped(self, runner):
        original = fpx_err.FpxCriticalRunnerError("already critical")

        async def cache_runner(*args):
            raise original

        runner._cache_runner = cache_runner
        with pytest.raises(fpx_err.FpxCriticalRunnerError) as exc_info:
            await runner._run_loop(1)
        assert exc_info.value is original

    @pytest.mark.asyncio
    async def test_on_error_failure_still_raises_critical(self, runner):
        @runner.router.on_error()
        async def on_error(event, exc):
            raise RuntimeError("handler crashed")

        async def cache_runner(*args):
            raise ValueError("unexpected")

        runner._cache_runner = cache_runner
        with pytest.raises(fpx_err.FpxCriticalRunnerError) as exc_info:
            await runner._run_loop(1)
        assert isinstance(exc_info.value.__cause__, ValueError)


class TestStartPolling:
    @pytest.mark.asyncio
    async def test_background_mode_returns_task(self, runner, monkeypatch):
        runner._run_loop = AsyncMock()
        task = await runner.start_polling(timer=1, is_background=True)
        assert isinstance(task, asyncio.Task)
        assert runner.polling_task is task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_foreground_mode_awaits_run_loop(self, runner):
        runner._run_loop = AsyncMock()
        await runner.start_polling(timer=1, is_background=False)
        runner._run_loop.assert_awaited_once_with(1, None, None)

    @pytest.mark.asyncio
    async def test_second_background_start_returns_same_task(self, runner):
        async def hang(*args, **kwargs):
            await asyncio.sleep(3600)

        runner._run_loop = hang
        first = await runner.start_polling(timer=1, is_background=True)
        second = await runner.start_polling(timer=1, is_background=True)
        assert first is second
        await runner.stop_polling()
        assert first.cancelled() or first.done()

    @pytest.mark.asyncio
    async def test_background_unknown_error_reaches_on_error_and_is_retrieved(self, runner):
        loop = asyncio.get_running_loop()
        contexts: list[dict] = []
        previous_handler = loop.get_exception_handler()

        def exception_handler(_loop, context):
            contexts.append(context)

        loop.set_exception_handler(exception_handler)

        async def cache_runner(*args):
            raise TypeError("parser broken")

        runner._cache_runner = cache_runner
        seen = []

        @runner.router.on_error()
        async def on_error(event, exc):
            seen.append((event, exc, exc.__cause__))

        try:
            task = await runner.start_polling(timer=0.01, is_background=True)
            assert runner.polling_task is task
            for _ in range(100):
                if task.done():
                    break
                await asyncio.sleep(0)
            assert task.done()
            await asyncio.sleep(0)

            assert seen
            event, exc, cause = seen[0]
            assert event is None
            assert isinstance(exc, fpx_err.FpxCriticalRunnerError)
            assert isinstance(cause, TypeError)
            assert runner.is_running is False

            stored = task.exception()
            assert isinstance(stored, fpx_err.FpxCriticalRunnerError)
            assert not any("never retrieved" in str(ctx.get("message", "")).lower() for ctx in contexts)
        finally:
            loop.set_exception_handler(previous_handler)


class TestStopPolling:
    @pytest.mark.asyncio
    async def test_stop_polling_cancels_background_task(self, runner):
        async def hang(*args, **kwargs):
            await asyncio.sleep(3600)

        runner._run_loop = hang
        task = await runner.start_polling(timer=10, is_background=True)
        await runner.stop_polling()
        assert task.done()
        assert runner.is_running is False

    @pytest.mark.asyncio
    async def test_stop_polling_without_task_only_sets_flag(self, runner):
        runner.is_running = True
        await runner.stop_polling()
        assert runner.is_running is False

    @pytest.mark.asyncio
    async def test_stop_polling_swallows_critical_error_from_finished_task(self, runner):
        async def cache_runner(*args):
            raise TypeError("parser broken")

        runner._cache_runner = cache_runner
        task = await runner.start_polling(timer=0.01, is_background=True)
        for _ in range(100):
            if task.done():
                break
            await asyncio.sleep(0)
        await runner.stop_polling()
        assert runner.is_running is False


class TestIdle:
    @pytest.mark.asyncio
    async def test_idle_sleeps_forever(self, runner, monkeypatch):
        sleep_mock = AsyncMock(side_effect=[None, asyncio.CancelledError()])
        monkeypatch.setattr("asyncio.sleep", sleep_mock)
        with pytest.raises(asyncio.CancelledError):
            await runner.idle()
        assert sleep_mock.await_count == 2
