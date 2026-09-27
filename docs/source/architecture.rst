Архитектура
===========

Общая структура
---------------

::

    cashmachine/
    ├── config/            # Django-проект (settings, urls, wsgi/asgi)
    ├── apps/
    │   ├── accounts/      # Пользователи и роли
    │   ├── catalog/       # Категории, товары, модификаторы
    │   ├── orders/        # Заказы, позиции, лайфцикл
    │   ├── analytics/     # Дневные сводки, дашборд
    │   └── pos/           # Экран кассы (HTMX-UI, склейка catalog+orders)
    ├── templates/         # Общие шаблоны (base.html, topbar)
    ├── static/            # CSS + вендорные htmx.min.js, alpine.min.js
    ├── desktop/           # Лаунчер pywebview и PyInstaller spec
    ├── docs/              # Sphinx
    └── manage.py

Модульность
-----------

Проект намеренно разделён на маленькие приложения — так удобнее объяснять
курс и легче переиспользовать код.

============  ========================================  ============
App           Отвечает за                               Зависит от
============  ========================================  ============
accounts      Пользовательская модель, вход/выход       —
catalog       Меню (Category, Product, Modifier)        —
orders        Заказы (Order, OrderLine, ...Modifier)    catalog, accounts
analytics     DailySummary, витрина аналитики           orders, accounts
pos           HTMX-кассовый UI и первичный bootstrap    catalog, orders
============  ========================================  ============

Слои внутри app
---------------

Каждое приложение придерживается одной и той же трёхслойной раскладки:

* ``models.py`` — только данные и простые методы над одной строкой.
* ``services.py`` — бизнес-логика: транзакционные операции над несколькими
  моделями (:mod:`apps.orders.services`, :mod:`apps.analytics.services`,
  :mod:`apps.catalog.services`).
* ``views.py`` — тонкая обвязка HTTP: вызвать сервис, вернуть шаблон.

Такая раскладка позволяет из shell (``python manage.py shell``) закрывать
смену или менять статус заказа без обхода через HTTP-слой, и делает бизнес
логику легко тестируемой.

Диаграмма потока «оформить и выдать»
------------------------------------

::

    ┌────────┐   click product   ┌────────────────┐   POST /pos/pay
    │ Кассир │ ────────────────► │  apps.pos.views │ ────────────────┐
    └────────┘                    └────────────────┘                  │
                                        │                              ▼
                                        │  services.add_line     ┌────────────┐
                                        └──────────────────────► │ apps.orders│
                                                                 │ .services  │
                                                                 └────┬───────┘
                                                                      │ pay_order
                                                                      ▼
                                                     status: NEW ──► IN_PROGRESS
                                                                      │
                              ┌────────────┐  HTMX polling             ▼
                              │  Бариста   │ ◄──────────── /orders/fragment/
                              └────────────┘   (updated queue)
                                    │
                                    │ POST /orders/<id>/ready/  status: READY
                                    ▼
                              ┌────────────┐
                              │  Кассир    │ POST /orders/<id>/handoff/ → HANDED_OFF
                              └────────────┘

Хранилище
---------

Используется SQLite, файл хранится под пользовательской папкой:

* Linux — ``~/.local/share/cashmachine/cashmachine.sqlite3``.
* macOS — ``~/Library/Application Support/CashMachine/cashmachine.sqlite3``.
* Windows — ``%LOCALAPPDATA%\CashMachine\cashmachine.sqlite3``.

Путь можно переопределить переменной ``CASHMACHINE_DB_PATH`` (это же
используется в тестах и Sphinx-сборке).

HTMX как middle-ground
----------------------

Мы сознательно не используем SPA. HTMX закрывает 95 % интерактива
(добавление позиций, обновление панели заказа, авто-обновление очереди
выдачи) на одном обработчике сервера — Django-view возвращает готовый
HTML-фрагмент. Это делает проект «понятно Django-приложением»:
рендер, роутинг и бизнес-логика живут в Python, а не в отдельном
JS-приложении.

Alpine.js добавлен только там, где нужно чистое клиентское состояние
(подсветка выбранной строки в панели заказа, закрытие модалки-пикера) —
он весит 18 KiB и не требует сборки.
