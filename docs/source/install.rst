Установка и запуск
==================

Требования
----------

* Python 3.10+.
* pip и (желательно) ``python -m venv``.
* Для сборки под Windows дополнительно: ``pywebview`` и ``pyinstaller``.

Клонирование и подготовка
-------------------------

.. code-block:: bash

   git clone https://github.com/grok-botty/POS_Terminal cashmachine
   cd cashmachine
   python -m venv .venv
   source .venv/bin/activate            # Windows: .venv\Scripts\activate
   pip install -r requirements-dev.txt   # dev: включает Sphinx и pytest

Инициализация базы данных
-------------------------

Одна команда применяет миграции, создаёт пользователей ``admin/admin`` и
``cashier/cashier`` и заполняет меню демо-данными:

.. code-block:: bash

   python manage.py bootstrap

Команда идемпотентна: если БД уже инициализирована, шаги пропускаются.

Запуск в режиме разработки
--------------------------

.. code-block:: bash

   python manage.py runserver 0.0.0.0:8000

Откройте http://127.0.0.1:8000/ — кассовый экран, http://127.0.0.1:8000/admin/
— админка Django.

Переменные окружения
--------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Переменная
     - Назначение
   * - ``CASHMACHINE_SECRET_KEY``
     - Секретный ключ Django. По умолчанию — insecure-заглушка, обязательно
       переопределяется для продакшена.
   * - ``CASHMACHINE_DEBUG``
     - ``0`` отключает ``DEBUG`` (например в PyInstaller-бандле).
   * - ``CASHMACHINE_DB_PATH``
     - Явный путь к файлу SQLite. Полезен для тестов и Sphinx-сборки.
   * - ``CASHMACHINE_ALLOWED_HOSTS``
     - Список разрешённых хостов через запятую.
   * - ``CASHMACHINE_TIME_ZONE``
     - Тайм-зона (по умолчанию ``Europe/Moscow``).

Проверка установки
------------------

.. code-block:: bash

   python manage.py check
   python manage.py test    # опционально: интеграционные тесты

Запуск как настольного приложения
---------------------------------

.. code-block:: bash

   pip install -r requirements-desktop.txt
   python desktop/launcher.py

Скрипт поднимает Django на свободном порту 127.0.0.1 и открывает
приложение в окне pywebview (или в системном браузере, если pywebview не
установлен).

Инструкции по сборке ``.exe`` см. в разделе :doc:`windows`.
