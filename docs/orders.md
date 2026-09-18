# Заказы

Отслеживание заказов, автовыдача, возвраты.

---

## Хендлеры

### `@fp.router.on_orders(mapping=None)`

Все события заказов (оплата, подтверждение, возврат).

⚠️ Не используй вместе с узкими хендлерами — будет дублирование.

```python
from fpx import types


@fp.router.on_orders()
async def any_order(order: types.Order):
    print(f"Заказ {order.order_id}, статус: {order.status}")
```

### `@fp.router.on_new_order(mapping=None)`

Только новые оплаченные заказы.

```python
@fp.router.on_new_order()
async def new_order(order: types.Order):
    print(f"Новый заказ #{order.order_id} от {order.client_name}")
    await order.answer(f'Заказ "{order.name}" принят!')
```

**mapping** — список ключевых слов. Хендлер сработает только если одно из слов есть в описании заказа:

```python
@fp.router.on_new_order(mapping=["ключ", "key"])
async def auto_key(order: types.Order):
    await order.answer("Вот твой ключ: XXX-YYY-ZZZ")
```

### `@fp.router.on_confirmed_orders(mapping=None)`

Только подтверждённые заказы (покупатель нажал "Подтвердить выполнение").

```python
@fp.router.on_confirmed_orders()
async def confirmed(order: types.Order):
    await order.answer("Спасибо за подтверждение! Буду рад отзыву")
```

### `@fp.router.on_refunded_orders(mapping=None)`

Только возвраты.

```python
@fp.router.on_refunded_orders()
async def refunded(order: types.Order):
    print(f"Возврат: {order.order_id}")
```

---

## Объект Order

| Поле | Тип | Описание |
|------|-----|----------|
| `order_id` | `str` | ID заказа |
| `chat_id` | `str` | ID чата |
| `order_time` | `str` | Время заказа |
| `description` | `str` | Описание (что ввёл покупатель) |
| `client_name` | `str` | Ник покупателя |
| `price` | `float` | Цена |
| `amount` | `int` | Количество |
| `status` | `str` | Статус (Оплачен / Paid / Відкрито, Закрыт / Closed / Закрито, Возврат / Refunded / Повернення) |
| `name` | `str` | Название товара |
| `category` | `str` | Категория |
| `review` | `dict` | Отзыв (если есть) |

### Методы

**`await order.answer(answer_text: str)`** — отправить сообщение в чат заказа. Поддерживает форматирование:
- `{order_id}` — ID заказа
- `{order_time}` — время
- `{client_name}` — ник покупателя
- `{order_name}` — название товара

---

## OrderManager (через account.order)

### `await fp.account.order.get_order_details(order_id)`

Полная информация о заказе со страницы `/orders/{id}/`.

```python
order = await fp.account.order.get_order_details("ABC123")
print(order.status)
print(order.description)
```

### `await fp.account.order.refund_order(order_id)`

Возврат денег по заказу.

```python
await fp.account.order.refund_order("ABC123")
```

Возвращает `True` если возврат прошёл. При ошибке — `FpxRefundError`.

---

## Альтернативный доступ через `fpx.services`

Те же методы доступны через отдельно объявленный `OrderManager` из `fpx.services`, если хочется явно держать его как отдельную переменную:

```python
from fpx.services import OrderManager

order_mgr = OrderManager(fp.account)
details = await order_mgr.get_order_details("ABC123")
await order_mgr.refund_order("ABC123")
```
