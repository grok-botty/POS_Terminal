CashMachine
===========

**CashMachine** — POS-терминал для кофейни МФТИ «6ка». Проект написан на
Django, работает поверх SQLite и упаковывается в единый исполняемый файл для
Windows через PyInstaller.

Документация ниже покрывает архитектуру системы, установку и запуск,
модель данных, API/URL-контракты, сборку под Windows и правила
контрибьюции.

.. toctree::
   :maxdepth: 2
   :caption: Содержание

   overview
   architecture
   install
   data_model
   api
   windows
   contribution
   reference/index

Быстрый старт
-------------

.. code-block:: bash

   python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements-dev.txt
   python manage.py bootstrap        # миграции + пользователи + меню
   python manage.py runserver 0.0.0.0:8000

Откройте http://127.0.0.1:8000/ и войдите как ``admin/admin`` (менеджер) или
``cashier/cashier`` (кассир).

Индексы
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
