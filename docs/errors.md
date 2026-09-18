# Ошибки

Все исключения наследуются от `FpxError`. Можно ловить конкретные или целые группы.

---

## Дерево ошибок

```
FpxError
├── FpxAccountError
│   ├── FpxAuthError
│   ├── FpxGetChatsError
│   ├── FpxMessageDeliverError
│   ├── FpxRaisingLotError
│   ├── FpxRefundError
│   ├── FpxRequestError
│   ├── FpxLotEditingError
│   ├── FpxAnswerReviewError
│   ├── FpxDeleteReviewError
│   ├── FpxClientNotAttachedError
│   ├── FpxGetGameIDError
│   ├── FpxGetLastCategoryLotError
│   ├── FpxGetChatDataError
│   ├── FpxGetLotEditorInfoError
│   ├── FpxGetLotInfoError
│   ├── FpxGetOrderInfoError
│   ├── FpxGetUserDataError
│   ├── FpxGetUserSellsError
│   └── FpxGetProfileError
├── FpxParseError
│   └── FpxNullDataError
├── FpxRunnerError
│   └── FpxCriticalRunnerError
└── FpxHandlerError
    ├── FpxAttributeError
    └── FpxCommandArgsError
```

---

## Группы ошибок

**FpxAccountError** — всё что связано с запросами к FunPay. Лови её если не важно что именно упало.

**FpxParseError** — проблемы с парсингом HTML. Обычно означает что FunPay изменил вёрстку.

**FpxRunnerError** — проблемы с фоновым движком.

**FpxHandlerError** — ошибки хендлеров (неправильные аргументы и т.д.).

---

## Конкретные ошибки

| Класс | Когда кидается |
|-------|----------------|
| `FpxError` | Базовая ошибка, ловит всё |
| `FpxAuthError` | Передан неверный `golden_key` |
| `FpxGetChatsError` | Не удалось запросить список чатов |
| `FpxMessageDeliverError` | Сообщение не отправилось |
| `FpxRaisingLotError` | Не удалось поднять лоты (нет лотов или ошибка) |
| `FpxRefundError` | Возврат не прошёл |
| `FpxRequestError` | Сеть упала, сервер не ответил, превышены попытки |
| `FpxLotEditingError` | Цена не поменялась после редактирования |
| `FpxAnswerReviewError` | Ответ на отзыв не сохранился |
| `FpxDeleteReviewError` | Отзыв или ответ на отзыв не удалось удалить |
| `FpxClientNotAttachedError` | Попытка вызвать `.answer()` у объекта без привязки к клиенту |
| `FpxGetGameIDError` | Не удалось получить `game_id` категории |
| `FpxGetLastCategoryLotError` | Не удалось получить последний лот в категории |
| `FpxGetChatDataError` | Не удалось получить технические данные чата |
| `FpxGetLotEditorInfoError` | Не удалось получить данные формы редактора лота |
| `FpxGetLotInfoError` | Не удалось получить информацию о лоте |
| `FpxGetOrderInfoError` | Не удалось получить информацию о заказе |
| `FpxGetUserDataError` | Не удалось получить данные юзера (csrf_token, user_id) |
| `FpxGetUserSellsError` | Не удалось получить список продаж |
| `FpxGetProfileError` | Не удалось получить данные профиля |
| `FpxNullDataError` | Парсер получил пустую страницу (слетела сессия/изменилась вёрстка) |
| `FpxCriticalRunnerError` | Критический сбой раннера |
| `FpxAttributeError` | Неправильно переданы атрибуты в хендлер |
| `FpxCommandArgsError` | В команде не хватает аргументов |

---

## Примеры

**Ловим конкретную ошибку:**

```python
from fpx.utils.errors import FpxLotEditingError

try:
    await fp.account.editor.change_lot_price("123", "100")
except FpxLotEditingError as e:
    print(f"Цена не поменялась: {e.message}")
```

**Ловим группу:**

```python
from fpx.utils.errors import FpxAccountError

try:
    await message.answer("Привет")
    await fp.account.order.refund_order("123")
except FpxAccountError as e:
    print(f"Ошибка: {e.message}")
```
