"""Тесты UpdatesRunner - приём событий через /runner/: теги, догрузка чатов, сверка страниц по сигналу."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx._parsers import FpxParser
from fpx.classes.runner.runner import Runner
from fpx.models.chat import Message
from fpx.utils import errors as fpx_err
from fpx.utils.storage.memory import MemoryStorage

SHOP_ID = 1000
BUYER_ID = 2000


def respond(*objects):
    return {"objects": list(objects), "response": False}


def counters(tag="c1", seller=0):
    return {"type": "orders_counters", "id": SHOP_ID, "tag": tag, "data": {"buyer": 0, "seller": seller}}


def bookmarks(*chats, tag="b1"):
    """chats: (chat_id, ID последнего сообщения, собеседник)."""
    html = "".join(
        f'<a href="https://funpay.com/chat/?node={chat_id}" class="contact-item" data-id="{chat_id}"'
        f' data-node-msg="{last_id}"><div class="media-user-name">{name}</div>'
        '<div class="contact-item-message">...</div></a>'
        for chat_id, last_id, name in chats
    )
    return {"type": "chat_bookmarks", "id": SHOP_ID, "tag": tag, "data": {"order": [], "html": html}}


def chat_node(chat_id, *messages, buyer_id=BUYER_ID):
    """messages: (ID, ID автора, текст)."""
    return {
        "type": "chat_node",
        "id": int(chat_id),
        "tag": "n1",
        "data": {
            "node": {"id": int(chat_id), "name": f"users-{SHOP_ID}-{buyer_id}", "silent": False},
            "messages": [
                {
                    "id": msg_id,
                    "author": author,
                    "html": f'<div class="chat-msg-item" id="message-{msg_id}">'
                    f'<div class="chat-msg-text">{text}</div></div>',
                }
                for msg_id, author, text in messages
            ],
        },
    }


@pytest.fixture
def account():
    acc = MagicMock()
    acc.data.user_id = str(SHOP_ID)
    acc.data.username = "shop"
    acc.data._node_names = {}
    acc._parser = FpxParser()
    acc._client.runner_request = AsyncMock()
    return acc


@pytest.fixture
def runner(account):
    r = Runner(account)
    r.storage = MemoryStorage()
    return r


@pytest.fixture
def updates(runner):
    return runner._updates


def sent_objects(account, call_index=-1):
    return account._client.runner_request.await_args_list[call_index].args[0]


def collect_messages(runner):
    seen = []

    @runner.router.on_message()
    async def on_message(message: Message):
        seen.append((message.chat_id, message.text))

    return seen


async def warm_up(updates, account, *chats):
    account._client.runner_request.side_effect = [respond(counters(), bookmarks(*chats))]
    await updates._warm_up()


class TestWarmUp:
    @pytest.mark.asyncio
    async def test_remembers_last_messages_and_watermark(self, updates, account, runner):
        await warm_up(updates, account, ("1", 100, "a"), ("2", 90, "b"))
        assert runner._chat._chat_last_ids == {"1": "100", "2": "90"}
        assert updates._watermark == 100
        assert updates._pending == {}
        types_ = [obj["type"] for obj in sent_objects(account)]
        assert types_ == ["orders_counters", "chat_bookmarks"]

    @pytest.mark.asyncio
    async def test_missing_bookmarks_is_an_error(self, updates, account):
        account._client.runner_request.side_effect = [respond(counters())]
        with pytest.raises(fpx_err.FpxGetUpdatesError):
            await updates._warm_up()

    @pytest.mark.asyncio
    async def test_loads_pages_only_for_registered_handlers(self, updates, account, runner):
        runner._order._update_order_page_cache = AsyncMock()
        runner._purchase._update_purchase_page_cache = AsyncMock()
        runner._review._update_review_cache = AsyncMock()

        @runner.router.on_new_order()
        async def on_new_order(order):
            pass

        await warm_up(updates, account)
        runner._order._update_order_page_cache.assert_awaited_once()
        runner._purchase._update_purchase_page_cache.assert_not_awaited()
        runner._review._update_review_cache.assert_not_awaited()
        # Первый тик сверит страницу ещё раз: заказ мог прийти между страницей и /runner/.
        assert updates._events_dirty is True

    @pytest.mark.asyncio
    async def test_without_page_handlers_first_tick_does_not_recheck(self, updates, account):
        await warm_up(updates, account)
        assert updates._events_dirty is False
        assert updates._ready == set()


class TestRequest:
    @pytest.mark.asyncio
    async def test_unexpected_error_is_wrapped(self, updates, account):
        account._client.runner_request.side_effect = ValueError("not json")
        with pytest.raises(fpx_err.FpxGetUpdatesError) as exc_info:
            await updates._request([])
        assert isinstance(exc_info.value.__cause__, ValueError)

    @pytest.mark.asyncio
    async def test_objects_must_be_a_list(self, updates, account):
        account._client.runner_request.side_effect = [{"objects": "oops"}]
        with pytest.raises(fpx_err.FpxGetUpdatesError):
            await updates._request([])

    @pytest.mark.asyncio
    async def test_account_errors_pass_through(self, updates, account):
        account._client.runner_request.side_effect = fpx_err.FpxRequestError("429")
        with pytest.raises(fpx_err.FpxRequestError):
            await updates._request([])


class TestPoll:
    @pytest.mark.asyncio
    async def test_sends_known_tags(self, updates, account):
        await warm_up(updates, account, ("1", 100, "a"))
        account._client.runner_request.side_effect = [respond()]
        await updates._poll()
        objects = sent_objects(account)
        assert [(obj["type"], obj["id"], obj["tag"]) for obj in objects] == [
            ("orders_counters", SHOP_ID, "c1"),
            ("chat_bookmarks", SHOP_ID, "b1"),
        ]

    @pytest.mark.asyncio
    async def test_counters_with_the_same_tag_are_not_a_change(self, updates, account):
        await warm_up(updates, account)
        account._client.runner_request.side_effect = [respond(counters("c1")), respond(counters("c2"))]
        assert (await updates._poll())[0] is False
        assert (await updates._poll())[0] is True

    @pytest.mark.asyncio
    async def test_bookmarks_without_html_are_ignored(self, updates, account):
        await warm_up(updates, account)
        bookmarks_without_data = {"type": "chat_bookmarks", "id": SHOP_ID, "tag": "b2", "data": False}
        account._client.runner_request.side_effect = [respond(bookmarks_without_data)]
        assert await updates._poll() == (False, None)
        assert updates._tags["chat_bookmarks"] == "b2"


class TestChats:
    @pytest.mark.asyncio
    async def test_history_is_requested_after_the_last_seen_message(self, updates, account, runner):
        seen = collect_messages(runner)
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 102, "buyer"), tag="b2")),
            respond(chat_node("1", (101, BUYER_ID, "раз"), (102, BUYER_ID, "два"))),
        ]
        await updates._check_updates()
        node = sent_objects(account)[0]
        assert node["type"] == "chat_node"
        assert node["id"] == 1
        assert node["data"] == {"node": 1, "last_message": 100, "content": ""}
        assert seen == [("1", "раз"), ("1", "два")]
        assert runner._chat.get_last_id("1") == "102"
        assert updates._pending == {}

    @pytest.mark.asyncio
    async def test_unknown_chat_gets_whole_history_filtered_by_watermark(self, updates, account, runner):
        seen = collect_messages(runner)
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("7", 103, "new"), ("1", 100, "buyer"), tag="b2")),
            respond(chat_node("7", (50, 3000, "до запуска"), (103, 3000, "после запуска"), buyer_id=3000)),
        ]
        await updates._check_updates()
        assert sent_objects(account)[0]["data"]["last_message"] == -1
        assert seen == [("7", "после запуска")]

    @pytest.mark.asyncio
    async def test_sender_names_come_from_bookmarks_and_account(self, updates, account, runner):
        senders = []
        # Хендлеры не зовутся для своих сообщений, поэтому смотрим, что уходит в диспетчер.
        runner._chat._trigger_message_handlers = AsyncMock(side_effect=lambda message: senders.append(message.sender))
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 102, "buyer"), tag="b2")),
            respond(chat_node("1", (101, BUYER_ID, "от покупателя"), (102, SHOP_ID, "от меня"))),
        ]
        await updates._check_updates()
        assert senders == ["buyer", "shop"]

    @pytest.mark.asyncio
    async def test_node_name_is_saved_for_send_message(self, updates, account):
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 101, "buyer"), tag="b2")),
            respond(chat_node("1", (101, BUYER_ID, "hi"))),
        ]
        await updates._check_updates()
        assert account.data._node_names == {"1": f"users-{SHOP_ID}-{BUYER_ID}"}

    @pytest.mark.asyncio
    async def test_handler_error_does_not_stop_the_next_message(self, updates, account, runner):
        seen = []
        errors = []

        @runner.router.on_message()
        async def on_message(message: Message):
            if message.text == "раз":
                raise RuntimeError("boom")
            seen.append(message.text)

        @runner.router.on_error()
        async def on_error(event, exception):
            errors.append((event.text, str(exception)))

        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 102, "buyer"), tag="b2")),
            respond(chat_node("1", (101, BUYER_ID, "раз"), (102, BUYER_ID, "два"))),
        ]
        await updates._check_updates()
        assert seen == ["два"]
        assert errors == [("раз", "boom")]

    @pytest.mark.asyncio
    async def test_incomplete_history_is_retried_then_skipped(self, updates, account, runner, caplog):
        seen = collect_messages(runner)
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 103, "buyer"), tag="b2")),
            respond(chat_node("1", (101, BUYER_ID, "раз"))),
            respond(),
            respond(chat_node("1", (101, BUYER_ID, "раз"), (102, BUYER_ID, "два"))),
            respond(),
            respond(chat_node("1", (101, BUYER_ID, "раз"), (102, BUYER_ID, "два"))),
        ]
        await updates._check_updates()
        assert "1" in updates._pending
        await updates._check_updates()
        assert seen == [("1", "раз"), ("1", "два")]
        assert sent_objects(account)[0]["data"]["last_message"] == 101
        with caplog.at_level(logging.WARNING, logger="fpx.updates_runner"):
            await updates._check_updates()
        assert updates._pending == {}
        assert runner._chat.get_last_id("1") == "103"
        assert "103" in caplog.text

    @pytest.mark.asyncio
    async def test_chat_missing_from_the_response_stays_pending(self, updates, account):
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 101, "buyer"), tag="b2")),
            respond(),
        ]
        await updates._check_updates()
        assert "1" in updates._pending

    @pytest.mark.asyncio
    async def test_chat_node_without_data_stays_pending(self, updates, account):
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 101, "buyer"), tag="b2")),
            respond({"type": "chat_node", "id": 1, "tag": "n1", "data": False}),
        ]
        await updates._check_updates()
        assert "1" in updates._pending

    @pytest.mark.asyncio
    async def test_failed_history_request_changes_nothing(self, updates, account, runner):
        seen = collect_messages(runner)
        await warm_up(updates, account, ("1", 100, "buyer"))
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 101, "buyer"), tag="b2")),
            fpx_err.FpxRequestError("timeout"),
        ]
        with pytest.raises(fpx_err.FpxRequestError):
            await updates._check_updates()
        assert seen == []
        assert runner._chat.get_last_id("1") == "100"
        assert "1" in updates._pending


class TestSources:
    def test_sources_follow_registered_handlers(self, updates, runner):
        assert updates._sources() == []
        runner.router.order_targets({"пометка": AsyncMock()})
        runner.router.on_purchases()(AsyncMock())
        runner.router.on_new_review()(AsyncMock())
        assert updates._sources() == ["orders", "purchases", "reviews"]

    @pytest.mark.asyncio
    async def test_first_sync_after_late_registration_only_fills_cache(self, updates, account, runner):
        await warm_up(updates, account)
        runner._review._update_review_cache = AsyncMock()
        runner._review._check_reviews = AsyncMock()
        runner.router.on_new_review()(AsyncMock())
        await updates._sync_sources()
        await updates._sync_sources()
        runner._review._update_review_cache.assert_awaited_once()
        runner._review._check_reviews.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_purchase_page_goes_from_cache_to_checks(self, updates, runner):
        runner._purchase._update_purchase_page_cache = AsyncMock()
        runner._purchase._check_purchase_page = AsyncMock()
        runner.router.on_new_purchase()(AsyncMock())
        await updates._sync_sources()
        await updates._sync_sources()
        runner._purchase._update_purchase_page_cache.assert_awaited_once()
        runner._purchase._check_purchase_page.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_every_failed_page_is_reported(self, updates, runner):
        orders_error = fpx_err.FpxGetUserSellsError("orders")
        reviews_error = fpx_err.FpxGetProfileError("reviews")
        runner._order._update_order_page_cache = AsyncMock(side_effect=orders_error)
        runner._review._update_review_cache = AsyncMock(side_effect=reviews_error)
        runner.router.on_new_order()(AsyncMock())
        runner.router.on_new_review()(AsyncMock())
        reported = []

        @runner.router.on_error()
        async def on_error(event, exception):
            reported.append(exception)

        with pytest.raises(fpx_err.FpxGetUserSellsError):
            await updates._sync_sources()
        assert reported == [reviews_error]
        assert updates._ready == set()

    @pytest.mark.asyncio
    async def test_failed_page_check_keeps_signal_and_still_delivers_messages(self, updates, account, runner):
        seen = collect_messages(runner)
        runner._order._update_order_page_cache = AsyncMock()
        runner._order._check_order_page = AsyncMock(side_effect=[fpx_err.FpxGetUserSellsError("down"), None])
        runner.router.on_new_order()(AsyncMock())
        await warm_up(updates, account, ("1", 100, "buyer"))
        updates._events_dirty = False
        account._client.runner_request.side_effect = [
            respond(bookmarks(("1", 102, "buyer"), tag="b2")),
            respond(chat_node("1", (101, 0, "Покупатель оплатил заказ #A1."), (102, BUYER_ID, "оплатил"))),
            respond(),
        ]
        with pytest.raises(fpx_err.FpxGetUserSellsError):
            await updates._check_updates()
        assert seen == [("1", "оплатил")]
        assert updates._events_dirty is True
        await updates._check_updates()
        assert runner._order._check_order_page.await_count == 2
        assert updates._events_dirty is False
