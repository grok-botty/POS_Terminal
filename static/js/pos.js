/* HTMX вставляет шторку допов после старта Alpine — инициализируем заново. */
document.addEventListener("htmx:afterSwap", function (evt) {
  if (window.Alpine && evt.target) {
    window.Alpine.initTree(evt.target);
  }
});

/* Правый клик по карточке очереди: сразу выбрать готовность.
   Левый клик по карточке по-прежнему открывает заказ, пилюля статуса
   крутит цикл. Оплату меню не меняет. */
(function () {
  var STATUSES = [
    ["in_progress", "Не готово"],
    ["ready", "Готово"],
    ["cancelled", "Отменено"],
  ];
  var menu = document.createElement("div");
  menu.id = "q-status-menu";
  menu.className = "q-status-menu";
  menu.hidden = true;
  menu.setAttribute("role", "menu");
  STATUSES.forEach(function (pair) {
    var button = document.createElement("button");
    button.type = "button";
    button.dataset.status = pair[0];
    button.textContent = pair[1];
    button.setAttribute("role", "menuitem");
    menu.appendChild(button);
  });
  document.body.appendChild(menu);

  var card = null;

  function closeMenu() {
    menu.hidden = true;
    card = null;
  }

  function openMenu(target, x, y) {
    card = target;
    var current = target.getAttribute("data-status");
    menu.querySelectorAll("button").forEach(function (button) {
      button.classList.toggle("is-current", button.dataset.status === current);
    });
    menu.hidden = false;
    var width = menu.offsetWidth;
    var height = menu.offsetHeight;
    var left = Math.min(x, window.innerWidth - width - 8);
    var top = Math.min(y, window.innerHeight - height - 8);
    menu.style.left = Math.max(8, left) + "px";
    menu.style.top = Math.max(8, top) + "px";
  }

  document.addEventListener("contextmenu", function (event) {
    var target = event.target.closest && event.target.closest(".q-card");
    if (!target) {
      closeMenu();
      return;
    }
    event.preventDefault();
    openMenu(target, event.clientX, event.clientY);
  });

  menu.addEventListener("click", function (event) {
    var button = event.target.closest("button");
    if (!button || !card || !window.htmx) return;
    event.preventDefault();
    event.stopPropagation();
    var source = card;
    var url = source.getAttribute("data-status-url");
    var status = button.dataset.status;
    closeMenu();
    var queue = document.getElementById("barista-queue");
    if (queue) window.htmx.trigger(queue, "htmx:abort");
    window.htmx.ajax("POST", url, {
      source: source,
      target: "#barista-queue",
      swap: "outerHTML",
      values: { status: status },
    });
  });

  document.addEventListener("click", function (event) {
    if (!menu.hidden && !menu.contains(event.target)) closeMenu();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeMenu();
  });
  window.addEventListener("scroll", closeMenu, true);
})();

/* Автоперевод в «Готово» через 5 секунд и уход из основной очереди
   через 13. Моменты приходят с сервера (data-auto-ready-at, data-leave-at),
   поэтому опрос HTMX и перезагрузка не начинают отсчёт заново. */
(function () {
  var AUTO_READY_MS = 5000;
  var autoTimers = Object.create(null);
  var leaveTimers = Object.create(null);
  var leaving = Object.create(null);

  function clearHandle(bucket, id) {
    if (bucket[id]) {
      clearTimeout(bucket[id]);
      delete bucket[id];
    }
  }

  function postStatus(card, status) {
    if (!window.htmx) return;
    var url = card.getAttribute("data-status-url");
    if (!url) return;
    var queue = document.getElementById("barista-queue");
    if (queue) window.htmx.trigger(queue, "htmx:abort");
    window.htmx.ajax("POST", url, {
      source: card,
      target: "#barista-queue",
      swap: "outerHTML",
      values: { status: status },
    });
  }

  function beginLeave(card) {
    var id = card.getAttribute("data-order-id");
    if (!id || leaving[id]) return;
    leaving[id] = true;
    card.classList.add("q-card-leaving");
    card.style.maxHeight = card.scrollHeight + "px";
    window.requestAnimationFrame(function () {
      card.classList.add("q-card-leave-go");
    });
    window.setTimeout(function () {
      if (card.parentNode) card.parentNode.removeChild(card);
    }, 480);
  }

  function armCard(card) {
    var id = card.getAttribute("data-order-id");
    if (!id) return;
    clearHandle(autoTimers, id);
    clearHandle(leaveTimers, id);

    if (!card.getAttribute("data-leave-at")) {
      delete leaving[id];
    } else if (leaving[id]) {
      if (card.parentNode) card.parentNode.removeChild(card);
      return;
    }

    var autoAt = card.getAttribute("data-auto-ready-at");
    if (autoAt && card.getAttribute("data-status") === "in_progress") {
      var due = Date.parse(autoAt) + AUTO_READY_MS;
      var wait = isNaN(due) ? AUTO_READY_MS : due - Date.now();
      autoTimers[id] = window.setTimeout(function () {
        delete autoTimers[id];
        var current = document.querySelector('.q-card[data-order-id="' + id + '"]');
        if (!current || current.getAttribute("data-status") !== "in_progress") return;
        if (!current.getAttribute("data-auto-ready-at")) return;
        postStatus(current, "ready");
      }, Math.max(0, wait));
    }

    var leaveRaw = card.getAttribute("data-leave-at");
    if (leaveRaw) {
      var when = Date.parse(leaveRaw);
      if (!isNaN(when)) {
        var left = when - Date.now();
        if (left <= 0) {
          beginLeave(card);
        } else {
          leaveTimers[id] = window.setTimeout(function () {
            delete leaveTimers[id];
            var current = document.querySelector('.q-card[data-order-id="' + id + '"]');
            if (current && current.getAttribute("data-leave-at")) beginLeave(current);
          }, left);
        }
      }
    }
  }

  function scanQueue() {
    var queue = document.getElementById("barista-queue");
    if (!queue) return;
    queue.querySelectorAll(".q-card").forEach(armCard);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scanQueue);
  } else {
    scanQueue();
  }
  document.addEventListener("htmx:afterSwap", scanQueue);
})();
