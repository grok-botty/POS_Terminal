/* HTMX вставляет шторку допов после старта Alpine — инициализируем заново. */
document.addEventListener("htmx:afterSwap", function (evt) {
  if (window.Alpine && evt.target) {
    window.Alpine.initTree(evt.target);
  }
});
