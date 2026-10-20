(function () {
  const api = window.ChemVisionAPI;
  if (!api || !api.requireAuth()) return;

  const $ = (id) => document.getElementById(id);

  // ── state ────────────────────────────────────────────────────────────────
  let allCards = [];
  let filtered = [];
  let currentIdx = 0;
  let isFlipped = false;
  let activeTopic = "";
  let revisionMode = false;
  let searchTerm = "";
  let searchTimer = null;

  // ── identity ──────────────────────────────────────────────────────────────
  async function loadIdentity() {
    try {
      const user = await api.profile();
      api.saveSession({ user });
      $("topName").textContent = user.full_name;
      $("topField").textContent = user.field_of_study || "Chemistry";
      $("topAvatar").textContent = api.initials(user.full_name);
    } catch (_) {}
  }

  // ── load flashcards ───────────────────────────────────────────────────────
  async function loadCards() {
    $("loadingState").style.display = "block";
    $("mainArea").style.display = "none";
    $("emptyState").style.display = "none";
    try {
      const params = {};
      if (activeTopic) params.topic = activeTopic;
      if (revisionMode) params.mode = "revision";
      if (searchTerm) params.q = searchTerm;
      allCards = await api.flashcards(params);
      filtered = allCards;
      buildTopicFilters();
      updateStats();
      renderList();
      if (filtered.length === 0) {
        $("emptyState").style.display = "block";
      } else {
        $("mainArea").style.display = "block";
        currentIdx = 0;
        showCard(0);
      }
    } catch (err) {
      $("emptyState").querySelector("h3").textContent = "Could not load flashcards";
      $("emptyState").querySelector("p").textContent = err.message;
      $("emptyState").style.display = "block";
    } finally {
      $("loadingState").style.display = "none";
    }
  }

  function buildTopicFilters() {
    const topics = [...new Set(allCards.map((c) => c.topic))].sort();
    const container = $("topicFilters");
    container.innerHTML = `<button class="chip-btn ${activeTopic === "" ? "active" : ""}" data-topic="">All Topics</button>`;
    topics.forEach((t) => {
      const btn = document.createElement("button");
      btn.className = "chip-btn" + (activeTopic === t ? " active" : "");
      btn.dataset.topic = t;
      btn.textContent = t;
      container.appendChild(btn);
    });
    container.querySelectorAll(".chip-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTopic = btn.dataset.topic;
        loadCards();
      });
    });
  }

  function updateStats() {
    $("statTotal").textContent = filtered.length;
    const known = filtered.filter((c) => c.progress && c.progress.state === "known").length;
    const learning = filtered.filter((c) => c.progress && c.progress.state === "learning").length;
    const revision = filtered.filter((c) => c.progress && c.progress.state === "needs_revision").length;
    const reviewed = filtered.reduce((sum, c) => sum + ((c.progress && c.progress.review_count) || 0), 0);
    $("statKnown").textContent = known;
    $("statLearning").textContent = learning;
    $("statRevision").textContent = revision;
    $("statReviewed").textContent = reviewed;
  }

  function renderList() {
    const list = $("cardList");
    list.innerHTML = "";
    filtered.forEach((card, idx) => {
      const item = document.createElement("div");
      item.className = "card-list-item" + (idx === currentIdx ? " current" : "");
      const state = card.progress ? card.progress.state : "";
      item.innerHTML = `
        <span class="list-dot ${state}"></span>
        <div>
          <div class="list-item-text">${api.escapeHtml(card.front)}</div>
          <div class="list-item-topic">${api.escapeHtml(card.topic)}</div>
        </div>`;
      item.addEventListener("click", () => {
        currentIdx = idx;
        showCard(idx);
        renderList();
      });
      list.appendChild(item);
    });
  }

  function showCard(idx) {
    const card = filtered[idx];
    if (!card) return;

    // reset flip
    isFlipped = false;
    $("flashcardScene").classList.remove("flipped");

    $("cardTopic").textContent = card.topic;
    $("cardTopicBack").textContent = card.topic;
    $("cardFront").textContent = card.front;
    $("cardBack").textContent = card.back;

    if (card.example) {
      $("cardExample").style.display = "block";
      $("cardExampleText").textContent = card.example;
    } else {
      $("cardExample").style.display = "none";
    }

    const diffClass = card.difficulty || "easy";
    const diffLabel = card.difficulty
      ? card.difficulty.charAt(0).toUpperCase() + card.difficulty.slice(1)
      : "";
    ["cardDiffFront", "cardDiffBack"].forEach((id) => {
      const el = $(id);
      el.className = `card-difficulty ${diffClass}`;
      el.textContent = diffLabel;
    });

    $("cardCounter").textContent = `${idx + 1} / ${filtered.length}`;
    const pct = filtered.length > 1 ? ((idx / (filtered.length - 1)) * 100).toFixed(1) : 100;
    $("progressFill").style.width = pct + "%";

    $("prevBtn").disabled = idx === 0;
    $("nextBtn").disabled = idx === filtered.length - 1;

    // highlight current in list
    document.querySelectorAll(".card-list-item").forEach((el, i) => {
      el.classList.toggle("current", i === idx);
    });
    // scroll into view
    const listEl = document.querySelectorAll(".card-list-item")[idx];
    if (listEl) listEl.scrollIntoView({ block: "nearest" });
  }

  // ── flip ──────────────────────────────────────────────────────────────────
  $("flashcardScene").addEventListener("click", () => {
    isFlipped = !isFlipped;
    $("flashcardScene").classList.toggle("flipped", isFlipped);
  });

  // ── navigation ────────────────────────────────────────────────────────────
  $("prevBtn").addEventListener("click", () => {
    if (currentIdx > 0) {
      currentIdx--;
      showCard(currentIdx);
      renderList();
    }
  });
  $("nextBtn").addEventListener("click", () => {
    if (currentIdx < filtered.length - 1) {
      currentIdx++;
      showCard(currentIdx);
      renderList();
    }
  });

  // keyboard
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") $("nextBtn").click();
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") $("prevBtn").click();
    else if (e.key === " " || e.key === "Enter") $("flashcardScene").click();
    else if (e.key === "1") $("btnRevision").click();
    else if (e.key === "2") $("btnLearning").click();
    else if (e.key === "3") $("btnKnown").click();
  });

  // ── review actions ────────────────────────────────────────────────────────
  async function reviewCard(state, correct) {
    const card = filtered[currentIdx];
    if (!card) return;
    try {
      const progress = await api.reviewFlashcard(card.id, { state, correct });
      card.progress = progress;
      updateStats();
      renderList();
      // auto-advance
      if (currentIdx < filtered.length - 1) {
        currentIdx++;
        showCard(currentIdx);
      }
    } catch (err) {
      console.error("Review failed:", err.message);
    }
  }

  $("btnRevision").addEventListener("click", () => reviewCard("needs_revision", false));
  $("btnLearning").addEventListener("click", () => reviewCard("learning", false));
  $("btnKnown").addEventListener("click", () => reviewCard("known", true));

  // ── mode toggle ───────────────────────────────────────────────────────────
  $("modeBtn").addEventListener("click", () => {
    revisionMode = !revisionMode;
    $("modeBtn").classList.toggle("revision-mode", revisionMode);
    $("modeBtn").querySelector("svg + *") ||
      ($("modeBtn").childNodes[1].textContent = revisionMode ? "All Cards" : "Revision Mode");
    // update button text
    const textNode = [...$("modeBtn").childNodes].find((n) => n.nodeType === 3);
    if (textNode) textNode.textContent = revisionMode ? " All Cards" : " Revision Mode";
    loadCards();
  });

  // ── search ────────────────────────────────────────────────────────────────
  $("searchInput").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTerm = e.target.value.trim();
    searchTimer = setTimeout(loadCards, 350);
  });

  // ── exit ──────────────────────────────────────────────────────────────────
  document.querySelectorAll(".exit").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      api.logout();
    });
  });

  // ── init ──────────────────────────────────────────────────────────────────
  loadIdentity();
  loadCards();
})();
