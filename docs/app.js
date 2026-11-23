/* Conquistas — lista do tópico microsoft-rewards
   Sem dependências. Renderiza a partir de window.REPOS_DATA (data/repos.js),
   com fallback para fetch de data/repos.json. */

(function () {
  "use strict";

  var LANG_COLORS = {
    TypeScript: "#3178c6",
    Python: "#3572A5",
    JavaScript: "#f1e05a",
    HTML: "#e34c26",
    Java: "#b07219",
    Kotlin: "#A97BFF",
    PowerShell: "#012456",
    Shell: "#89e051",
    Batchfile: "#C1F12E",
    C: "#555555",
    "C#": "#178600",
    AutoHotkey: "#6594b9",
    "Jupyter Notebook": "#DA5B0B",
    "Visual Basic .NET": "#945db7",
  };

  var ICONS = {
    star: '<path d="M12 3.2l2.8 5.7 6.3.9-4.6 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.8l6.2-.9z" fill="currentColor" stroke="none"/>',
    fork: '<circle cx="7" cy="4.5" r="1.8"/><circle cx="17" cy="4.5" r="1.8"/><circle cx="7" cy="19.5" r="1.8"/><path d="M7 6.3v11.4M17 6.3v3.2a4 4 0 0 1-4 4H7"/>',
    arrow: '<path d="M7 17 17 7"/><path d="M9 7h8v8"/>',
  };

  var state = {
    query: "",
    language: "all",
    sort: "stars",
    hideArchived: false,
  };

  var data = null;
  var nodes = {};

  // ------------------------------------------------------------------ utils
  function normalize(text) {
    return String(text || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function formatNumber(value) {
    try {
      return new Intl.NumberFormat("pt-BR").format(value);
    } catch (error) {
      return String(value);
    }
  }

  function formatDate(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) return "—";
    try {
      return new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      }).format(date);
    } catch (error) {
      return date.toLocaleDateString();
    }
  }

  function relativeUpdate(iso) {
    var then = Date.parse(iso);
    if (isNaN(then)) return "";
    var days = Math.max(0, Math.floor((Date.now() - then) / 86400000));
    if (days === 0) return "atualizado hoje";
    if (days === 1) return "atualizado ontem";
    if (days < 7) return "atualizado há " + days + " dias";
    if (days < 30) {
      var weeks = Math.round(days / 7);
      return "atualizado há " + weeks + (weeks === 1 ? " semana" : " semanas");
    }
    if (days < 365) {
      var months = Math.round(days / 30);
      return "atualizado há " + months + (months === 1 ? " mês" : " meses");
    }
    var years = Math.floor(days / 365);
    return "atualizado há " + years + (years === 1 ? " ano" : " anos");
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function svgIcon(name, className) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    if (className) svg.setAttribute("class", className);
    svg.innerHTML = ICONS[name];
    return svg;
  }

  // ------------------------------------------------------------------ dados
  function filtered() {
    var query = normalize(state.query).trim();
    var list = data.repos.filter(function (repo) {
      if (state.hideArchived && repo.archived) return false;
      if (state.language !== "all" && (repo.language || "Sem linguagem") !== state.language) {
        return false;
      }
      if (!query) return true;
      var haystack = normalize(
        [repo.full_name, repo.description, repo.owner, (repo.topics || []).join(" "), repo.language]
          .join(" ")
      );
      return query.split(/\s+/).every(function (term) {
        return haystack.indexOf(term) !== -1;
      });
    });

    var sorters = {
      stars: function (a, b) {
        return b.stars - a.stars || a.full_name.localeCompare(b.full_name);
      },
      updated: function (a, b) {
        return Date.parse(b.pushed_at) - Date.parse(a.pushed_at) || b.stars - a.stars;
      },
      forks: function (a, b) {
        return b.forks - a.forks || b.stars - a.stars;
      },
      name: function (a, b) {
        return a.full_name.localeCompare(b.full_name, "pt-BR");
      },
    };
    return list.sort(sorters[state.sort] || sorters.stars);
  }

  // ------------------------------------------------------------------ render
  function createCard(repo, rank) {
    var card = el("a", "card");
    card.href = repo.url;
    card.target = "_blank";
    card.rel = "noopener";
    card.setAttribute(
      "aria-label",
      repo.full_name +
        ", " +
        formatNumber(repo.stars) +
        " estrelas. Abrir no GitHub em nova aba."
    );

    var head = el("div", "card-head");
    head.appendChild(el("span", "rank", "#" + rank));

    var avatar = el("img", "avatar");
    avatar.src = repo.avatar || "";
    avatar.alt = "";
    avatar.width = 30;
    avatar.height = 30;
    avatar.loading = "lazy";
    avatar.decoding = "async";
    avatar.addEventListener("error", function () {
      avatar.style.visibility = "hidden";
    });
    head.appendChild(avatar);

    var titles = el("div", "titles");
    titles.appendChild(el("h2", "repo", repo.full_name.split("/")[1] || repo.full_name));
    titles.appendChild(el("p", "owner", repo.owner));
    head.appendChild(titles);

    if (repo.archived) head.appendChild(el("span", "badge", "arquivado"));
    card.appendChild(head);

    var desc = el("p", "desc", repo.description || "Sem descrição no repositório.");
    if (!repo.description) desc.classList.add("is-empty");
    desc.title = repo.description || "";
    card.appendChild(desc);

    var topics = (repo.topics || []).slice(0, 3);
    if (topics.length) {
      var list = el("ul", "topics");
      topics.forEach(function (topic) {
        list.appendChild(el("li", "topic", topic));
      });
      card.appendChild(list);
    }

    var meta = el("div", "card-meta");

    var stars = el("span", "metric stars");
    stars.appendChild(svgIcon("star"));
    stars.appendChild(el("span", null, formatNumber(repo.stars)));
    meta.appendChild(stars);

    var forks = el("span", "metric");
    forks.appendChild(svgIcon("fork"));
    forks.appendChild(el("span", null, formatNumber(repo.forks)));
    meta.appendChild(forks);

    var language = el("span", "lang");
    var languageName = repo.language || "Sem linguagem";
    var dot = el("span", "lang-dot");
    dot.style.background = LANG_COLORS[languageName] || "var(--muted)";
    language.appendChild(dot);
    language.appendChild(el("span", null, languageName));
    meta.appendChild(language);

    card.appendChild(meta);

    var foot = el("div", "card-foot");
    foot.appendChild(el("span", "updated", relativeUpdate(repo.pushed_at)));

    var cta = el("span", "cta");
    cta.appendChild(el("span", null, "Abrir no GitHub"));
    cta.appendChild(svgIcon("arrow"));
    foot.appendChild(cta);

    card.appendChild(foot);
    return card;
  }

  function render() {
    var list = filtered();
    var fragment = document.createDocumentFragment();
    list.forEach(function (repo, index) {
      fragment.appendChild(createCard(repo, index + 1));
    });
    nodes.grid.replaceChildren(fragment);

    var hasFilters =
      state.query.trim() !== "" || state.language !== "all" || state.hideArchived;
    var text = hasFilters
      ? list.length + " de " + data.total + (data.total === 1 ? " projeto" : " projetos")
      : list.length + (list.length === 1 ? " projeto" : " projetos");
    if (state.language !== "all") text += " · " + state.language;
    if (state.hideArchived) text += " · arquivados ocultos";
    nodes.count.textContent = text;

    nodes.empty.hidden = list.length !== 0;
    nodes.grid.hidden = list.length === 0;
  }

  // ------------------------------------------------------------------ filtros
  function buildChips() {
    var fragment = document.createDocumentFragment();
    var options = [{ name: "all", label: "Todos", count: data.total }];
    Object.keys(data.languages).forEach(function (language) {
      options.push({ name: language, label: language, count: data.languages[language] });
    });

    options.forEach(function (option) {
      var chip = el("button", "chip");
      chip.type = "button";
      chip.dataset.language = option.name;
      chip.appendChild(el("span", null, option.label));
      chip.appendChild(el("span", "lang-count", " " + option.count));
      chip.setAttribute("aria-pressed", String(state.language === option.name));
      chip.addEventListener("click", function () {
        state.language = option.name;
        Array.prototype.forEach.call(nodes.chips.children, function (other) {
          other.setAttribute("aria-pressed", String(other === chip));
        });
        render();
      });
      fragment.appendChild(chip);
    });

    nodes.chips.replaceChildren(fragment);
  }

  function resetFilters() {
    state.query = "";
    state.language = "all";
    state.hideArchived = false;
    state.sort = "stars";
    nodes.input.value = "";
    nodes.hideArchived.checked = false;
    nodes.sort.value = "stars";
    Array.prototype.forEach.call(nodes.chips.children, function (chip) {
      chip.setAttribute("aria-pressed", String(chip.dataset.language === "all"));
    });
    render();
    nodes.input.focus();
  }

  function debounce(fn, delay) {
    var timer = null;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(fn, delay);
    };
  }

  // ------------------------------------------------------------------ init
  function init(payload) {
    data = payload;

    nodes.grid = document.getElementById("lista");
    nodes.count = document.getElementById("count");
    nodes.empty = document.getElementById("empty");
    nodes.chips = document.getElementById("langChips");
    nodes.input = document.getElementById("q");
    nodes.sort = document.getElementById("sort");
    nodes.hideArchived = document.getElementById("hideArchived");

    document.getElementById("repoTotal").textContent = formatNumber(data.total);
    document.getElementById("statRepos").textContent = formatNumber(data.total);
    document.getElementById("statStars").textContent = formatNumber(data.total_stars);
    document.getElementById("statLangs").textContent = formatNumber(
      Object.keys(data.languages).length
    );
    document.getElementById("statActive").textContent = formatNumber(
      data.repos.filter(function (repo) {
        return Date.now() - Date.parse(repo.pushed_at) < 30 * 86400000;
      }).length
    );
    document.getElementById("generatedAt").textContent = formatDate(data.generated_at);
    document.title = "Microsoft Rewards no GitHub — " + data.total + " projetos para explorar";

    buildChips();

    nodes.input.addEventListener(
      "input",
      debounce(function () {
        state.query = nodes.input.value;
        render();
      }, 120)
    );

    nodes.sort.addEventListener("change", function () {
      state.sort = nodes.sort.value;
      render();
    });

    nodes.hideArchived.addEventListener("change", function () {
      state.hideArchived = nodes.hideArchived.checked;
      render();
    });

    document.getElementById("clearFilters").addEventListener("click", resetFilters);

    render();
  }

  function fail(message) {
    var grid = document.getElementById("lista");
    grid.textContent = message;
    grid.className = "empty";
  }

  function boot() {
    if (window.REPOS_DATA && window.REPOS_DATA.repos) {
      init(window.REPOS_DATA);
      return;
    }
    fetch("data/repos.json")
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(init)
      .catch(function () {
        fail("Não foi possível carregar os dados. Abra a página por um servidor HTTP local.");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
