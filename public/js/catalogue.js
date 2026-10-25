// Log page catalogue: instant filtering, − / + steppers, a short "Added" state on the card,
// and hiding the message at the bottom after a few seconds. Saving itself is done by HTMX.
(function () {
  var list = document.getElementById("catalogue");
  if (!list) return;
  var filterBox = document.getElementById("catalogue-filter");
  var empty = document.getElementById("catalogue-empty");
  var chips = document.querySelectorAll(".filter-chips .chip");
  var mode = "all";

  function applyFilter() {
    var words = filterBox.value.trim().toLowerCase();
    var shown = 0;
    list.querySelectorAll(":scope > li").forEach(function (li) {
      var ok = (!words || li.dataset.name.indexOf(words) !== -1) &&
        (mode === "all" || (mode === "fav" ? li.dataset.fav === "1"
          : li.dataset.tags.indexOf("|" + mode.slice(4) + "|") !== -1));  // "tag:fruit" matches "|fruit|"
      li.hidden = !ok;
      if (ok) shown++;
    });
    empty.hidden = shown > 0;
  }
  filterBox.addEventListener("input", applyFilter);
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      mode = chip.dataset.filter;
      chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c === chip)); });
      applyFilter();
    });
  });

  // − / +: one serving at a time, or 10 g / ml (1 for other units) when the amount is in the food's unit.
  list.addEventListener("click", function (e) {
    var btn = e.target.closest(".step");
    if (!btn) return;
    var form = btn.closest("form");
    var input = form.querySelector("input[name=amount]");
    var select = form.querySelector("select[name=mode]");
    var size = 1;
    if (select && select.value === "amount") size = /^(g|ml)$/.test(select.dataset.unit) ? 10 : 1;
    var next = Math.max(0, (parseFloat(input.value) || 0) + Number(btn.dataset.step) * size);
    input.value = Math.round(next * 100) / 100;
  });

  // After a successful add: the + briefly becomes ✓, then the card's amount resets.
  document.body.addEventListener("htmx:afterRequest", function (e) {
    var form = e.detail.elt;
    if (!form.classList || !form.classList.contains("product") || !e.detail.successful) return;
    var button = form.querySelector(".product-add");
    form.classList.add("added");
    button.textContent = "✓";
    setTimeout(function () {
      form.classList.remove("added");
      button.textContent = "+";
      form.querySelector("input[name=amount]").value = 1;
    }, 1200);
  });

  // Hide the message a few seconds after it last changed.
  var timer;
  document.body.addEventListener("htmx:afterSettle", function () {
    var toast = document.getElementById("toast");
    if (!toast || !toast.classList.contains("show")) return;
    clearTimeout(timer);
    timer = setTimeout(function () { toast.classList.remove("show"); }, 6000);
  });
})();
