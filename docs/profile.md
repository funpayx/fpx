# Профиль, баланс, продажи

Всё через `fp.account.profile`.

---

## ProfileManager

### `await fp.account.profile.get_user_data()`

Запрашивает данные юзера, сохраняет csrf_token и user_id в кеш. Вызывается автоматически при первом POST-запросе, но можно вызвать и вручную.

```python
data = await fp.account.profile.get_user_data()
print(data.user_id)
print(data.csrf_token)
```

Возвращает `UserData`.

### `await fp.account.profile.get_my_sells(limit=0)`

Список твоих продаж.

```python
orders = await fp.account.profile.get_my_sells(limit=25)
for order in orders:
    print(f"#{order.order_id}: {order.name} — {order.price} ({order.status})")
```

`limit=0` — вернёт все заказы. Возвращает `list[Order]`.

### `await fp.account.profile.profile(user_id=None)`

Данные профиля. Если `user_id` не передан — берёт свой.

```python
profile = await fp.account.profile.profile()
print(f"Категорий: {len(profile.category_ids)}")
print(f"Лотов: {len(profile.lots)}")

for review in profile.reviews:
    print(f"[{review.stars}/5] {review.author}: {review.text}")
```

Возвращает `Profile`:
- `category_ids` — список ID категорий
- `lots` — список `LotInfo` (name, id)
- `reviews` — список `CurReview` (text, stars, author, order_id)

### `await fp.account.profile.get_balance()`

Баланс аккаунта.

```python
balance = await fp.account.profile.get_balance()
print(f"{balance.rub} ₽")
print(f"{balance.usd} $")
print(f"{balance.eur} €")
```

Возвращает `Balance`.

### `await fp.account.profile.check_banned()`

Проверяет, заблокирован ли текущий аккаунт. FunPay отвечает `200` на `/account/blocked` при бане и `404`, если бана нет.

```python
if await fp.account.profile.check_banned():
    print("Аккаунт заблокирован")
```

Возвращает `bool`.

---

## Альтернативный доступ через `fpx.services`

```python
from fpx.services import ProfileManager

profile_mgr = ProfileManager(fp.account)
balance = await profile_mgr.get_balance()
```
