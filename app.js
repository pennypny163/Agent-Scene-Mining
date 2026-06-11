(function () {
  "use strict";

  var DATA = null;
  var state = {
    q: "",
    categories: new Set(),
    roles: new Set(),
    sources: new Set(),
    minHeat: 0,
    sort: "heat"
  };

  var $ = function (id) { return document.getElementById(id); };

  /* ---------- Theme ---------- */
  function initTheme() {
    var saved = localStorage.getItem("theme");
    var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    var theme = saved || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
    $("theme-toggle").addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme");
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
    });
  }

  /* ---------- Load ---------- */
  function load() {
    fetch("data/scenes.json")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        DATA = d;
        boot();
      })
      .catch(function (e) {
        $("cards").innerHTML = '<div class="empty">数据加载失败：' + e.message + "</div>";
      });
  }

  function boot() {
    if (DATA.meta) {
      if (DATA.meta.title) $("site-title").textContent = DATA.meta.title;
      if (DATA.meta.subtitle) $("site-subtitle").textContent = DATA.meta.subtitle;
      if (DATA.meta.updated_at) $("updated-at").textContent = DATA.meta.updated_at;
    }
    $("stat-total").textContent = DATA.scenes.length;
    $("stat-week").textContent = countThisWeek();

    buildChips("filter-category", DATA.categories, "categories");
    buildChips("filter-role", DATA.roles, "roles");
    buildChips("filter-source", DATA.sources, "sources");
    bindControls();
    render();
  }

  function countThisWeek() {
    var now = new Date(DATA.meta && DATA.meta.updated_at ? DATA.meta.updated_at : Date.now());
    var weekAgo = new Date(now.getTime() - 7 * 864e5);
    return DATA.scenes.filter(function (s) { return new Date(s.date) >= weekAgo; }).length;
  }

  /* ---------- Filters UI ---------- */
  function buildChips(containerId, items, key) {
    var box = $(containerId);
    box.innerHTML = "";
    items.forEach(function (label) {
      var chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = label;
      chip.addEventListener("click", function () {
        var set = state[key];
        if (set.has(label)) { set.delete(label); chip.classList.remove("active"); }
        else { set.add(label); chip.classList.add("active"); }
        render();
      });
      box.appendChild(chip);
    });
  }

  function bindControls() {
    $("search").addEventListener("input", function (e) {
      state.q = e.target.value.trim().toLowerCase();
      render();
    });

    var range = $("heat-range");
    range.addEventListener("input", function (e) {
      state.minHeat = parseInt(e.target.value, 10);
      $("heat-value").textContent = state.minHeat;
      render();
    });

    document.querySelectorAll(".sort-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".sort-tab").forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        state.sort = tab.getAttribute("data-sort");
        render();
      });
    });

    document.querySelectorAll(".clear-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var which = btn.getAttribute("data-clear");
        var keyMap = { category: "categories", role: "roles", source: "sources" };
        var contMap = { category: "filter-category", role: "filter-role", source: "filter-source" };
        state[keyMap[which]].clear();
        $(contMap[which]).querySelectorAll(".chip").forEach(function (c) { c.classList.remove("active"); });
        render();
      });
    });

    $("reset-all").addEventListener("click", resetAll);
  }

  function resetAll() {
    state.q = "";
    state.categories.clear();
    state.roles.clear();
    state.sources.clear();
    state.minHeat = 0;
    $("search").value = "";
    $("heat-range").value = 0;
    $("heat-value").textContent = "0";
    document.querySelectorAll(".chip").forEach(function (c) { c.classList.remove("active"); });
    render();
  }

  /* ---------- Filtering ---------- */
  function applyFilters() {
    return DATA.scenes.filter(function (s) {
      if (state.minHeat && s.heat < state.minHeat) return false;
      if (state.categories.size && !state.categories.has(s.category)) return false;
      if (state.sources.size && !state.sources.has(s.source)) return false;
      if (state.roles.size) {
        var hit = s.roles.some(function (r) { return state.roles.has(r); });
        if (!hit) return false;
      }
      if (state.q) {
        var hay = (s.name + " " + s.desc + " " + s.tools + " " + s.category + " " + s.roles.join(" ")).toLowerCase();
        if (hay.indexOf(state.q) === -1) return false;
      }
      return true;
    });
  }

  function sortScenes(arr) {
    var copy = arr.slice();
    if (state.sort === "heat") copy.sort(function (a, b) { return b.heat - a.heat; });
    else copy.sort(function (a, b) { return new Date(b.date) - new Date(a.date); });
    return copy;
  }

  /* ---------- Render ---------- */
  function render() {
    var list = sortScenes(applyFilters());
    $("result-count").textContent = list.length;
    var cards = $("cards");
    var empty = $("empty");

    if (!list.length) { cards.innerHTML = ""; empty.hidden = false; return; }
    empty.hidden = true;
    cards.innerHTML = list.map(cardHTML).join("");
  }

  function esc(str) {
    return String(str).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function cardHTML(s) {
    var roleTags = s.roles.map(function (r) { return '<span class="tag">' + esc(r) + "</span>"; }).join("");
    return (
      '<article class="card">' +
        '<div class="card-top">' +
          '<h2 class="card-name">' + esc(s.name) + "</h2>" +
          '<div class="heat-badge">' +
            '<span class="heat-num">' + s.heat + "</span>" +
            '<span class="heat-bar"><i style="width:' + s.heat + '%"></i></span>' +
          "</div>" +
        "</div>" +
        '<p class="card-desc">' + esc(s.desc) + "</p>" +
        '<div class="card-tags">' +
          '<span class="tag cat">' + esc(s.category) + "</span>" +
          roleTags +
        "</div>" +
        '<div class="card-foot">' +
          '<div class="card-meta">' +
            '<span class="card-tool">' + esc(s.tools) + "</span>" +
            '<span class="dot"></span>' +
            "<span>" + esc(s.source) + "</span>" +
            '<span class="dot"></span>' +
            "<span>" + esc(s.date) + "</span>" +
          "</div>" +
          '<a class="card-link" href="' + esc(s.url) + '" target="_blank" rel="noopener">原文 →</a>' +
        "</div>" +
      "</article>"
    );
  }

  initTheme();
  load();
})();
