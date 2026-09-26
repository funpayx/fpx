"""Тесты FunPayTools — точка входа в библиотеку, инициализация клиента/раннера."""

import asyncio

import httpx
import pytest

from fpx.classes.account.account import Account
from fpx.classes.runner.runner import Runner
from fpx.main import FunPayTools, _close_async_client_sync
from fpx.utils.storage.memory import MemoryStorage

TEST_GKEY = "0123456789abcdef0123456789abcdef"


def _track_owned_async_client(monkeypatch: pytest.MonkeyPatch) -> dict[str, httpx.AsyncClient]:
    created: dict[str, httpx.AsyncClient] = {}
    original = httpx.AsyncClient

    def tracking_async_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        client = original(*args, **kwargs)
        created["client"] = client
        return client

    monkeypatch.setattr("fpx.main.httpx.AsyncClient", tracking_async_client)
    return created


class TestInit:
    def test_default_http_client_is_created_with_cookies(self):
        tools = FunPayTools(TEST_GKEY)
        assert tools._client.cookies["golden_key"] == TEST_GKEY
        assert isinstance(tools.account, Account)
        assert isinstance(tools.runner, Runner)
        assert tools.router is tools.runner.router

    def test_default_storage_is_memory_storage(self):
        tools = FunPayTools(TEST_GKEY)
        assert isinstance(tools.storage, MemoryStorage)
        assert tools.runner.storage is tools.storage

    def test_custom_storage_is_used(self):
        custom_storage = MemoryStorage()
        tools = FunPayTools(TEST_GKEY, storage=custom_storage)
        assert tools.storage is custom_storage
        assert tools.runner.storage is custom_storage

    def test_custom_http_client_gets_cookies_and_headers_merged(self):
        http_client = httpx.AsyncClient()
        tools = FunPayTools(TEST_GKEY, http_client=http_client)
        assert tools._client is http_client
        assert http_client.cookies["golden_key"] == TEST_GKEY

    def test_proxy_and_http_client_together_raises(self):
        http_client = httpx.AsyncClient()
        with pytest.raises(ValueError):
            FunPayTools(TEST_GKEY, proxy="http://127.0.0.1:8080", http_client=http_client)

    def test_proxy_alone_builds_client_with_mounts(self):
        tools = FunPayTools(TEST_GKEY, proxy="http://127.0.0.1:8080")
        assert tools._client is not None

    def test_request_engine_linked_to_runner(self):
        tools = FunPayTools(TEST_GKEY)
        assert tools.account._request_engine.runner is tools.runner


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_stops_runner_and_closes_client(self):
        tools = FunPayTools(TEST_GKEY)
        tools.runner.is_running = True
        await tools.shutdown()
        assert tools.runner.is_running is False
        assert tools._client.is_closed is True

    @pytest.mark.asyncio
    async def test_shutdown_idempotent_when_already_closed(self):
        tools = FunPayTools(TEST_GKEY)
        await tools.shutdown()
        # повторный вызов не должен упасть
        await tools.shutdown()

    @pytest.mark.asyncio
    async def test_async_context_manager_calls_shutdown(self):
        tools = FunPayTools(TEST_GKEY)
        async with tools as t:
            assert t is tools
        assert tools._client.is_closed is True

    @pytest.mark.asyncio
    async def test_shutdown_cancels_polling_task(self):
        tools = FunPayTools(TEST_GKEY)
        if tools._refresh_task and not tools._refresh_task.done():
            tools._refresh_task.cancel()
            try:
                await tools._refresh_task
            except asyncio.CancelledError:
                pass
            tools._refresh_task = None

        async def hang(*args, **kwargs):
            await asyncio.sleep(3600)

        tools.runner._run_loop = hang
        task = await tools.runner.start_polling(timer=10, is_background=True)
        assert tools.polling_task is task
        await tools.shutdown()
        assert tools.runner.is_running is False
        assert task.done()

    def test_polling_task_is_none_before_start(self):
        tools = FunPayTools(TEST_GKEY)
        assert tools.polling_task is None

    @pytest.mark.asyncio
    async def test_shutdown_does_not_close_caller_owned_client(self):
        http_client = httpx.AsyncClient()
        try:
            tools = FunPayTools(TEST_GKEY, http_client=http_client)
            tools.runner.is_running = True
            await tools.shutdown()
            assert tools.runner.is_running is False
            assert http_client.is_closed is False
            assert tools._client is http_client
        finally:
            await http_client.aclose()

    @pytest.mark.asyncio
    async def test_shutdown_idempotent_for_caller_owned_client(self):
        http_client = httpx.AsyncClient()
        try:
            tools = FunPayTools(TEST_GKEY, http_client=http_client)
            await tools.shutdown()
            await tools.shutdown()
            assert http_client.is_closed is False
        finally:
            await http_client.aclose()

    @pytest.mark.asyncio
    async def test_async_context_manager_does_not_close_caller_owned_client(self):
        http_client = httpx.AsyncClient()
        try:
            async with FunPayTools(TEST_GKEY, http_client=http_client) as tools:
                assert tools._client is http_client
            assert http_client.is_closed is False
        finally:
            await http_client.aclose()


class TestInitClientCleanup:
    def test_owned_client_closed_when_account_init_fails(self, monkeypatch):
        created = _track_owned_async_client(monkeypatch)

        def fail_account(_client: object) -> None:
            raise RuntimeError("account init failed")

        monkeypatch.setattr("fpx.main.Account", fail_account)
        with pytest.raises(RuntimeError, match="account init failed"):
            FunPayTools(TEST_GKEY)
        assert created["client"].is_closed is True

    def test_owned_client_closed_when_runner_init_fails(self, monkeypatch):
        created = _track_owned_async_client(monkeypatch)

        def fail_runner(_account: object) -> None:
            raise RuntimeError("runner init failed")

        monkeypatch.setattr("fpx.main.Runner", fail_runner)
        with pytest.raises(RuntimeError, match="runner init failed"):
            FunPayTools(TEST_GKEY)
        assert created["client"].is_closed is True

    def test_caller_owned_client_stays_open_when_account_init_fails(self, monkeypatch):
        http_client = httpx.AsyncClient()

        def fail_account(_client: object) -> None:
            raise RuntimeError("account init failed")

        monkeypatch.setattr("fpx.main.Account", fail_account)
        try:
            with pytest.raises(RuntimeError, match="account init failed"):
                FunPayTools(TEST_GKEY, http_client=http_client)
            assert http_client.is_closed is False
        finally:
            asyncio.run(http_client.aclose())

    def test_init_error_is_not_masked_if_owned_client_close_fails(self, monkeypatch):
        def fail_account(_client: object) -> None:
            raise RuntimeError("account init failed")

        def fail_close(_client: httpx.AsyncClient) -> None:
            raise RuntimeError("close failed")

        monkeypatch.setattr("fpx.main.Account", fail_account)
        monkeypatch.setattr("fpx.main._close_async_client_sync", fail_close)
        with pytest.raises(RuntimeError, match="account init failed"):
            FunPayTools(TEST_GKEY)

    def test_close_async_client_sync_without_running_loop(self):
        client = httpx.AsyncClient()
        _close_async_client_sync(client)
        assert client.is_closed is True

    def test_close_async_client_sync_noop_if_already_closed(self):
        client = httpx.AsyncClient()
        asyncio.run(client.aclose())
        _close_async_client_sync(client)
        assert client.is_closed is True

    @pytest.mark.asyncio
    async def test_owned_client_closed_when_account_fails_with_running_loop(self, monkeypatch):
        created = _track_owned_async_client(monkeypatch)

        def fail_account(_client: object) -> None:
            raise RuntimeError("account init failed")

        monkeypatch.setattr("fpx.main.Account", fail_account)
        with pytest.raises(RuntimeError, match="account init failed"):
            FunPayTools(TEST_GKEY)
        await asyncio.sleep(0)
        assert created["client"].is_closed is True
