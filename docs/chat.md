# Чаты и сообщения

Всё что связано с получением, отправкой и обработкой сообщений.

---

## Хендлеры (через роутер)

Основной способ — через `@fp.router.on_message()`. Подробно описано в разделе [Роутер](router.md).

```python
from fpx import types


@fp.router.on_message()
async def any_msg(message: types.Message):
    print(f"{message.sender}: {message.text}")
    await message.answer("Принято")
```

### Команды

```python
async def status_cmd(message: types.Message):
    await message.answer("Бот работает")


fp.router.message_commands({"!status": status_cmd})
```

---

## Объект Message

Прилетает в хендлеры. Содержит:

| Поле | Тип | Описание |
|------|-----|----------|
| `sender` | `str` | Ник отправителя |
| `chat_id` | `str` | ID чата (node) |
| `text` | `str` | Текст сообщения |
| `is_system` | `bool` | Системное ли сообщение |

### Методы

**`await message.answer(answer_text: str)`** — ответить в тот же чат. Поддерживает форматирование:
- `{sender}` — ник отправителя
- `{chat_id}` — ID чата
- `{text}` — текст сообщения

```python
await message.answer("Привет, {sender}! Твой ID чата: {chat_id}")
```

---

## Не помечать чаты прочитанными (`read_messages`)

По умолчанию, чтобы получить сообщения, раннер открывает изменившиеся чаты, как это делает сайт FunPay. Из-за этого чат помечается прочитанным, и в браузере или приложении вы не увидите, что вам написали.

Параметр `read_messages` отключает это поведение:

```python
fp = FunPayTools(gkey)
fp.read_messages = False  # чаты не открываются, остаются непрочитанными

await fp.runner.start_polling(3, is_background=True)
```

| Значение | Поведение |
|----------|-----------|
| `True` (по умолчанию) | Раннер загружает историю изменившегося чата. Чат помечается прочитанным. Хендлеры получают все новые сообщения, включая пришедшие подряд. |
| `False` | История чата не загружается. Сообщение берётся из списка чатов, чат остаётся непрочитанным. |

Значение читается на каждом тике, поэтому его можно менять в любой момент, в том числе после `start_polling`:

```python
fp.read_messages = False
print(fp.read_messages)  # False
```

### Ограничения режима `read_messages = False`

Сообщение берётся из превью в списке чатов, а не из самой переписки. Поэтому:

- **Только последнее сообщение.** Если между двумя тиками в чат пришло несколько сообщений, хендлеры получат только последнее. Чем меньше `timer` в `start_polling`, тем реже это случается.
- **Оповещения FunPay не отличить от обычных сообщений.** В превью нет признака системного сообщения, поэтому `message.is_system` всегда `False`. Сообщения вроде «покупатель оплатил заказ» попадут в `on_message` как обычные. Страницы заказов и отзывов при этом по-прежнему обновляются по смене счётчиков, но не по оповещению в чате.
- **Свои сообщения не обрабатываются.** В превью автором всегда указан собеседник, даже если последнее сообщение отправили вы. Чтобы бот не реагировал на собственные ответы, обрабатываются только чаты, которые FunPay пометил непрочитанными. Если вы сами прочитали сообщение в браузере до того, как раннер его забрал, хендлер не сработает.
- **`message.answer()` и `send_message()` открывают чат.** Для отправки нужно имя чата (`node_name`) и `csrf_token`, и FunPay отдаёт их только со страницы чата. Она загружается один раз на каждый чат, пока имя не сохранено, и при этом чат помечается прочитанным. Чтобы чат остался непрочитанным, не отвечайте в нём из хендлера.

### Как это работает

В режиме по умолчанию раннер на каждом тике запрашивает через `/runner/` список чатов (`chat_bookmarks`), а для изменившихся чатов шлёт ещё запрос `chat_node`, именно он помечает чат прочитанным. При `read_messages = False` запрос `chat_node` не отправляется, а сообщение собирается из `chat_bookmarks`, который в любом случае приходит каждый тик.

Параметр работает и в `legacy_polling=True`, но там фильтра по непрочитанным нет, поэтому свои сообщения могут попасть в хендлеры. Для режима без чтения используйте стандартный polling.

---

## ChatManager (через account.chat)

Методы для работы с чатами напрямую, вне хендлеров.

### `await fp.account.chat.get_chats()`

Возвращает список всех чатов на аккаунте.

```python
chats = await fp.account.chat.get_chats()
for chat in chats:
    print(f"{chat.username}: {chat.last_msg}")
```

Возвращает `list[Chat]`, каждый объект содержит:
- `id` — ID чата (node)
- `username` — Ник собеседника
- `last_msg` — Последнее сообщение
- `date` — Дата
- `link` — Ссылка на чат
- `is_unread` — Непрочитанное ли

### `await fp.account.chat.send_message(chat_id, text)`

Отправить сообщение в чат по его ID.

```python
await fp.account.chat.send_message("12345678", "Привет")
```

### `await fp.account.chat.send_image(chat_id, image_id)`

Отправить изображение в чат по его ID.

```python
image_id = await fp.account.upload_image("photo.jpg")
await fp.account.chat.send_image("12345678", image_id)
```

**Аргументы:**
- `chat_id` (str) -- ID чата.
- `image_id` (str) -- ID изображения на FunPay, полученный через `fp.account.upload_image`.

**Возвращает** словарь ответа от FunPay.

**Исключения:** `FpxMessageDeliverError`.

### `await fp.account.chat.ban_chat(chat_id)`

Блокирует чат — то же действие, что кнопка «Заблокировать» в шапке переписки.

FunPay делает это через `POST /chat/mute` с `node_id` чата и `mute=1`.

```python
await fp.account.chat.ban_chat("12345678")
```

Если передан системный ID вида `users-123-456`, числовой `data-id` берётся со страницы чата.

**Аргументы:**
- `chat_id` (int | str) — ID чата (node / data-id).

**Возвращает** `True` при успехе.

**Исключения:** `FpxBanChatError`.

### `await fp.account.chat.get_chat_data(chat_id)`

Получает технические данные чата (csrf_token, node_name, последнее сообщение).

```python
data = await fp.account.chat.get_chat_data("12345678")
print(data.csrf_token)
print(data.last_message.text)
```

Возвращает `ChatData`:
- `node_name` — системный ID (например `users-12345-67890`)
- `csrf_token` — токен для POST-запросов
- `user_id` — твой ID
- `last_message` — объект `Message` (последнее сообщение)

---

## Альтернативный доступ через `fpx.services`

Все методы выше доступны и так же через `fp.account.chat`, и через отдельно объявленный `ChatManager` из `fpx.services` - оба варианта работают с тем же самым аккаунтом, разница только в стиле кода:

```python
from fpx.services import ChatManager

chat = ChatManager(fp.account)
chats = await chat.get_chats()
```

`ChatManager` не создаёт ничего своего — он просто принимает уже существующий `account` (например `fp.account`) и даёт к нему ещё один способ доступа.
