"""
Сквозные тесты приёма событий через /runner/.

Настоящие Runner, RequestEngine и парсеры, подменён только HTTP: FakeFunPay поверх
httpx.MockTransport отдаёт страницы и отвечает на /runner/ как сайт - объект
возвращается, только если его тег отличается от присланного клиентом.
Тег счётчиков заказов считается по самим счётчикам, поэтому оплата одного заказа
и подтверждение другого за один тик его не меняют.
"""

import asyncio
import hashlib
import json
import re
from typing import Any, Callable
from urllib.parse import parse_qs

import httpx
import pytest

from fpx import FunPayTools, types
from fpx.utils import errors as fpx_err

SHOP_ID, SHOP = 1000, "shop"
BUYER_ID, BUYER = 2000, "buyer1"
NODE = 555
GKEY = "a" * 32


def version(value: Any) -> str:
    return hashlib.md5(json.dumps(value, sort_keys=True).encode()).hexdigest()[:8]


class FakeFunPay:
    """Ровно столько funpay.com, сколько нужно раннеру и парсерам fpx."""

    def __init__(self) -> None:
        self.next_id = 101
        self.chats: dict[int, dict[str, Any]] = {
            NODE: {"buyer_id": BUYER_ID, "buyer": BUYER, "messages": [(100, BUYER_ID, "Здравствуйте")]}
        }
        self.orders: list[dict[str, Any]] = [{"id": "OLD0", "date": "Вчера, 10:00", "status": "Закрыт", "node": NODE}]
        self.reviews: list[dict[str, Any]] = []
        self.requests: list[str] = []
        self.runner_calls: list[list[str]] = []
        self.broken_chat_node_responses = 0
        # Сколько последних чатов FunPay кладёт в chat_bookmarks (на сайте их ограниченное число).
        self.bookmarks_limit = 50
        # Действия, которые происходят на сайте прямо перед ответом на очередной /runner/.
        self.before_runner: list[Callable[[], None]] = []

    # -- что происходит на FunPay
    def say(self, text: str, author: int = BUYER_ID, node: int = NODE) -> None:
        self.chats[node]["messages"].append((self.next_id, author, text))
        self.next_id += 1

    def notify(self, text: str, node: int = NODE) -> None:
        self.say(text, author=0, node=node)

    def open_chat(self, node: int, buyer_id: int, buyer: str) -> None:
        self.chats[node] = {"buyer_id": buyer_id, "buyer": buyer, "messages": []}

    def add_order(self, order_id: str, status: str = "Оплачен", date: str = "Сегодня, 12:00", node: int = NODE) -> None:
        self.orders.insert(0, {"id": order_id, "date": date, "status": status, "node": node})

    def pay(self, order_id: str, node: int = NODE) -> None:
        self.add_order(order_id, node=node)
        chat = self.chats[node]
        self.notify(
            f'Покупатель <a href="https://funpay.com/users/{chat["buyer_id"]}/">{chat["buyer"]}</a> оплатил '
            f'<a href="https://funpay.com/orders/{order_id}/">заказ #{order_id}</a>.',
            node,
        )

    def confirm(self, order_id: str) -> None:
        order = self.order(order_id)
        order["status"] = "Закрыт"
        chat = self.chats[order["node"]]
        self.notify(f"Покупатель {chat['buyer']} подтвердил успешное выполнение заказа #{order_id}.", order["node"])

    def leave_review(self, order_id: str, text: str, stars: int) -> None:
        order = self.order(order_id)
        chat = self.chats[order["node"]]
        self.reviews.insert(0, {"order_id": order_id, "text": text, "stars": stars, "author": chat["buyer"]})
        self.notify(f"Покупатель {chat['buyer']} написал отзыв к заказу #{order_id}.", order["node"])

    def order(self, order_id: str) -> dict[str, Any]:
        return next(order for order in self.orders if order["id"] == order_id)

    # -- /runner/
    def counters(self) -> tuple[dict[str, int], str]:
        data = {"buyer": 0, "seller": sum(order["status"] == "Оплачен" for order in self.orders)}
        return data, version(data)

    def bookmarks(self) -> tuple[dict[str, Any], str]:
        chats = sorted(
            ((node, chat) for node, chat in self.chats.items() if chat["messages"]),
            key=lambda item: item[1]["messages"][-1][0],
            reverse=True,
        )[: self.bookmarks_limit]
        html = "".join(
            f'<a href="https://funpay.com/chat/?node={node}" class="contact-item" data-id="{node}"'
            f' data-node-msg="{chat["messages"][-1][0]}" data-user-msg="{chat["messages"][-1][0]}">'
            f'<div class="media-user-name">{chat["buyer"]}</div>'
            f'<div class="contact-item-message">{re.sub("<[^>]+>", "", chat["messages"][-1][2])}</div>'
            '<div class="contact-item-time">12:00</div></a>'
            for node, chat in chats
        )
        data = {"order": [node for node, _ in chats], "html": html}
        return data, version([(node, chat["messages"][-1][0]) for node, chat in chats])

    def message_html(self, node: int, index: int) -> str:
        messages = self.chats[node]["messages"]
        msg_id, author, text = messages[index]
        with_head = index == 0 or messages[index - 1][1] != author
        if author == 0:
            head = (
                '<div class="media-user-name">FunPay'
                ' <span class="chat-msg-author-label label label-primary">оповещение</span></div>'
            )
            body = (
                '<div class="alert alert-with-icon alert-info" role="alert">'
                f'<div class="chat-msg-text">{text}</div></div>'
            )
        else:
            name = SHOP if author == SHOP_ID else self.chats[node]["buyer"]
            head = (
                '<div class="media-user-name"><a class="chat-msg-author-link"'
                f' href="https://funpay.com/users/{author}/">{name}</a></div>'
            )
            body = f'<div class="chat-msg-text">{text}</div>'
        classes = "chat-msg-item chat-msg-with-head" if with_head else "chat-msg-item"
        return (
            f'<div class="{classes}" id="message-{msg_id}"><div class="chat-message">'
            f'{head if with_head else ""}<div class="chat-msg-body">{body}</div></div></div>'
        )

    def chat_node(self, node: int, last_message: int) -> tuple[dict[str, Any], str]:
        chat = self.chats[node]
        messages = chat["messages"]
        indexes = [i for i, message in enumerate(messages) if last_message == -1 or message[0] > last_message][-50:]
        low, high = sorted((SHOP_ID, chat["buyer_id"]))
        data = {
            "node": {"id": node, "name": f"users-{low}-{high}", "silent": False},
            "messages": [
                {"id": messages[i][0], "author": messages[i][1], "html": self.message_html(node, i)} for i in indexes
            ],
        }
        return data, version([message[0] for message in messages])

    def node_by_name(self, name: str) -> int:
        buyer_ids = {int(part) for part in name.split("-")[1:]} - {SHOP_ID}
        return next(node for node, chat in self.chats.items() if chat["buyer_id"] in buyer_ids)

    def runner(self, form: dict[str, list[str]]) -> httpx.Response:
        if self.before_runner:
            self.before_runner.pop(0)()
        objects = json.loads(form.get("objects", ["[]"])[0])
        types_ = [obj["type"] for obj in objects]
        self.runner_calls.append(types_)
        if "chat_node" in types_ and self.broken_chat_node_responses:
            self.broken_chat_node_responses -= 1
            return httpx.Response(200, text="<html>Что-то пошло не так</html>")
        response: Any = False
        request = form.get("request", ["false"])[0]
        if request != "false":
            data = json.loads(request)["data"]
            self.say(data["content"], author=SHOP_ID, node=self.node_by_name(data["node"]))
            response = {"error": None}
        result = []
        for obj in objects:
            if obj["type"] == "orders_counters":
                data, tag = self.counters()
            elif obj["type"] == "chat_bookmarks":
                data, tag = self.bookmarks()
            elif obj["type"] == "chat_node":
                data, tag = self.chat_node(int(obj["data"]["node"]), int(obj["data"]["last_message"]))
            else:
                continue
            if tag != obj["tag"]:
                result.append({"type": obj["type"], "id": obj["id"], "tag": tag, "data": data})
        return httpx.Response(200, json={"objects": result, "response": response})

    # -- страницы
    def main_page(self) -> str:
        app = json.dumps({"csrf-token": "tok", "userId": SHOP_ID})
        return (
            f"<html><body data-app-data='{app}'>"
            f'<a class="user-link-dropdown" href="https://funpay.com/users/{SHOP_ID}/">'
            f'<div class="user-link-name">{SHOP}</div></a></body></html>'
        )

    def sales_page(self) -> str:
        rows = "".join(
            f'<a class="tc-item" href="https://funpay.com/orders/{order["id"]}/">'
            f'<div class="tc-date-time">{order["date"]}</div><div class="tc-order">#{order["id"]}</div>'
            '<div class="order-desc"><div>1000 робуксов</div><div>Roblox, Робуксы</div></div>'
            f'<div class="tc-user"><span class="pseudo-a">{self.chats[order["node"]]["buyer"]}</span></div>'
            f'<div class="tc-status">{order["status"]}</div><div class="tc-price">1000 ₽</div></a>'
            for order in self.orders
        )
        return f"<html><body>{rows}</body></html>"

    def order_page(self, order_id: str) -> str:
        order = self.order(order_id)
        return (
            f'<html><body><h1 class="page-header">Заказ #{order_id} <span>{order["status"]}</span></h1>'
            f'<div class="chat-float" data-id="{order["node"]}"></div>'
            "<h5>Подробное описание</h5><div>1000 робуксов</div></body></html>"
        )

    def profile_page(self) -> str:
        items = "".join(
            f'<div class="review-item"><div class="media-user-name">{review["author"]}</div>'
            f'<div class="review-item-order"><a href="https://funpay.com/orders/{review["order_id"]}/">'
            f'#{review["order_id"]}</a></div><div class="review-item-text">{review["text"]}</div>'
            f'<div class="rating"><div class="rating{review["stars"]}"></div></div></div>'
            for review in self.reviews
        )
        return f"<html><body>{items}</body></html>"

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append(f"{request.method} {path}")
        if path == "/runner/":
            return self.runner(parse_qs(request.content.decode()))
        if path == "/":
            html = self.main_page()
        elif path == "/orders/trade":
            html = self.sales_page()
        elif path.startswith("/orders/") and path != "/orders/":
            html = self.order_page(path.strip("/").split("/")[-1])
        elif path == f"/users/{SHOP_ID}/":
            html = self.profile_page()
        else:
            return httpx.Response(404)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})


@pytest.fixture
def site() -> FakeFunPay:
    return FakeFunPay()


def make_tools(site: FakeFunPay) -> FunPayTools:
    # Создаётся вне event loop, поэтому fpx не запускает фоновое обновление куков.
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(site.handle),
        base_url="https://funpay.com",
        follow_redirects=True,
    )
    return FunPayTools(GKEY, http_client=client)


async def tick(fp: FunPayTools) -> list[str]:
    """Одна итерация polling (то же, что делает start_polling); возвращает ошибки аккаунта."""
    try:
        await fp.runner._cache_runner(None, None)
    except fpx_err.FpxAccountError as error:
        return [type(error).__name__]
    return []


def run(fp: FunPayTools, scenario: Any) -> None:
    async def main() -> None:
        try:
            await scenario()
        finally:
            await fp._client.aclose()

    asyncio.run(main())


def collect_messages(fp: FunPayTools) -> list[str]:
    seen: list[str] = []

    @fp.router.on_message()
    async def on_message(message: types.Message) -> None:
        seen.append(message.text)

    return seen


def test_idle_tick_is_one_runner_request(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen = collect_messages(fp)

    async def scenario() -> None:
        assert await tick(fp) == []  # прогрев
        site.requests.clear()
        assert await tick(fp) == []
        assert await tick(fp) == []

    run(fp, scenario)
    assert site.requests == ["POST /runner/", "POST /runner/"]
    assert seen == []


def test_burst_of_messages_arrives_in_order_without_chat_pages(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen = collect_messages(fp)

    async def scenario() -> None:
        await tick(fp)
        site.say("логин: robloxuser")
        site.say("пароль: hunter2")
        await tick(fp)
        await tick(fp)

    run(fp, scenario)
    assert seen == ["логин: robloxuser", "пароль: hunter2"]
    assert not any(request.startswith("GET /chat/") for request in site.requests)
    assert site.runner_calls.count(["chat_node"]) == 1


def test_buyer_text_with_system_phrase_is_delivered(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen = collect_messages(fp)

    async def scenario() -> None:
        await tick(fp)
        site.say("Я оплатил заказ, где товар?")
        await tick(fp)

    run(fp, scenario)
    assert seen == ["Я оплатил заказ, где товар?"]


def test_messages_of_a_chat_opened_after_start_are_delivered(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen = collect_messages(fp)

    async def scenario() -> None:
        await tick(fp)
        site.open_chat(777, 3000, "buyer2")
        site.say("Первое", author=3000, node=777)
        site.say("Второе", author=3000, node=777)
        await tick(fp)

    run(fp, scenario)
    assert seen == ["Первое", "Второе"]


def test_payment_reaches_order_handler_before_buyer_message(site: FakeFunPay) -> None:
    fp = make_tools(site)
    events: list[tuple[str, ...]] = []

    @fp.router.on_new_order()
    async def on_new_order(order: types.Order) -> None:
        events.append(("order", str(order.order_id), str(order.chat_id)))

    @fp.router.on_message()
    async def on_message(message: types.Message) -> None:
        events.append(("message", message.text, str(message.chat_id)))

    async def scenario() -> None:
        await tick(fp)
        await tick(fp)
        site.pay("NEW1")
        site.say("Оплатил, жду")
        await tick(fp)
        await tick(fp)

    run(fp, scenario)
    # Оповещение об оплате в on_message не попадает, заказ приходит раньше сообщения.
    assert events == [("order", "NEW1", str(NODE)), ("message", "Оплатил, жду", str(NODE))]


def test_order_paid_during_warm_up_is_not_lost(site: FakeFunPay) -> None:
    """Оплата между загрузкой страницы продаж и первым /runner/ находится на первом тике."""
    fp = make_tools(site)
    seen: list[str] = []

    @fp.router.on_new_order()
    async def on_new_order(order: types.Order) -> None:
        seen.append(str(order.order_id))

    site.before_runner.append(lambda: site.pay("RACE1"))

    async def scenario() -> None:
        await tick(fp)
        await tick(fp)

    run(fp, scenario)
    assert seen == ["RACE1"]


def test_counters_alone_trigger_order_check(site: FakeFunPay) -> None:
    """Заказ без оповещения в видимом чате находится по смене счётчиков."""
    fp = make_tools(site)
    seen: list[str] = []

    @fp.router.on_new_order()
    async def on_new_order(order: types.Order) -> None:
        seen.append(str(order.order_id))

    async def scenario() -> None:
        await tick(fp)
        await tick(fp)
        site.add_order("QUIET1")
        await tick(fp)

    run(fp, scenario)
    assert seen == ["QUIET1"]


def test_old_messages_of_chat_beyond_bookmarks_are_not_replayed(site: FakeFunPay) -> None:
    """Чат, которого при запуске не было в списке, отдаёт только сообщения после запуска."""
    site.bookmarks_limit = 1
    site.open_chat(777, 3000, "buyer2")
    site.say("старое", author=3000, node=777)
    site.say("свежее в другом чате")
    fp = make_tools(site)
    seen = collect_messages(fp)

    async def scenario() -> None:
        await tick(fp)
        site.say("новое", author=3000, node=777)
        await tick(fp)

    run(fp, scenario)
    assert seen == ["новое"]


def test_order_pages_are_loaded_only_on_signals(site: FakeFunPay) -> None:
    fp = make_tools(site)

    @fp.router.on_new_order()
    async def on_new_order(order: types.Order) -> None:
        pass

    async def scenario() -> None:
        await tick(fp)
        await tick(fp)  # повторная сверка после прогрева
        site.requests.clear()
        await tick(fp)
        site.say("просто вопрос")
        await tick(fp)

    run(fp, scenario)
    assert site.requests == ["POST /runner/", "POST /runner/", "POST /runner/"]


def test_payment_and_confirmation_in_one_tick_are_both_seen(site: FakeFunPay) -> None:
    site.add_order("OPEN1")
    fp = make_tools(site)
    events: list[tuple[str, str]] = []

    @fp.router.on_new_order()
    async def on_new_order(order: types.Order) -> None:
        events.append(("new", str(order.order_id)))

    @fp.router.on_confirmed_orders()
    async def on_confirmed(order: types.Order) -> None:
        events.append(("confirmed", str(order.order_id)))

    async def scenario() -> None:
        await tick(fp)
        await tick(fp)
        counters_before = site.counters()
        site.pay("NEW1")
        site.confirm("OPEN1")
        assert site.counters() == counters_before  # тег счётчиков не изменился
        await tick(fp)

    run(fp, scenario)
    assert sorted(events) == [("confirmed", "OPEN1"), ("new", "NEW1")]


def test_date_change_at_midnight_is_not_an_order_event(site: FakeFunPay) -> None:
    site.add_order("OPEN1", date="Сегодня, 23:59")
    fp = make_tools(site)
    seen: list[str] = []

    @fp.router.on_new_order()
    async def on_new_order(order: types.Order) -> None:
        seen.append(str(order.order_id))

    async def scenario() -> None:
        await tick(fp)
        await tick(fp)
        site.order("OPEN1")["date"] = "Вчера, 23:59"
        site.pay("NEW1")
        await tick(fp)

    run(fp, scenario)
    assert seen == ["NEW1"]


def test_bot_answer_is_not_an_event_and_needs_no_chat_page(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen: list[str] = []

    @fp.router.on_message()
    async def on_message(message: types.Message) -> None:
        seen.append(message.text)
        await message.answer("Ответ бота")

    async def scenario() -> None:
        await tick(fp)
        site.say("Привет")
        await tick(fp)
        await tick(fp)

    run(fp, scenario)
    assert seen == ["Привет"]
    assert site.chats[NODE]["messages"][-1][1:] == (SHOP_ID, "Ответ бота")
    assert not any(request.startswith("GET /chat/") for request in site.requests)


def test_review_notification_reaches_review_handler(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen: list[tuple[str, int]] = []

    @fp.router.on_new_review()
    async def on_review(review: types.CurReview) -> None:
        seen.append((review.order_id, review.stars))

    async def scenario() -> None:
        await tick(fp)
        await tick(fp)
        site.leave_review("OLD0", "Отлично", 5)
        await tick(fp)
        await tick(fp)

    run(fp, scenario)
    assert seen == [("OLD0", 5)]


def test_failed_history_request_is_retried_without_loss_or_duplicates(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen = collect_messages(fp)

    async def scenario() -> None:
        await tick(fp)
        site.broken_chat_node_responses = 1
        site.say("раз")
        assert await tick(fp) == ["FpxGetUpdatesError"]
        assert seen == []
        site.say("два")
        assert await tick(fp) == []
        assert await tick(fp) == []

    run(fp, scenario)
    assert seen == ["раз", "два"]


def test_many_changed_chats_are_loaded_in_batches_of_ten(site: FakeFunPay) -> None:
    fp = make_tools(site)
    seen = collect_messages(fp)

    async def scenario() -> None:
        await tick(fp)
        for node in range(1000, 1012):
            site.open_chat(node, node + 5000, f"buyer{node}")
            site.say(f"from {node}", author=node + 5000, node=node)
        site.runner_calls.clear()
        await tick(fp)

    run(fp, scenario)
    assert sorted(seen) == sorted(f"from {node}" for node in range(1000, 1012))
    assert [len(call) for call in site.runner_calls] == [2, 10, 2]
