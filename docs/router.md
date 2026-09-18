# Роутер и хендлеры

Роутер — это штука которая связывает события с твоими функциями. Все декораторы висят на объекте `Router` — это либо `fp.router` (простой стиль), либо переменная `router`, которую ты сам вытащил через `router = fp.runner.router` или создал в отдельном файле через `Router()` (продвинутый стиль). Поведение одинаковое — в примерах ниже используется `fp.router`, но всё работает так же через `router`.

---

## Сообщения

### `@fp.router.on_message()`

Самый главный декоратор. Ловит все новые сообщения в чатах.

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `text` | `str` | Срабатывает если сообщение **начинается** с этого текста |
| `contains` | `str` или `list[str]` | Срабатывает если в сообщении есть эти слова |
| `regex` | `str` или `list[str]` | Регулярка (через `re.search`) |
| `custom` | `Callable` | Своя функция-проверка, должна вернуть `True`/`False` |
| `mapping` | `dict[str, str]` | Словарь `{'триггер': 'ответ'}`, ответит автоматически |
| `state` | `str` | Сработает только если у чата этот стейт FSM |
| `ignore_chat_id` | `str`, `int` или `list` | Черный список чатов (игнорит эти айди) |
| `ignore_sender` | `str` или `list[str]` | Черный список юзеров |
| `priority` | `int` | Приоритет, чем больше — тем раньше проверяется |

**В хендлер прилетает объект `Message`:**

```python
from fpx import types


@fp.router.on_message()
async def any_msg(message: types.Message):
    print(f"{message.sender}: {message.text}")
```

**Пример с фильтрами:**

```python
@fp.router.on_message(text="!привет")
async def cmd_hello(message: types.Message):
    await message.answer("Привет")


@fp.router.on_message(contains=["купить", "заказать"])
async def buy_intent(message: types.Message):
    await message.answer("Хочешь купить? Пиши !товар")


@fp.router.on_message(regex=r"^id\d+$")
async def by_regex(message: types.Message):
    await message.answer("Нашёл ID")


@fp.router.on_message(mapping={"привет": "Привет!", "как дела": "Норм"})
async def mapped(message: types.Message):
    # ответ уже отправлен автоматически, этот хендлер всё равно вызовется
    pass
```

**Совет:** mapping отвечает автоматически, но хендлер тоже вызывается. Если mapping сработал — не забудь поставить `return` если не хочешь чтобы дальнейший код выполнялся.

---

## Команды сообщений

### `fp.router.message_commands(dict)`

Регистрирует команды для чата. Ключ — команда (например `!start`), значение — асинхронная функция.

```python
async def start_cmd(message: types.Message):
    await message.answer("Привет, введи ник")


async def help_cmd(message: types.Message):
    await message.answer("Команды: !start, !help")


fp.router.message_commands({"!start": start_cmd, "!help": help_cmd})
```

В функцию-команду автоматически передаются:
- `message: types.Message` — если параметр аннотирован как `types.Message`
- `state: FSMContext` — если параметр аннотирован как `FSMContext`
- `Dependency(...)` — зависимости, смотри пример ниже

**Пример с Dependency:**

```python
from fpx import Dependency, types


async def get_user(message: types.Message):
    return {"name": message.sender, "vip": True}


async def vip_cmd(message: types.Message, user: dict = Dependency(get_user)):
    if user["vip"]:
        await message.answer("Ты VIP")


fp.router.message_commands({"!vip": vip_cmd})
```

Команды проверяются **до** обычных `on_message` хендлеров. Если команда сработала — обычные хендлеры для этого сообщения не вызываются.

---

## Заказы

### `@fp.router.on_orders(mapping=None)`

Ловит **все** события заказов (оплата, подтверждение, возврат). Не рекомендуется использовать вместе с узкими хендлерами чтобы избежать дублирования.

```python
@fp.router.on_orders()
async def all_orders(order: types.Order):
    print(f"Заказ {order.order_id}: {order.status}")
```

### `@fp.router.on_new_order(mapping=None)`

Только новые оплаченные заказы (статус "Оплачен" / "paid" / "відкрито").

```python
@fp.router.on_new_order(mapping=["ключ", "key"])
async def auto_key(order: types.Order):
    # сработает только если в описании есть "ключ" или "key"
    await order.answer("Вот твой ключ: ABC-123")
```

### `@fp.router.on_confirmed_orders(mapping=None)`

Только подтверждённые заказы (статус "Закрыт" / "closed" / "закрито").

```python
@fp.router.on_confirmed_orders()
async def confirmed(order: types.Order):
    await order.answer("Спасибо за подтверждение!")
```

### `@fp.router.on_refunded_orders(mapping=None)`

Только возвраты (статус "Возврат" / "refund" / "повернення").

```python
@fp.router.on_refunded_orders()
async def refund(order: types.Order):
    print(f"Возврат по заказу {order.order_id}")
```

### `fp.router.order_targets(dict)`

Регистрирует целевые команды для автовыдачи по новым заказам. Ключ — фрагмент описания заказа, значение — функция.

```python
async def sell_guide(order: types.Order):
    print(f"ЗАКАААЗ")
    await order.answer("Привет, введи свой ник")


fp.router.order_targets({"id: 133": sell_guide})
```

---

## Отзывы

### `@fp.router.on_new_review(stars=None)`

Ловит новые отзывы. Если `stars` указан — только с этим количеством звёзд.

```python
@fp.router.on_new_review(stars=5)
async def good_review(review: types.CurReview):
    await review.answer("Спасибо!")


@fp.router.on_new_review(stars=1)
async def bad_review(review: types.CurReview):
    await review.message_author("Давай решим проблему")
```

Можно вешать несколько декораторов на одну функцию:

```python
@fp.router.on_new_review(stars=1)
@fp.router.on_new_review(stars=2)
@fp.router.on_new_review(stars=3)
async def handle_bad(review: types.CurReview):
    print(f"Плохой отзыв: {review.stars} звезд")
```

---

## Категории (мониторинг цен)

### `@fp.router.on_lot_category()`

Следит за изменениями цен в категориях обычных лотов. Срабатывает когда кто-то меняет цену или появляется новый топ-1. Игнорит твои собственные лоты.

```python
@fp.router.on_lot_category()
async def lot_changed(lot: types.CategoryLastLot):
    print(f"Новая цена в категории {lot.category_id}: {lot.price}")
```

### `@fp.router.on_chip_category()`

То же самое но для чипсов (короткие лоты под валюты).

```python
@fp.router.on_chip_category()
async def chip_changed(lot: types.CategoryLastLot):
    print(f"Чипсы: новая цена {lot.price}, лот {lot.offer_id}")
```

---

## Системные хендлеры

### `@fp.router.on_startup()`

Срабатывает один раз при запуске polling, после прогрева кеша.

```python
@fp.router.on_startup()
async def startup():
    print("Бот запущен!")
```

### `@fp.router.on_flood()`

Срабатывает когда FunPay присылает 429 (флуд-контроль). В функцию передаётся количество секунд ожидания.

```python
@fp.router.on_flood()
async def flood_handler(seconds):
    print(f"Флуд на {seconds} секунд")
```

### `@fp.router.on_error()`

Ловит ошибки при обработке событий и критические сбои polling (`FpxCriticalRunnerError`).
Для сбоя цикла `event` будет `None`.

```python
@fp.router.on_error()
async def error_handler(event, error):
    print(f"Ошибка: {error}")
```

---

## Подключение внешних роутеров

### `router.include_router(другой_router)`

Хендлеры не обязательно регистрировать в одном файле. В любом модуле можно создать свой `Router` через `from fpx import Router`, навесить на него хендлеры, а затем подключить к главному роутеру методом `include_router`.

**handlers/test.py:**

```python
from fpx import Router, types

other_router = Router()


@other_router.on_message(text="!test")
async def test(message: types.Message):
    await message.answer("OK")
```

**main.py:**

```python
from handlers.test import other_router

# простой стиль:
fp.router.include_router(other_router)

# продвинутый стиль (если ты вытащил router = fp.runner.router):
# router.include_router(other_router)
```

Метод объединяет хендлеры обоих роутеров — после вызова `fp.router` (или `router`) будет знать обо всех хендлерах из `other_router`. Удобно для плагинов и разбивки большого бота на модули по смыслу (например, `handlers/messages.py`, `handlers/orders.py`, `handlers/reviews.py`).
