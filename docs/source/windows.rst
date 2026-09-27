Сборка под Windows
==================

Цель — получить один самодостаточный ``CashMachine.exe``, который на любом
Windows-компьютере поднимает локальный Django, открывает окно pywebview и
пишет данные в ``%LOCALAPPDATA%\\CashMachine\\cashmachine.sqlite3``.

Требования на билд-машине
-------------------------

* Windows 10/11.
* Python 3.11 x64 (`python.org <https://www.python.org/downloads/windows/>`_).
* Установленный ``Microsoft Edge WebView2 Runtime`` (для окна pywebview).
* Свежий ``git``.

Пошагово
--------

1. Клонировать репозиторий и создать venv:

   .. code-block:: bat

      git clone https://github.com/LotFullKa/POS_Terminal
      cd POS_Terminal
      python -m venv .venv
      .venv\Scripts\activate

2. Установить зависимости (runtime + desktop):

   .. code-block:: bat

      pip install --upgrade pip
      pip install -r requirements.txt
      pip install -r requirements-desktop.txt

3. Собрать бандл:

   .. code-block:: bat

      desktop\build.bat

   Скрипт вызывает ``manage.py collectstatic``, чтобы WhiteNoise отдал CSS/JS
   из бандла, а затем — ``pyinstaller`` с ``desktop\pyinstaller_spec.spec``.

4. Готовый файл появится в ``dist\CashMachine.exe``.

Проверка перед выкладкой
------------------------

* Убедитесь, что база данных создаётся заново под свежим Windows-профилем:

  .. code-block:: bat

     rd /s /q "%LOCALAPPDATA%\CashMachine"
     dist\CashMachine.exe

  При первом запуске должно быть создано два пользователя — ``admin/admin``
  и ``cashier/cashier``, — а меню заполнено демо-товарами.

* Файлы, которые CashMachine создаёт в системе пользователя:

  * ``%LOCALAPPDATA%\CashMachine\cashmachine.sqlite3`` — SQLite-БД.
  * ``%LOCALAPPDATA%\CashMachine\cashmachine.log`` — журнал.

Настройки для продакшена
------------------------

Перед раздачей бинарника рекомендуется:

* Установить ``CASHMACHINE_SECRET_KEY`` в переменных окружения службы
  Windows (или в файле ``desktop\launcher.bat``).
* Отключить создание дефолтных ``admin/admin`` — заменить их своими через
  админку. Дефолты создаются только когда таблица пользователей пуста, так
  что после первого запуска и удаления «болванок» они больше не появятся.
* Настроить регулярное копирование ``cashmachine.sqlite3`` на сетевой диск
  или в облако — это единственный источник данных.

Диагностика
-----------

* ``dist\CashMachine.exe`` не открывает окно, но в трее видно процесс:
  проверьте ``cashmachine.log``, часто это конфликт с уже занятым портом
  8765/8766/8767 — лаунчер выбирает следующий свободный автоматически.
* Ошибка «Missing WebView2 runtime»: установите
  `Evergreen Bootstrapper
  <https://developer.microsoft.com/en-us/microsoft-edge/webview2/>`_.
* Логи PyInstaller живут в ``build\pyinstaller_spec\warn-*.txt``.

Обновление
----------

Один ``.exe`` не имеет автообновления. Обычный workflow — собрать новую
версию, положить рядом с БД (или в отдельную папку) и подсказать бариста
запустить новый бинарник; SQLite-файл при этом переиспользуется как есть.
