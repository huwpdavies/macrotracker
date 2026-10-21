// Paste-a-label helper: sends pasted text to the server, which returns the numbers it found.
(function () {
  // Keep the serving size's unit text in step with the unit dropdown.
  var unit = document.getElementById("unit");
  var unitLabel = document.querySelector("[data-unit-label]");
  if (unit && unitLabel) {
    unit.addEventListener("change", function () { unitLabel.textContent = unit.value; });
  }

  var box = document.getElementById("label-text");
  if (!box) return;
  var result = document.getElementById("label-result");
  var timer;

  var NAMES = {
    calories_kcal: "calories", protein_g: "protein", carbs_g: "carbs",
    fat_g: "fat", fibre_g: "fibre", salt_g: "salt"
  };

  box.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(parse, 300);
  });

  function parse() {
    var text = box.value.trim();
    if (!text) { result.textContent = ""; return; }
    var token = document.querySelector("input[name=csrf_token]").value;
    fetch(box.dataset.url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      body: JSON.stringify({ text: text })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var found = Object.keys(data.values);
        if (!found.length) {
          result.textContent = "Nothing recognised. Try copying just the nutrition table rows.";
          return;
        }
        var last;
        found.forEach(function (key) {
          var el = document.getElementById(key);
          if (el) { el.value = data.values[key]; el.dispatchEvent(new Event("change")); last = el; }
        });
        if (last) last.dispatchEvent(new Event("input", { bubbles: true })); // refresh the preview
        var missing = data.missing.map(function (k) { return NAMES[k]; });
        result.textContent = "Filled in " + found.length + " fields." +
          (missing.length ? " Not found: " + missing.join(", ") + "." : "");
      })
      .catch(function () { result.textContent = "Couldn't read that label."; });
  }
})();
