# Модели

Все датаклассы которые используются во фреймворке. Самому их создавать не нужно — фреймворк отдаёт уже готовые объекты в хендлеры. Импортировать модели можно через `from fpx import types`, а затем обращаться как `types.Message`, `types.Order`, `types.CurReview`, `types.CategoryLastLot`.

---

## Message

Входящее сообщение. Прилетает в хендлеры `on_message`.

| Поле | Тип | Описание |
|------|-----|----------|
| `sender` | `str` | Ник отправителя |
| `chat_id` | `str` | ID чата (node) |
| `text` | `str` | Текст сообщения |
| `is_system` | `bool` | Системное ли сообщение |

**Метод:** `await message.answer(answer_text: str)` — ответить в чат. Поддерживает `{sender}`, `{chat_id}`, `{text}`.

---

## Order

Заказ. Прилетает в хендлеры заказов.

| Поле | Тип | Описание |
|------|-----|----------|
| `order_id` | `str` | ID заказа |
| `chat_id` | `str` | ID чата |
| `order_time` | `str` | Время заказа |
| `description` | `str` | Описание (данные от покупателя) |
| `client_name` | `str` | Ник покупателя |
| `price` | `float` | Цена |
| `amount` | `int` | Количество |
| `topup_data` | `str` | Данные для пополнения (ник, ссылка) |
| `status` | `str` | Статус |
| `name` | `str` | Название товара |
| `category` | `str` | Категория |
| `review` | `dict` | Отзыв |

**Метод:** `await order.answer(answer_text: str)` — ответить в чат заказа. Поддерживает `{order_id}`, `{order_time}`, `{client_name}`, `{order_name}`.

---

## Purchase

Покупка. Братский класс [`Order`](#order) — те же поля и тот же метод `.answer()`, но
описывает не заказ у вас, а вашу покупку у другого продавца. Прилетает в хендлеры покупок
(см. [Покупки](purchases.md)).

| Поле | Тип | Описание |
|------|-----|----------|
| `order_id` | `str` | ID заказа |
| `chat_id` | `str` | ID чата |
| `order_time` | `str` | Время заказа |
| `description` | `str` | Описание (данные, которые вы ввели при покупке) |
| `client_name` | `str` | Ник продавца |
| `price` | `float` | Цена |
| `amount` | `int` | Количество |
| `topup_data` | `str` | Данные для пополнения (ник, ссылка) |
| `status` | `str` | Статус |
| `name` | `str` | Название товара |
| `category` | `str` | Категория |
| `review` | `dict` | Отзыв |

**Метод:** `await purchase.answer(answer_text: str)` — ответить в чат покупки. Поддерживает `{order_id}`, `{order_time}`, `{client_name}`, `{order_name}`.
В отличие от `Order`, метода `.refund()` у `Purchase` нет.

---

## CurReview

Текущий отзыв. Прилетает в хендлер `on_new_review`. Автоматически подтягивает данные заказа.

| Поле | Тип | Описание |
|------|-----|----------|
| `text` | `str` | Текст отзыва |
| `stars` | `int` | Звёзды (1-5) |
| `author` | `str` | Ник автора |
| `order_id` | `str` | ID заказа |
| `order` | `Order` | Объект заказа |

**Методы:**
- `await review.answer(answer_text)` — ответ на отзыв в профиле. Поддерживает `{author}`, `{order_id}`, `{order_name}`, `{order_time}`, `{stars}`
- `await review.message_author(message_text)` — написать автору в чат
- `await review.delete()` — удалить свой отзыв или ответ на отзыв

---

## Review

Статический отзыв (без связи с заказом). Возвращается `get_review`.

| Поле | Тип | Описание |
|------|-----|----------|
| `text` | `str` | Текст отзыва |
| `stars` | `int` | Звёзды |
| `answer` | `str` | Твой ответ |

---

## Chat

Чат из списка диалогов.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `str` | ID чата (node) |
| `node_msg_id` | `int` | ID последнего сообщения |
| `username` | `str` | Ник собеседника |
| `last_msg` | `str` | Текст последнего сообщения |
| `date` | `str` | Дата |
| `link` | `str` | Ссылка |
| `is_unread` | `bool` | Непрочитанное |

---

## ChatData

Технические данные чата.

| Поле | Тип | Описание |
|------|-----|----------|
| `node_name` | `str` | Системный ID (users-12345-67890) |
| `csrf_token` | `str` | CSRF-токен |
| `user_id` | `str` | Твой ID |
| `last_message` | `Message` | Последнее сообщение |

---

## CategoryLastLot

Информация о лоте в категории.

| Поле | Тип | Описание |
|------|-----|----------|
| `category_id` | `str` | ID категории |
| `filtration` | `str` | Фильтр |
| `price` | `float` | Цена |
| `offer_id` | `str` | ID лота |
| `owner_username` | `str` | Ник продавца |

---

## CurrentLotInfo

Информация о конкретном лоте.

| Поле | Тип | Описание |
|------|-----|----------|
| `short_desc` | `str` | Краткое описание |
| `description` | `str` | Полное описание |
| `price` | `float` | Цена |

---

## LotInfo

Лот из профиля.

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | `str` | Название |
| `id` | `str` | ID лота |

---

## LotEditor

Технический объект редактора лота.

| Поле | Тип | Описание |
|------|-----|----------|
| `csrf_token` | `str` | Токен |
| `form_created_at` | `str` | Время создания формы |
| `offer_id` | `str` | ID оффера |
| `node_id` | `str` | ID нода |
| `location` | `str` | Локация |
| `deleted` | `str` | Флаг удаления |
| `fields` | `dict` | Все поля лота |

---

## UserData

Данные юзера.

| Поле | Тип | Описание |
|------|-----|----------|
| `csrf_token` | `str` | CSRF-токен |
| `user_id` | `str` | ID юзера |

---

## Profile

Данные профиля.

| Поле | Тип | Описание |
|------|-----|----------|
| `category_ids` | `list` | ID категорий с лотами |
| `lots` | `list[LotInfo]` | Список лотов |
| `reviews` | `list[CurReview]` | Отзывы |

---

## Balance

Баланс аккаунта.

| Поле | Тип | Описание |
|------|-----|----------|
| `rub` | `float` | Рубли |
| `usd` | `float` | Доллары |
| `eur` | `float` | Евро |

---

## Dependency

Зависимость для хендлеров.

```python
from fpx import Dependency, types


def get_user(message):
    return {"name": message.sender}


async def handler(message: types.Message, user: dict = Dependency(get_user)):
    print(user)
```
