(function () {
  const api = window.ChemVisionAPI;
  if (!api || !api.requireAuth()) return;

  const $  = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const reactionsWrap = $(".reactions");
  const dz    = document.getElementById("dz");
  const input = document.getElementById("fileInput");

  // ── greeting time ─────────────────────────────────────────────────────────
  function greeting() {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  }

  // ── identity ──────────────────────────────────────────────────────────────
  function setIdentity(user) {
    if (!user) return;
    const firstName = (user.full_name || "there").split(/\s+/)[0];
    const title  = $(".greeting h1");
    const name   = $(".identity .who b");
    const field  = $(".identity .who span");
    const avatar = $(".avatar");
    if (title)  title.textContent  = `${greeting()}, ${firstName}`;
    if (name)   name.textContent   = user.full_name;
    if (field)  field.textContent  = user.field_of_study || "Chemistry";
    if (avatar) avatar.textContent = api.initials(user.full_name);
    // Also update topbar avatar if it exists with id
    const topAvatar = document.getElementById("topAvatar");
    if (topAvatar) topAvatar.textContent = api.initials(user.full_name);
  }

  // ── stat cards — populated from real API ──────────────────────────────────
  function updateStatCards(reactions, progress) {
    const cards = $$(".stat-card b");
    // Card 0 = reactions explored
    if (cards[0]) cards[0].textContent = reactions.length;
    // Card 1 = study time placeholder (backend doesn't track time directly)
    if (cards[1] && progress) {
      const reviewed = progress.flashcards_reviewed || 0;
      cards[1].textContent = reviewed > 0 ? reviewed + " cards" : "—";
    }
  }

  // ── render reaction cards ──────────────────────────────────────────────────
  function renderReactions(reactions) {
    if (!reactionsWrap) return;
    if (!reactions.length) {
      reactionsWrap.innerHTML = `
        <article class="rcard">
          <span class="tag">READY</span>
          <h4>No reactions yet</h4>
          <p class="eqn">Upload a PNG, JPG, or WEBP reaction image to begin.</p>
          <hr>
          <div class="yield-row">
            <div><span class="lbl">STATUS</span><span class="val">0</span></div>
          </div>
        </article>`;
      return;
    }
    reactionsWrap.innerHTML = reactions
      .map((r) => `
        <article class="rcard" data-id="${r.id}" tabindex="0" role="button">
          <span class="tag">${api.escapeHtml(r.reaction_type || "REACTION")}</span>
          <h4>${api.escapeHtml(r.reaction_name)}</h4>
          <p class="eqn">${api.formatEquation(r.equation)}</p>
          <hr>
          <div class="yield-row">
            <div>
              <span class="lbl">${r.requires_verification ? "NEEDS REVIEW" : "VERIFIED"}</span>
              <span class="val">${r.ocr_confidence == null ? "--" : Math.round(r.ocr_confidence * 100) + "%"}</span>
            </div>
            <div class="go"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></div>
          </div>
        </article>`)
      .join("");

    reactionsWrap.querySelectorAll(".rcard[data-id]").forEach((card) => {
      const open = () => (window.location.href = `visualizer.html?id=${card.dataset.id}`);
      card.addEventListener("click", open);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") open();
      });
    });
  }

  // ── dropzone feedback ─────────────────────────────────────────────────────
  function setDropzone(message, busy = false) {
    if (!dz) return;
    const title = dz.querySelector("b");
    const sub   = dz.querySelector("span");
    if (title) title.textContent = message;
    if (sub)   sub.textContent   = busy
      ? "Processing image and identifying reaction…"
      : "PNG, JPG or WEBP · up to 8 MB";
  }

  // ── load everything ───────────────────────────────────────────────────────
  async function loadDashboard() {
    try {
      // Load profile + reactions in parallel; progress separately (non-critical)
      const [user, reactions] = await Promise.all([api.profile(), api.reactions()]);
      api.saveSession({ user });
      setIdentity(user);
      renderReactions(reactions);

      // Load progress stats without blocking UI
      api.profileProgress().then((progress) => {
        updateStatCards(reactions, progress);
      }).catch(() => {
        updateStatCards(reactions, null);
      });

    } catch (error) {
      renderReactions([]);
      setDropzone(error.message);
    }
  }

  // ── upload ────────────────────────────────────────────────────────────────
  async function upload(file) {
    if (!file) return;
    setDropzone(`Uploading ${file.name}…`, true);
    try {
      const reaction = await api.uploadReaction(file);
      const reactions = await api.reactions();
      renderReactions(reactions);
      updateStatCards(reactions, null);
      setDropzone(`${reaction.reaction_name} saved`);
      window.setTimeout(
        () => (window.location.href = `visualizer.html?id=${reaction.id}`),
        550
      );
    } catch (error) {
      setDropzone(error.message);
    }
  }

  if (input) input.addEventListener("change", () => upload(input.files?.[0]));
  if (dz) {
    dz.addEventListener("drop", (e) => {
      const file = e.dataTransfer?.files?.[0];
      if (file) upload(file);
    });
  }

  // ── quick access links ────────────────────────────────────────────────────
  const qcards = $$(".qcard");
  const qLinks = ["flashcards.html", "studio.html", "quiz.html"];
  qcards.forEach((card, i) => {
    if (qLinks[i]) {
      card.setAttribute("href", qLinks[i]);
      card.style.cursor = "pointer";
    }
  });

  // ── exit ──────────────────────────────────────────────────────────────────
  $$(".exit").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      api.logout();
    });
  });

  loadDashboard();
})();
