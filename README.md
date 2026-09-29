# CashMachine — касса кофейни «6ка»

POS-терминал МФТИ-кофейни «6ка». Полностью на Django, работает поверх
SQLite, упаковывается в один `.exe` для Windows. UI — Django-шаблоны +
HTMX (никакой SPA).

## Быстрый старт (dev)

```bash
git clone https://github.com/grok-botty/POS_Terminal cashmachine
cd cashmachine
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python manage.py bootstrap          # migrate + demo меню + admin/admin
python manage.py runserver 0.0.0.0:8000
```

Открыть <http://127.0.0.1:8000/>. Логины по умолчанию:

| Логин   | Пароль  | Роль            |
|---------|---------|-----------------|
| admin   | admin   | Администратор   |
| cashier | cashier | Кассир          |

Смените их перед выкладкой в реальную кассу (пользователи и пароли —
`/admin/auth/user/` для суперпользователя; меню — `/catalog/`).

## Быстрый старт (Windows desktop)

```bat
git clone https://github.com/grok-botty/POS_Terminal
cd POS_Terminal
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-desktop.txt
desktop\build.bat
```

Готовый бинарник — `dist\CashMachine.exe`. Он поднимает Django на свободном
loopback-порту и открывает окно pywebview. Данные хранятся в
`%LOCALAPPDATA%\CashMachine\cashmachine.sqlite3`, лог — в
`%LOCALAPPDATA%\CashMachine\cashmachine.log`.

Подробности сборки — в [`docs/source/windows.rst`](docs/source/windows.rst).

## Документация

```bash
cd docs
make html          # macOS/Linux
make.bat html      # Windows
```

Открыть `docs/build/html/index.html`.

Разделы: обзор, архитектура, установка/запуск, модель данных, HTTP-контракт
и URL-карта, Windows-сборка, правила контрибьюции, автосправочник по всем
модулям.

## Что умеет

- Заказы: товары + модификаторы (сироп / молоко), имя гостя, комментарий,
  «В зале / С собой», оплата.
- Экран выдачи: активные и недавние заказы с HTMX-polling, кнопка
  «Все готовы», отдача одним кликом.
- **Меню**: in-app раздел `/catalog/` — CRUD категорий, товаров, групп
  модификаторов и опций в стиле POS (не Django-админка). Быстрое
  скрытие/показ позиций одним кликом через HTMX; форма товара умеет
  привязывать группы модификаторов.
- Аналитика: выручка по дням, топ товаров, загрузка по часам, история
  закрытых смен.
- Закрытие смены: один клик → снапшот в `DailySummary`.
- Django-админка (`/admin/`) остаётся, но ссылка на неё показана только
  суперпользователям — для повседневных операций она не нужна.

## Структура

```
cashmachine/
├── config/                # Django-проект (settings, urls, wsgi/asgi)
├── apps/
│   ├── accounts/          # Пользователи (кастомная модель + роли)
│   ├── catalog/           # Категории, товары, модификаторы
│   ├── orders/            # Заказы и позиции
│   ├── analytics/         # Дневные сводки + дашборд
│   └── pos/               # HTMX-экран кассы + первичный bootstrap
├── templates/             # base.html + partials
├── static/                # css + вендорный htmx.min.js, alpine.min.js
├── desktop/               # launcher.py, PyInstaller spec, build.bat / .sh
├── docs/                  # Sphinx (RU) + autodoc
└── manage.py
```

## Стек

- Django 5.x, SQLite, django-htmx, WhiteNoise.
- HTMX 1.9 + Alpine.js 3.14 (оба вендорены, без npm).
- pywebview + PyInstaller для настольной сборки.
- Sphinx + Furo для документации.

## Лицензия

MIT — см. `LICENSE` (если добавите).
