Модель данных
=============

Диаграмма
---------

::

   ┌───────────┐        ┌────────────────┐        ┌────────────┐
   │ Category  │───┬───►│    Product     │◄──┬───►│ ModifierGr │
   └───────────┘   │    └────────┬───────┘   │    └────┬───────┘
                   │             │           │         │
                   │             ▼           │         ▼
                   │       ┌───────────┐     │    ┌──────────┐
                   │       │ OrderLine │◄────┘    │ Modifier │
                   │       └──┬────────┘          └────┬─────┘
                   │          │                        │
                   │          ▼                        │
                   │  ┌───────────────────┐            │
                   │  │ OrderLineModifier │◄───────────┘
                   │  └───────────────────┘
                   │
                   ▼
              ┌─────────┐        ┌──────────────┐
              │  Order  │───────►│ DailySummary │
              └────┬────┘        └──────────────┘
                   │
                   ▼
                ┌──────┐
                │ User │
                └──────┘

Каталог
-------

.. autoclass:: apps.catalog.models.Category
   :members:
   :noindex:

.. autoclass:: apps.catalog.models.Product
   :members:
   :noindex:

.. autoclass:: apps.catalog.models.ModifierGroup
   :members:
   :noindex:

.. autoclass:: apps.catalog.models.Modifier
   :members:
   :noindex:

У :class:`~apps.catalog.models.Modifier` есть флаг ``is_default``: в группе
одного выбора такой вариант уже отмечен, когда кассир открывает шторку.

Заказы
------

.. autoclass:: apps.orders.models.Shift
   :members:
   :noindex:

Бизнес-дату и время начала смены задаёт кассир. ``opened_at`` — ноль
отсчёта на часах сервера, а не время, которое показывается на кассе.
Время оплаты и выдачи заказа выводится как начало смены плюс
прошедшее с этого нуля. Закрытие не проставляет ``closed_at``
и не меняет статус заказов «не готово»: они остаются привязанными
к этой смене. Статистика группирует заказы по смене, а не по
``created_at``.

.. autoclass:: apps.orders.models.Order
   :members:
   :noindex:

Поле ``fulfilment`` — это «здесь» или «на вынос» (по умолчанию «здесь»).

У позиции есть флаг ``handed_out`` («отдали»). Когда он стоит на всех
строках оплаченного заказа в статусе «не готово», ``auto_ready_at``
запоминает этот момент: через 5 секунд заказ становится «Готово»,
и ``ready_at`` — это время выдачи. Снятие галочки или оплаты очищает
``auto_ready_at``. Поле ``main_queue_until`` держит оплаченное «Готово»
и любое «Отменено» в основной очереди ещё 13 секунд.

.. autoclass:: apps.orders.models.OrderLine
   :members:
   :noindex:

.. autoclass:: apps.orders.models.OrderLineModifier
   :members:
   :noindex:

Аналитика
---------

.. autoclass:: apps.analytics.models.DailySummary
   :members:
   :noindex:

Учётные записи
--------------

.. autoclass:: apps.accounts.models.User
   :members:
   :noindex:
