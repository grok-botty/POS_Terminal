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
