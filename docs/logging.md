# Логирование

Библиотека использует стандартный модуль `logging` с иерархией логгеров под корневым именем `fpx`:

| Логгер | Откуда |
|--------|--------|
| `fpx` | корневой |
| `fpx.runner` | цикл polling и критические сбои раннера |
| `fpx.chat_runner` | обработка сообщений |
| `fpx.order_runner` | обработка заказов |
| `fpx.review_runner` | обработка отзывов |
| `fpx.chat_parser` | парсинг чатов |
| `fpx.order_parser` | парсинг заказов |
| `fpx.lot_parser` | парсинг лотов |
| `fpx.profile_parser` | парсинг профиля |

По умолчанию к `fpx` подключён `NullHandler` — библиотека ничего не выводит, пока ты сам не настроишь обработчик.

---

## Включить дебаг-логи

```python
import logging

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))

fpx_logger = logging.getLogger("fpx")
fpx_logger.setLevel(logging.DEBUG)
fpx_logger.addHandler(handler)
```

Логи пойдут только от `fpx.*` — остальные библиотеки не затрагиваются.

Пример вывода:

```
2026-06-19 12:00:01 [fpx.chat_runner] DEBUG: Ошибка при обработке сообщения: ...
```

---

## Логировать только конкретный модуль

```python
logging.getLogger("fpx.chat_runner").setLevel(logging.DEBUG)
```

---

## Писать в файл

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler("fpx.log", encoding="utf-8"), logging.StreamHandler()],
)

logging.getLogger("fpx").setLevel(logging.DEBUG)
```
