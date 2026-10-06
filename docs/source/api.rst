HTTP-контракт и URL-карта
=========================

Приложение отдаёт HTML-фрагменты через HTMX. Это не REST API, но URL-схема
чёткая и стабильная — ниже описаны все маршруты.

Учётные записи
--------------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - URL
     - Метод
     - Назначение
   * - ``/accounts/login/``
     - GET / POST
     - Форма входа. POST принимает ``username``, ``password``.
   * - ``/accounts/logout/``
     - POST
     - Выход, редирект на страницу входа.

Касса (POS)
-----------

.. list-table::
   :header-rows: 1
   :widths: 40 12 48

   * - URL
     - Метод
     - Действие
   * - ``/pos/``
     - GET
     - Полный экран кассы: очередь, меню, текущий заказ.
   * - ``/pos/shift/``
     - GET
     - Заглушка вкладки «Смена» (открытие с ручной датой — следующий проход).
   * - ``/pos/panel/``
     - GET
     - HTMX-фрагмент правой панели заказа.
   * - ``/pos/queue/``
     - GET
     - HTMX-фрагмент очереди баристы.
   * - ``/pos/queue/<id>/cycle/``
     - POST
     - Цикл статуса: не готово → готово → отменено. Ответ — фрагмент очереди.
   * - ``/pos/products/?category=<id>``
     - GET
     - HTMX-фрагмент меню. Без ``category`` — вкладка «Все».
   * - ``/pos/products/<pid>/pick/``
     - GET
     - Шторка допов. Если групп нет — сразу добавляет товар в заказ.
   * - ``/pos/products/<pid>/add/``
     - POST
     - Добавить товар. Радиогруппы приходят как ``group_<id>``,
       мультивыбор — как ``modifiers``. Необязательное поле ``line_note``.
   * - ``/pos/lines/<lid>/edit/``
     - GET / POST
     - Открыть шторку существующей строки или сохранить допы и заметку.
   * - ``/pos/lines/<lid>/inc/``
     - POST
     - +1 к количеству позиции.
   * - ``/pos/lines/<lid>/dec/``
     - POST
     - -1 (0 удаляет позицию).
   * - ``/pos/lines/<lid>/remove/``
     - POST
     - Убрать позицию.
   * - ``/pos/meta/``
     - POST
     - Обновить ``guest_name``, ``comment`` и «С собой» (``to_go``).
       Ответ ``204``, панель не перерисовывается.
   * - ``/pos/pay/``
     - POST
     - Оплатить и отправить в очередь. ``204`` + ``HX-Redirect``.
   * - ``/pos/enqueue/``
     - POST
     - Поставить в очередь без оплаты.
   * - ``/pos/discard/``
     - POST
     - Удалить текущий черновик заказа.

Очередь выдачи (Orders)
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 40 12 48

   * - URL
     - Метод
     - Действие
   * - ``/orders/``
     - GET
     - Полный экран выдачи.
   * - ``/orders/fragment/``
     - GET
     - HTMX-таргет для polling каждые 5 секунд.
   * - ``/orders/<id>/ready/``
     - POST
     - Пометить заказ готовым.
   * - ``/orders/<id>/handoff/``
     - POST
     - Пометить заказ выданным.
   * - ``/orders/<id>/cancel/``
     - POST
     - Отменить заказ.
   * - ``/orders/all-ready/``
     - POST
     - Массовая операция: все ``IN_PROGRESS`` → ``READY``.

Меню (Catalog, менеджерская зона)
---------------------------------

* ``/catalog/`` — обзор.
* ``/catalog/categories/new/``, ``/catalog/categories/<id>/`` — CRUD категорий.
* ``/catalog/products/new/``, ``/catalog/products/<id>/`` — CRUD товаров.
* ``/catalog/modifier-groups/…`` — CRUD групп модификаторов.
* ``/catalog/modifiers/…`` — CRUD опций.

Аналитика
---------

* ``/analytics/?days=<N>`` — дашборд.
* ``/analytics/close-day/`` — закрытие смены (POST).

Django-админка
--------------

``/admin/`` — стандартная админка Django с зарегистрированными моделями
(:mod:`apps.accounts.admin`, :mod:`apps.catalog.admin`,
:mod:`apps.orders.admin`, :mod:`apps.analytics.admin`).

Программный доступ
------------------

Все действия из URL-таблиц выше доступны напрямую из shell:

.. code-block:: python

   from apps.orders import services
   from apps.orders.models import Order
   from apps.catalog.models import Product

   order = services.create_order()
   services.add_line(order, Product.objects.get(name="Латте"), quantity=2)
   services.pay_order(order)
   services.mark_ready(order)
   services.hand_off(order)

Список сервисных функций
------------------------

.. automodule:: apps.orders.services
   :members:
   :noindex:

.. automodule:: apps.analytics.services
   :members:
   :noindex:

.. automodule:: apps.catalog.services
   :members:
   :noindex:
