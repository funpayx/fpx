# fpx API Documentation

Асинхронный Python-фреймворк для автоматизации FunPay.

---

## Роутер / Обработчики событий

### `Router.include_router`

```
Метод для подключения плагинов и сторонних роутеров
```

### `Router.message_commands`

```
Метод для регистрации команд автоматизации сообщений.

Args:
    target_dict (dict): Словарь вида {'command': answer_new_def, '!start': another_func}
```

### `Router.on_chip_category`

```
Декоратор отслеживает снижение цен на чипсах(коротких лотов под валюты).    

Returns:
    CategoryLastLot: Объект, содержащий:    
        - price (float): Цена лота      
        - offer_id (str): Айди лота
```

### `Router.on_confirmed_orders`

```
Декоратор, который отслеживает только событие подтверждёния заказа.

Returns:
    Order: Объект, содержащий:      
        - order_id (str): Уникальный ID заказа          
        - order_time (str): Время оплаты заказа     
        - client_name (str): Имя клиента
        - price (str): Цена товара     
        - status (str): Статус заказа   
        - name (str): Название товара   
        - anwer (method): При указании текста в аргументах, отвечает на сообщение
```

### `Router.on_error`

```
Декоратор для отлова ошибок
```

### `Router.on_flood`

```
Декоратор отслеживает флуд в системе
```

### `Router.on_lot_category`

```
Декоратор отслеживает снижение цен на лоты.     

Returns:
    CategoryLastLot: Объект, содержащий:        
        - price (float): Цена лота      
        - offer_id (str): Айди лота
```

### `Router.on_message`

```
Декоратор отслеживает новые сообщения.
Важно: если сделать несколько хендлеров с одинаковыми фильтрами, то подходящее
сообщение будет вызвано только под первый хендлер.

Внимание: если пользователь отправит два одинаковых сообщения подряд —
второе детектировано не будет, так как кеш не изменился. Это намеренное
поведение для защиты от спама.

Args:
    - text (str | None): Срабатывает, если сообщение НАЧИНАЕТСЯ с этого текста.
        Регистр игнорируется — 'Привет' и 'привет' равнозначны.
    - contains (str | list | None): Срабатывает, если в сообщении
        есть эти ключевые слова (можно строку или список слов).
    - regex (str | list | None): Фильтр по регуляркам (re.search).
        Ест сырые строки типа r'^id\d+$' или список паттернов.
    - custom (Callable | None): Твоя кастомная проверка.
        Сюда можно закинуть лямбду или синхронную/асинхронную функцию, которая возвращает True/False.
    - mapping (dict | None): Умный автоответчик.
        Передаешь словарь {'триггер': 'ответ'}, и скрипт сам ответит за тебя, подставив переменные.
    - state (str | None): Фильтр по состоянию FSM.
        Хендлер сработает только если текущий стейт чата совпадает с этим.
    - ignore_chat_id (str | int | list | None): Черный список для чатов.
        Айдишники отсюда скрипт будет просто игнорить (одиночный ID или список).
    - ignore_sender (str | list | None): Черный список для юзеров. Скрипт проигнорит сообщения от них.
    - priority (int | None): Приоритет декоратора, чем выше тем раньше проверяется (12 проверит раньше чем 11)

Returns:
    Message: Объект, содержащий:
        - sender (str): Имя отправителя
        - chat_id (str): Айди чата (node id)
        - text (str): Сообщение, которое было отправлено в этом чате
        - is_system (bool): Системное ли сообщение
        - answer (method): При указании текста в аргументах, отвечает на сообщение
```

### `Router.on_new_order`

```
Декоратор, который отслеживает только новые заказы.

Returns:
    Order: Объект, содержащий:      
        - order_id (str): Уникальный ID заказа          
        - order_time (str): Время оплаты заказа     
        - client_name (str): Имя клиента
        - price (str): Цена товара     
        - status (str): Статус заказа   
        - name (str): Название товара   
        - anwer (method): При указании текста в аргументах, отвечает на сообщение
```

### `Router.on_new_review`

```
Декоратор отслеживает новые отзывы.

Args:
    - stars (int | None): Количество звёзд, на которое хендлер будет реагировать (не обязательно передавать).

Returns:
    CurReview: Объект, содержащий:        
        - text (str): Текст отзыва  
        - stars (int): Кол-во звёзд, оставленных под отзывом    
        - author (str): Автор отзыва    
        - item_name (str): Заказ, под которым оставлен отзыв
```

### `Router.on_orders`

```
Декоратор отслеживает все события заказов.
Не рекомендуется использовать вместе с on_cofirmed_orders, on_new_order, on_refunded_orders во избежание дублирования событий.

Returns:
    Order: Объект, содержащий:      
        - order_id (str): Уникальный ID заказа          
        - description (str): Описание лота
        - order_time (str): Время оплаты заказа     
        - client_name (str): Имя клиента
        - price (str): Цена товара     
        - status (str): Статус заказа   
        - name (str): Название товара   
        - anwer (method): При указании текста в аргументах, отвечает на сообщение
```

### `Router.on_refunded_orders`

```
Декоратор отслеживает события возврата заказов.

Returns:
    Order: Объект, содержащий:      
        - order_id (str): Уникальный ID заказа          
        - order_time (str): Время оплаты заказа     
        - client_name (str): Имя клиента
        - price (str): Цена товара     
        - status (str): Статус заказа   
        - name (str): Название товара   
        - anwer (method): При указании текста в аргументах, отвечает на сообщение
```

### `Router.on_startup`

```
Декоратор отслеживает запуск раннера
```

### `Router.order_targets`

```
Метод для регистрации команд автоматизации новых заказов.

Args:
    target_dict (dict): Словарь вида {'target': answer_new_def, 'моя пометка в описании': another_func}
```

## Раннер

### `ChatRunner._compare_chat_cache`

```
Сравнивает старый кеш сообщений с новым, если находит отличия, выносит сообщение в список, после чего возвращает полный список
```

### `ChatRunner._update_chat_cache`

```
Обновляет кеш последних чатов
```

### `FpxCriticalRunnerError`

```
Критический сбой раннера, требующий остановки или жесткого перезапуска.
```

### `FpxRunnerError`

```
Ошибки фонового раннера проверок.
```

### `OrderRunner._compare_order_cache`

```
Сравнивает старый и новый кеш заказов
```

### `OrderRunner._update_order_cache`

```
Обновляет кеш заказов в раннере
```

### `ReviewRunner._compare_review_cache`

```
Сравнивает кеш отзывов
```

### `ReviewRunner._update_review_cache`

```
Обновляет кеш отзывов
```

### `Runner._cache_runner`

```
Управляет кешем
```

### `Runner._warm_up`

```
Прогрев кеша
```

### `Runner.idle`

```
Зацикливает выполнение программы, чтобы фоновые задачи не закрылись.
```

### `Runner.start_polling`

```
Запускает поиск новых событий.

Args:
    timer (str): Задержка в секундах, раз в которую будет происходить обновление кеша (рекомендуемо 3-5 сек).   
    is_background (bool): По дефолту True(в фоне). Определяет, будет ли функция запущена в фоне или нет (если не в фоне, блокирует остальные процессы). 
    watch_lots (list): Можно не передавать. Список категорий лотов, которые будет проверять скрипт.     
    watch_chips (list): Можно не передавать. Список категорий чипсов(коротких лотов под валюты), которые будет проверять скрипт.

Неизвестные ошибки оборачиваются в FpxCriticalRunnerError, логируются
и прокидываются в on_error. Фоновая задача сохраняется в Runner.polling_task
(и FunPayTools.polling_task) и отслеживается через add_done_callback.
```

### `Runner.stop_polling`

```
Останавливает цикл polling и отменяет фоновую задачу, если она есть.
```

### `Runner.polling_task`

```
Фоновая задача polling либо None, если polling не запущен в фоне.
```

## Менеджеры аккаунта

### `Account`

```
Взаимодействует с аккаунтом.
```

### `AccountData`

```
Хранит данные аккаунта
```

### `AddonsManager.get_game_id`

```
Получает game_id.

Args:
    category_id (str | int): ID подкатегории.
        
Returns:    
    str | int: ID игры.

Raises:
    FpxGetGameIDError: Ошибка запроса ID игры
```

### `CategoryManager.get_chip_category_last_lot`

```
Находит самый дешевый лот краткий в категории по каждому из фильтров.  

Args:
    lot_category_id (int | str): ID категории лота          

Returns:
    List[CategoryLastLot]: Объект, содержащий в себе:          
        - category_id (str): ID категории   
        - filtration (str): Название фильтра    
        - price (float): Цена лота  
        - offer_id (str): ID лота   
        - owner_username (str): Юзернейм владельца лота     
    Raises:
        FpxGetLastCategoryLotError: Ошибка запроса последней категории
```

### `CategoryManager.get_lot_category_last_lot`

```
Находит самый дешевый лот в категории по каждому из фильтров.  

Args:
    lot_category_id (int | str): ID категории лота      

Returns:
    List[CategoryLastLot]: Объект, содержащий в себе:     
        - category_id (str): ID категории       
        - filtration (str): Название фильтра    
        - price (float): Цена лота      
        - offer_id (str): ID лота       
        - owner_username (str): Юзернейм владельца лота       
Raises:
    FpxGetLastCategoryLotError: Ошибка запроса последней категории
```

### `ChatManager.get_chat_data`

```
Получает данные чата.

Args:
    chat_id (int | str): Айди чата

Returns:
    ChatData: Объект с тех. данными чата:   
        - node_name (str): Полный ID переписки, нужный для отправки сообщения (users-8778502-19903068)  
        - csrf_token (str): Нужен для post запросов, сохраняется в кеш self.account._csrf_token  
        - user_id (str): твой ID     
        - Message: Объект, содержащий последнее сообщение в чате:           
            - chat_id (str): ID чата       
            - is_system (bool): Системное ли сообщение            
            - sender (str): Отправитель сообщения   
            - text (str): Текст сообщения       
Raises:
    FpxGetChatDataError: Ошибка запроса данных чата
```

### `ChatManager.get_chats`

```
Собирает все чаты на аккаунте.

Returns:
    list[Chat]: Список объектов чатов. Каждый содержит:   
        - id (str): ID чата (node_id).  
        - username (str): Имя клиента.  
        - last_msg (str): Последнее сообщение в чате.   
        - date (str): Дата последнего сообщения.    
        - link (str): Полная ссылка на чат. 
        - is_unread (bool): Прочитано или нет (True, если не прочитано).    

Raises:
    FpxGetChatsError: Ошибка получения чатов FunPay
```

### `ChatManager.send_message`

```
Отправляет сообщение.  

Args:
    chat_id (str): ID чата  
    text (str): Текст сообщения 

Returns:
    bool: True, если сообщение отправлено   

Raises:
    FpxMessageNotDelivered: Если не удалось отправить сообщение.
```

### `ChatManager.ban_chat`

```
Блокирует чат (кнопка «Заблокировать» в шапке чата FunPay).
FunPay выполняет блокировку через POST /chat/mute с mute=1.

Args:
    chat_id (int | str): ID чата (node / data-id). Если передан
        системный users-..., числовой data-id берётся со страницы чата.

Returns:
    bool: True если чат заблокирован.

Raises:
    FpxBanChatError: Не удалось заблокировать чат.
```

### `FpxAccountError`

```
Ошибки, связанные с действиями аккаунта (запросы, лоты, заказы).
```

### `FpxGetLotEditorInfoError`

```
Ошибка запроса данных редактора лота
```

### `FunPayEditor.change_lot_price`

```
Изменяет цену лота.

Args:
    lot_id (str | int): Айди лота
    new_price (str): Новая цена лота
Returns:
    bool: True - цена изменилась.
Raises:
    FpxLotEditingError: Цена не изменилась 
    FpxRequestError: Плохое соединение с интернетом/сервер не ответил
```

### `FunPayEditor.toggle_off_lot`

```
Выключает лот.

Args:
    lot_id (str | int): Айди лота
Returns:
    bool: True - лот выключен
Raises:
    FpxRequestError: Сервер не ответил
```

### `FunPayEditor.toggle_on_lot`

```
Включает лот.

Args:
    lot_id (str | int): Айди лота
Returns:
    bool: True - лот включен
Raises:
    FpxRequestError: Сервер не ответил
```

### `LotManager._get_lot_editor_details`

```
Не для обычного использования! (функция для изменения лота)
Получает данные для изменения лота с https://funpay.com/lots/offerEdit?offer={lot_id}.

Args:
    lot_id (str | int): Айди лота
Returns:
    LotEditor: Возвращает объект с:
        - csrf_token (str): нужен для любого post запроса.  
        - form_created_at (str): время создания формы изменения лота.  
        - offer_id (str): Айди оффера(лота).  
        - node_id (str): Айди нода.  
        - location (str): Обычно пустой.  
        - deleted (str): Обычно пустой.  
        - fields (dict): Словарь с филдами, нет фиксированного кол-ва филдов, просто отправляйте все.  
Raises:
    FpxGetLotEditorInfoError: ошибка поулучения данных редактора
```

### `LotManager.get_lot_info`

```
Собирает данные лота.

Args:
    lot_id (str | int): ID лота.
Returns:
    CurrentLotInfo: Объект с этими данными:  
        - short_desc (str): Краткое описание.   
        - description (str): Полное описание.  
        - price (float): Цена лота.  
Raises:
    FpxGetLotInfoError: Ошибка запроса данных лота
```

### `LotManager.raise_lots`

```
Поднимает все лоты.

Returns:
    list: Ответы от сервера. 
Raises:
    FpxRaisingLotError: Лот не поднят.
```

### `OrderManager.get_order_details`

```
Функция запрашивает детали заказа из /orders/{order_id}/.

Args:
    order_id (str | int): ID заказа
Returns:
    Order: Объект с данными:  
        - order_id (str): ID заказа
        - status (str): Статус заказа.  
        - review (dict): Словарь с данными отзыва, который оставили к заказу.   
        - description (str): Строка с подробным описанием заказа    
        - chat_id (str): ID чата    
Raises:
    FpxGetOrderInfoError: Ошибка запроса данных заказа
```

### `OrderManager.find_orders_by_buyer_name`

```
Ищет все заказы по имени покупателя или названию заказа,
    или по названию заказа и имени покупателя.

Args:
    buyer_name (str | None): Имя покупателя.
    order_name (str | None): Название заказа.
    search_mode (str, optional): Режим поиска для order_name:
        - 'exact': точное совпадение названия;  
        - 'partial': поиск по части строки (подстроке);     
        - 'keywords': поиск по ключевым словам (все слова должны присутствовать).       
        По умолчанию 'partial'.
    full_info (bool): Спрашивает показывать ли полную информацию
        по каждому заказу (требует дополнительный запрос).
        True по дефолту
    Returns:
        list[Order]: Список объектов Order, которые содержат:
            - order_id (str): ID заказа
            - order_time (str): Время заказа
            - client_name (str): Имя покупателя
            - price (float): Сумма заказа
            - status (str): Статус заказа
            - name (str): Название купленного лота
            - category (str): Категория заказа
            - amount (int): Кол-во штук заказа
            - topup_data (str): Данные пополнения (ссылка, ник, тп)
            - review (dict): Словарь с данными отзыва, который оставили к заказу.
            - description (str): Строка с подробным описанием заказа
            - chat_id (str): ID чата
    Raises:
        FpxGetOrderInfoError: Ошибка запроса данных заказа
```

### `OrderManager.refund_order`

```
Делает возврат заказа.

Args:
    order_id (str | int): Айди заказа
Returns:
    bool: True если возврат прошёл успешно. 
Raises:
    FpxRefundError: Не удалось сделать возврат.
```

### `ProfileManager.check_banned`

```
Проверяет, заблокирован ли текущий аккаунт.

GET /account/blocked: 200 — бан, 404 — бана нет.

Returns:
    bool: True если аккаунт заблокирован.
Raises:
    FpxAuthError: Неверные куки
    FpxGetProfileError: Ошибка проверки бана
    
```

### `ProfileManager.get_2fa_status`

```
Проверяет, включена ли двухфакторная аутентификация на аккаунте.

Returns:
    bool: True если 2FA включена, False если выключена.
Raises:
    FpxGetProfileError: Ошибка запроса статуса 2FA
```

### `ProfileManager.get_telegram_connect_url`

```
Возвращает ссылку привязки Telegram уведомлений (@funpaysmartbot).

GET /account/linkTelegram - редирект на t.me.

Returns:
    str: URL привязки Telegram.
Raises:
    FpxAuthError: Неверные куки
    FpxGetProfileError: Ошибка запроса ссылки привязки
```

### `ProfileManager.get_balance`

```
Собирает баланс аккаунта.

Returns:
    Balance: Объект с валютами:    
        - rub (float): Баланс в рублях  
        - usd (float): Баланс в долларах  
        - eur (float): Баланс в евро    
Raises:
    FpxGetProfileError: Ошибка сбора баланса
```

### `ProfileManager.get_my_sells`

```
Запрашивает страницу продаж юзера.

Args:
    limit (int): Лимит заказов, которые нужно вернуть(если 0, то вернёт все заказы).
Returns:
    list: Список объектов, каждый содержит в себе:      
        - order_id (str): ID заказа.        
        - order_time (str): Время создания заказа.      
        - client_name (str): Имя клиента.       
        - price (float): Сумма заказа.      
        - amount (int): Кол-во штук заказа (1 по дефолту).      
        - topup_nickname (str): Данные, на которые отправлять пополнение. (ник, ссылка игрока и тд.)    
        - status (str): Статус заказа.  
        - name (str): Название заказа.  
        - category (str): Категория заказа.   
Raises:
    FpxGetUserSellsError: Ошибка запроса продаж
```

### `ProfileManager.get_user_data`

```
Запрашивает данные юзера, сохраняет их в кеш.

Returns:
    UserData: Объект с данными юзера:   
        - user_id (str): ID юзера.  
        - csrf_token (str): Нужен для любого post запроса на funpay.  
Raises:
    FpxGetUserDataError: ошибка запроса данных юзера
```

### `ProfileManager.profile`

```
Запрашивает профиль юзера.
Args:
    user_id (str | int): Можно не передавать, если None, сама узнает айди владельца сессии и запросит данные о нём. Айди юзера.
Returns:
    Profile: Объект, с данными:  
        - category_ids (list): ID категорий, в которых у юзера выставлены лоты.   
        - lots (list): Список словарей с лотами юзера юзера {lot['name']: lot['id']}.   
        - reviews (list): Список объектов отзыва CurReview с данными:  
            - text (str): Текст отзыва. 
            - stars (int): Кол-во звёзд в отзыве (1-5). 
            - author (str): Автор отзыва.   
            - item_name (str): Название заказа, под которым оставлен отзыв.     
Raises:
    FpxGetProfileError: Ошибка запроса профиля
```

### `ReviewManager.get_review`

```
Забирает отзыв от заказа.

Args:
    order_id (str | int): Айди заказа.
Returns:
    Review: Объект с данными отзыва:  
        - text (str): Текст отзыва. 
        - stars (int): Количество звёзд в отзыве.   
        - answer (str): Ваш ответ на отзыв, может быть пустой строкой.
```

### `ReviewManager.review_answer`

```
Отвечает на отзыв, оставленный покупателем.

Args:
    order_id (str | int): ID заказа, на отзыв которого хотите ответить,  
    text (str): Текст, которым вы хотите ответить на отзыв.  
Returns:
    bool: True при успехе
Raises:
    FpxAnswerReviewError: При ошибке (ответ не совпадает заданному/сервер не вернул ничего).
```

### `ReviewManager.delete_review`

```
Удаляет отзыв или ответ на отзыв.

Args:
    order_id (str | int): ID заказа, отзыв (или ответ на отзыв) которого хотите удалить.
Returns:
    bool: True при успехе
Raises:
    FpxDeleteReviewError: При ошибке (сервер не вернул виджет отзыва / сервер не вернул ничего).
```

## Модели данных

### `Chat`

```
id: Chat id (node)
username: Client nickname
last_msg: Last message in chat
date: last message date
link: full chat link (https://funpay.com/chat/?node=id)
is_unread: Readed or not
```

### `CurReview.answer`

```
Ответить на отзыв
```

### `CurReview.message_author`

```
Ответить на отзыв в чате
```

### `CurReview.delete`

```
Удалить отзыв или ответ на отзыв
```

### `Message.answer`

```
Ответить в этот же чат
```

### `Order.answer`

```
Ответить в этот же чат
```

## Парсеры

### `BaseParser._safe_parse_links`

```
Fallback метод
```

### `BaseParser.clean_text`

```
Безопасный сбор текста, если элемент не найден, вернет пустую строку
```

### `ChatParser.parse_chat`

```
Парсит страницу https://funpay.com/chat/?node=...
```

### `ChatParser.parse_chats_list`

```
Парсит страницу https://funpay.com/chat/
```

### `FpxParser`

```
Главный парсер fpx
Собирает внутри себя методы из отдельных модулей.
```

### `LotParser.parse_current_lot_menu`

```
https://funpay.com/lots/offer?id=...
```

### `LotParser.parse_edit_lot_page`

```
https://funpay.com/lots/offerEdit?node=...&offer=...
```

### `LotParser.parse_lot_menu`

```
Парсит страницу pay.com/lots/.../trade
```

### `OrderParser.parse_category_page`

```
Парсит https://funpay.com/lots/.../
```

### `OrderParser.parse_order_page`

```
Парсит https://funpay.com/orders/.../
```

### `ProfileParser.parse_2fa_status`

```
Парсит https://funpay.com/security/twoFactorSetting
```

### `ProfileParser.parse_finanses`

```
Парсит https://funpay.com/account/balance
```

### `ProfileParser.parse_main_menu`

```
Парсит funpay.com
```

### `ProfileParser.parse_my_sells`

```
Парсит https://funpay.com/orders/trade
```

### `ProfileParser.parse_profile`

```
Парсит https://funpay.com/users/.../
```

## FSM (Finite State Machine)

### `BaseStorage.clear_state`

```
Очищает состояние
```

### `BaseStorage.get_data`

```
Забирает данные состояния
```

### `BaseStorage.get_state`

```
Находит состояние
```

### `BaseStorage.set_state`

```
Задаёт стейт
```

### `BaseStorage.update_data`

```
Обновляет данные состояния
```

## Исключения

### `FpxAnswerReviewError`

```
Ошибка при ответе на отзыв.
```

### `FpxAttributeError`

```
Неправильно переданы аттрибуты.
```

### `FpxBanChatError`

```
Ошибка при блокировке чата.
```

### `FpxClientNotAttachedError`

```
Объект контекста не привязан к главному клиенту fpx.
```

### `FpxCommandArgsError`

```
Вызывается, когда функция команды ожидает аргументы, но в сообщении их передали меньше, чем нужно.
```

### `FpxDeleteReviewError`

```
Ошибка при удалении отзыва или ответа на отзыв.
```

### `FpxError`

```
Базовое исключение для всего фреймворка.
```

### `FpxGetChatDataError`

```
Ошибка запроса данных чата
```

### `FpxGetChatsError`

```
Не удалось запросить чаты.
```

### `FpxGetGameIDError`

```
Ошибка запроса айди игры
```

### `FpxGetLastCategoryLotError`

```
Ошибка запроса последнего лота в категории
```

### `FpxGetLotInfoError`

```
Ошибка запроса данных лота
```

### `FpxGetOrderInfoError`

```
Ошибка запроса данных заказа
```

### `FpxGetProfileError`

```
Ошибка запроса данных юзера
```

### `FpxGetUserDataError`

```
Ошибка запроса данных юзера
```

### `FpxGetUserSellsError`

```
Ошибка запроса данных юзера
```

### `FpxHandlerError`

```
Ошибки хендлера.
```

### `FpxLotEditingError`

```
Ошибка при редактировании лота.
```

### `FpxMessageDeliverError`

```
Сообщение не было доставлено.
```

### `FpxNullDataError`

```
Парсер ожидал данные, но пришёл пустой тег или скелет страницы.
```

### `FpxParseError`

```
Ошибки парсинга HTML/JSON от фп.
```

### `FpxRaisingLotError`

```
Ошибка при поднятии лотов.
```

### `FpxRefundError`

```
Ошибка при возврате денег за заказ.
```

### `FpxRequestError`

```
Превышено количество попыток запроса или сервер упал.
```
