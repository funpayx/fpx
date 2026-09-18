# Отзывы

Отслеживание новых отзывов, ответ на них, удаление ответа, написание автору в чат.

---

## Хендлер

### `@fp.router.on_new_review(stars=None)`

Ловит новые отзывы. Если `stars` не указан — ловит все.

```python
from fpx import types


@fp.router.on_new_review(stars=5)
async def five_stars(review: types.CurReview):
    await review.answer("Спасибо за отзыв!")


@fp.router.on_new_review(stars=1)
@fp.router.on_new_review(stars=2)
@fp.router.on_new_review(stars=3)
async def bad_review(review: types.CurReview):
    await review.message_author("Извини, давай решим проблему")
```

---

## Объект CurReview

| Поле | Тип | Описание |
|------|-----|----------|
| `text` | `str` | Текст отзыва |
| `stars` | `int` | Звёзды (1-5) |
| `author` | `str` | Ник автора |
| `order_id` | `str` | ID заказа |
| `order` | `Order` | Объект заказа (подтягивается автоматически) |

### Методы

**`await review.answer(answer_text: str)`** — ответить на отзыв на странице профиля. Поддерживает форматирование:
- `{author}` — автор отзыва
- `{order_id}` — ID заказа
- `{order_name}` — название товара
- `{order_time}` — время заказа
- `{stars}` — количество звёзд

**`await review.message_author(message_text: str)`** — написать автору отзыва в чат заказа. Форматирование то же самое.

**`await review.delete()`** — удалить свой отзыв или ответ на отзыв. Не требует объект заказа, достаточно `order_id`.

```python
await review.answer("Спасибо, {author}!")
await review.message_author("{author}, спасибо за {stars} звёзд!")
await review.delete()
```

---

## ReviewManager (через account.review)

### `await fp.account.review.get_review(order_id)`

Получить отзыв к конкретному заказу.

```python
review = await fp.account.review.get_review("ABC123")
print(review.text)
print(review.stars)
print(review.answer)  # твой ответ (если есть)
```

Возвращает объект `Review` с полями: `text`, `stars`, `answer`.

### `await fp.account.review.review_answer(order_id, text)`

Ответить на отзыв вручную.

```python
await fp.account.review.review_answer("ABC123", "Спасибо!")
```

Возвращает `True` при успехе.

### `await fp.account.review.delete_review(order_id)`

Удалить свой отзыв или ответ на отзыв по ID заказа. FunPay принимает `POST /orders/reviewDelete` с `authorId` текущего аккаунта и `orderId`.

```python
await fp.account.review.delete_review("ABC123")
```

Возвращает `True` при успехе. При ошибке кидает `FpxDeleteReviewError`.

---

## Альтернативный доступ через `fpx.services`

```python
from fpx.services import ReviewManager

review_mgr = ReviewManager(fp.account)
review = await review_mgr.get_review("ABC123")
```
