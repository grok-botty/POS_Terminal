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
     - GET / POST
     - Открытие смены (``action=open``, ``business_date=YYYY-MM-DD``)
       или закрытие. Первый шаг — сводка, второй (``?step=confirm``)
       требует POST ``action=close`` и ``confirmation=ЗАКРЫТЬ``.
       Незавершённые заказы не отменяются.
   * - ``/pos/stats/``
     - GET
     - Статистика по сменам. ``period=this|7|30|all`` либо
       ``from`` / ``to`` по бизнес-дате. График — выручка по дате смены
       той же выборки. Нужна открытая смена.
   * - ``/pos/stats/export/``
     - GET
     - CSV той же выборки, UTF-8 с BOM.
   * - ``/pos/panel/``
     - GET
     - HTMX-фрагмент правой панели заказа.
   * - ``/pos/queue/``
     - GET
     - HTMX-фрагмент очереди баристы.
   * - ``/pos/queue/<id>/``
     - GET
     - Открыть заказ очереди в правой колонке. Черновик с позициями
       перед этим сам ставится в очередь без оплаты.
   * - ``/pos/queue/<id>/cycle/``
     - POST
     - Цикл готовности: не готово → готово → отменено. Оплату не меняет.
       Ответ — фрагмент очереди.
   * - ``/pos/queue/<id>/status/``
     - POST
     - Поставить готовность сразу (``status=in_progress|ready|cancelled``).
       Оплату не меняет. Ответ — фрагмент очереди. Правый клик по карточке.
   * - ``/pos/products/?category=<id>&q=``
     - GET
     - HTMX-фрагмент меню. Без ``category`` — вкладка «Все».
       ``q`` оставляет плитки, в названии которых есть эта подстрока
       без учёта регистра. Пустой ``q`` возвращает список вкладки.
       Запрос с ``HX-Target: menu-body`` отдаёт только сетку.
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
     - Отметить оплату. Черновик уходит в очередь; у заказа из очереди
       готовность сохраняется. ``204`` + ``HX-Redirect``.
   * - ``/pos/enqueue/``
     - POST
     - Поставить черновик в очередь без оплаты (плашка «не оплачено»).
   * - ``/pos/discard/``
     - POST
     - Удалить черновик. Для заказа из очереди кнопка «Новый чек»
       только закрывает правую колонку, карточку не удаляет.

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

* ``/catalog/`` — редактор позиций (``?product=``, ``?tag=``, ``?q=``, ``?new=1``).
* ``/catalog/groups/`` — справочник групп допов. POST ``/catalog/groups/save/``
  и ``/catalog/groups/<id>/save/`` сохраняют группу и опции (цена, дефолт).
* ``/catalog/tags/`` — справочник тегов (категорий).
* ``/catalog/categories/…``, ``/catalog/products/…``,
  ``/catalog/modifier-groups/…``, ``/catalog/modifiers/…`` — те же операции
  отдельными формами. POST товара с ``stay=1`` возвращает в редактор.

Аналитика
---------

* ``/analytics/?days=<N>`` — старый дашборд менеджера (календарные дни).
* ``/analytics/close-day/`` — снимок дня в ``DailySummary`` (POST). Это не
  экран закрытия смены: смена закрывается на ``/pos/shift/``.

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
