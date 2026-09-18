<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
</p>

<h1 align="center">fpx</h1>

<p align="center">
  <strong>fpx</strong> - асинхронный фреймворк и библиотека для упрощения взаимодействия с <a href="https://funpay.com">funpay.com</a>, с целью максимальной скорости и простоты входа
</p>

<p align="center">
  <a href="https://github.com/bymyforge/fpx" target="_blank">
<img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub">
</a>
<a href="https://gitlab.com/funpayx/fpx" target="_blank">
<img src="https://img.shields.io/badge/GitLab-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white" alt="GitLab">
</a>
<a href="https://fpx.readthedocs.io/ru/latest/" target="_blank">
<img src="https://img.shields.io/badge/Документация-00b0ff?style=for-the-badge&logo=read-the-docs&logoColor=white" alt="Read the Docs">
</a>
<a href="https://t.me/fpx_engine" target="_blank">
<img src="https://img.shields.io/badge/Телеграм_Чат-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Телеграм Чат">
</a>
<a href="https://pypi.org/project/fpx-engine/" target="_blank">
<img src="https://img.shields.io/badge/PyPI-3775A9?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI">
</a>
</p>

---

Оригинальный сайт не предоставляет публичного API для разработчиков. Фреймворк написан в качестве исправления данной проблемы. 

## Особенности
* В отличие от **FunPayAPI** фреймворк работает на декораторах, что сильно упрощает разработку
* Стиль проекта сформирован из популярных фреймворков, таких как **aiogram, fastapi, starlette**
* Очень простой код, ниже реализован пример

## Установка    
Установка библиотеки:      
```
pip install fpx-engine  
``` 
Обновление библиотеки:  
```
pip install -U fpx-engine
```

## Пример использования

Получение нового сообщения и автоматический ответ на него:

```python
import asyncio
from fpx import FunPayTools, types


async def main():
    # инициализируем аккаунт (golden_key - куки твоего аккаунта на funpay.com)
    fp = FunPayTools("golden_key")

    # ловим сообщение
    @fp.router.on_message()
    async def answer_message(message: types.Message):
        # отвечаем на сообщение
        await message.answer("Привет")

    # запускаем приём событий
    await fp.runner.start_polling(3, is_background=True)
    await fp.runner.idle()


if __name__ == "__main__":
    asyncio.run(main())
```

## Архитектура

### Как устроен приём событий
Из-за отсутсвтия вебхуков или подобной технологии на фанпей, fpx работает через polling, раз в заданное кол-во секунд делает несколько запросов на фанпей, а именно отслеживание сообщений, заказов, отзывов, демперов, записывает их в кеш и сравнивает новые данные со старыми, если находит отличие то вызывает хендлер. 

### Фильтры в хендлерах
Вместо ручной обработки есть возможность использовать множество встроенных фильтров, но при желании всё также можно добавить свой кастомный фильтр.  
Пример: 
```
@fp.router.on_message(text='start')
async def cmd_start(message: types.Message):
    await message.answer('На связи')
```

### Отличия от других утилит
В отличие от коллег, fpx полностью асинхронный фреймворк, с максимальной простотой входа. У фреймворка есть полезные встроенные инструменты, в пример можно взять fp.router.message_commands() который регистрирует команды одной строчкой. 

## Экосистема

Вы можете использовать телеграм бот <a href="https://github.com/bymyforge/FunPayX">FunPayX</a> как оболочку над фреймворком с уже встроенными автоматизациями
