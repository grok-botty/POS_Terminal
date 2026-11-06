Сборка под Windows
==================

Цель — получить один самодостаточный ``CashMachine.exe``, который на любом
Windows-компьютере поднимает локальный Django, открывает окно pywebview и
пишет данные в ``%LOCALAPPDATA%\\CashMachine\\cashmachine.sqlite3``.

Скачать готовый exe
-------------------

Каждый push в ``main`` (смерженный pull request приходит именно так) и
ручной запуск workflow ``Windows exe`` на ветке ``main`` собирают
``CashMachine.exe`` на раннере ``windows-latest``. Файл лежит артефактом
``CashMachine-windows`` у этого прогона. После успешной проверки workflow
выпускает следующую версию ``v1.1``, ``v1.2``, ``v1.3``, … (если тегов
``vX.Y`` ещё не было — ``v1.1``): аннотированный тег, релиз с перечнем
изменений и сам exe. Прежние версии не удаляются.

Скользящий тег ``latest`` каждый раз переносится на эту же сборку, поэтому
постоянная ссылка не меняется:

`Скачать CashMachine.exe (latest)
<https://github.com/grok-botty/POS_Terminal/releases/download/latest/CashMachine.exe>`_

Все версии и их описания — на странице `Releases
<https://github.com/grok-botty/POS_Terminal/releases>`_.

Push уже существующего тега ``vX.Y`` (два числа, без patch) пересобирает
exe и обновляет релиз этого тега. Следующая версия при этом не заводится.

Как запустить скачанный файл:

1. Нужен `Microsoft Edge WebView2 Runtime
   <https://developer.microsoft.com/en-us/microsoft-edge/webview2/>`_
   (на Windows 11 он обычно уже есть).
2. Сохраните ``CashMachine.exe`` и откройте его двойным щелчком.
   Файл не подписан — антивирус может спросить подтверждение.
3. Окно кассы откроется само. При первом запуске создаётся
   ``%LOCALAPPDATA%\\CashMachine\\cashmachine.sqlite3``, применяются
   миграции и, если пользователей ещё нет, заводятся ``admin/admin`` и
   ``cashier/cashier``. Касса входит как ``admin``.

Журнал: ``%LOCALAPPDATA%\\CashMachine\\cashmachine.log``.
Пересобрать текущий ``main`` без нового коммита: Actions → ``Windows exe``
→ ``Run workflow``. Такой запуск тоже выпускает следующую версию ``vX.Y``,
даже если код не менялся.

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

      git clone https://github.com/grok-botty/POS_Terminal
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
  * ``%LOCALAPPDATA%\CashMachine\cashmachine.log`` — журнал процесса
    (ротация, около 1 МБ × 3). Успешные опросы ``/pos/queue/`` туда не
    пишутся.
  * ``%LOCALAPPDATA%\CashMachine\cashmachine-boot.log`` — короткая
    строка старта: pid, commit сборки, ``wall=`` (часы ноутбука, им
    нельзя верить) и ``mono=``.
  * ``%LOCALAPPDATA%\CashMachine\cashmachine.instance.lock`` — замок
    одного процесса. Файл не удалять, пока касса запущена.
  * ``%LOCALAPPDATA%\CashMachine\webview\<pid>\`` — профиль окна
    WebView2 этого запуска.

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

Журнал смешивает ``asctime`` (настенные часы ноутбука, на этой кассе они
прыгают) и ``mono=`` — секунды от старта процесса. Порядок событий внутри
одного ``pid`` читается по ``mono``. Commit сборки — поле ``commit=`` в
``event=process_start`` и в boot-журнале. Номер ``v1.x`` присваивается
релизу уже после сборки exe, поэтому в файле его может не быть: сверяйте
commit с коммитом релиза на GitHub.

* ``event=health_ok`` — Django слушает порт. Это не страница смены.
* ``event=health_failed`` — процесс не дождался HTTP 200 от ``/pos/health/``.
  В ``detail`` будет ``server_thread_dead``, ``URLError`` или код ответа.
  Это единственный случай, когда лаунчер пишет, что сервер не поднялся.
* ``event=webview_failed`` — не создался WebView2 (в том числе
  ``E_UNEXPECTED``). Сервер при этом не гасится, касса открывается в
  браузере. ``event=webview_closed reason=user`` — окно закрыл человек.
* ``event=already_running`` и ``event=attach`` — второй двойной щелчок
  подключился к уже живому серверу и не запускал migrate.
* ``event=process_exit`` — процесс завершился. Рядом нет
  ``event=uncaught`` / ``event=server_crash`` — это не падение Python.
* Ошибка «Missing WebView2 runtime»: установите
  `Evergreen Bootstrapper
  <https://developer.microsoft.com/en-us/microsoft-edge/webview2/>`_.
* Логи PyInstaller живут в ``build\pyinstaller_spec\warn-*.txt``.

Проверка обновления, не трогая базу
------------------------------------

Эти шаги выполняются на кассовом ноутбуке. Они не удаляют SQLite и не
вызывают ``migrate`` вручную.

1. Скопируйте ``cashmachine.sqlite3`` рядом (страховка). Рабочий файл
   не переименовывайте и не удаляйте.
2. Закройте уже запущенный CashMachine через крестик или диспетчер задач.
3. Замените exe новым файлом и запустите его один раз.
4. Откройте смену как обычно: дата и время вручную, имя кассира.
   Старые заказы должны остаться на своих местах. Пробейте один
   тестовый заказ.
5. В ``cashmachine-boot.log`` есть ``event=runtime_hook_ok`` с ``pid=``,
   ``commit=`` и ``wall_clock=unreliable``.
6. В ``cashmachine.log`` есть ``event=process_start`` с тем же commit и
   следом ``event=health_ok``. После закрытия окна —
   ``event=webview_closed reason=user``.
7. Не закрывая первую копию, запустите exe ещё раз. Второй процесс пишет
   ``event=already_running`` и ``event=attach`` и не создаёт вторую базу.
8. Если окно пустое, а в журнале ``event=webview_failed``, касса должна
   открыться в браузере. Это сбой WebView2, не «Django не поднялся».

Обновление
----------

Один ``.exe`` не имеет автообновления. Обычный способ отдать новую сборку —
скачать ``CashMachine.exe`` из релиза ``latest`` (ссылка выше) и заменить
старый файл. Нужная старая версия остаётся на странице Releases
(``v1.1``, ``v1.2``, …). SQLite в ``%LOCALAPPDATA%\\CashMachine\\`` при
этом переиспользуется как есть. Локальная сборка через ``desktop\\build.bat``
по-прежнему кладёт такой же файл в ``dist\\CashMachine.exe``.
