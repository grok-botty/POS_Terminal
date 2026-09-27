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

Заказы
------

.. autoclass:: apps.orders.models.Order
   :members:
   :noindex:

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
