(function () {
  const api = window.ChemVisionAPI;
  if (!api || !api.requireAuth()) return;
  const $ = (id) => document.getElementById(id);
  let currentProfile = null;

  function value(id, next) {
    const el = $(id);
    if (el) el.value = next || "";
  }

  function text(id, next) {
    const el = $(id);
    if (el) el.textContent = next || "";
  }

  function render(profile) {
    currentProfile = profile;
    const initials = api.initials(profile.full_name);
    const field = profile.field_of_study || "Chemistry";
    const institution = profile.institution || "Institution not set";
    const focus = profile.learning_focus || "Reaction visualization and chemical learning.";

    text("topName", profile.full_name);
    text("topField", field);
    text("topAvatar", initials);
    text("heroName", profile.full_name);
    text("heroSub", `${field} · ${institution}`);
    value("vFullName", profile.full_name);
    value("vEmail", profile.email);
    value("vField", field);
    value("vInstitution", institution);
    value("vFocus", focus);
    text("modalInitials", initials);

    const heroAvatar = $("heroAvatar");
    if (heroAvatar && heroAvatar.firstChild) heroAvatar.firstChild.textContent = `${initials} `;
  }

  function fillEdit() {
    if (!currentProfile) return;
    value("eFullName", currentProfile.full_name);
    value("eEmail", currentProfile.email);
    value("eField", currentProfile.field_of_study || "");
    value("eInstitution", currentProfile.institution || "");
    value("eFocus", currentProfile.learning_focus || "");
    text("modalInitials", api.initials(currentProfile.full_name));
  }

  function showToast(message) {
    text("toastText", message);
    const toast = $("toast");
    if (!toast) return;
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 2400);
  }

  async function load() {
    try {
      const profile = await api.profile();
      api.saveSession({ user: profile });
      render(profile);
      // Load real progress stats
      loadProgress();
    } catch (error) {
      showToast(error.message);
    }
  }

  async function loadProgress() {
    try {
      const p = await api.profileProgress();
      // Update stat cards with real data
      const stats = document.querySelectorAll(".stat-card");
      stats.forEach((card) => {
        const b    = card.querySelector("b");
        const span = card.querySelector("span");
        if (!b || !span) return;
        const label = span.textContent.toLowerCase();
        if (label.includes("reactions") || label.includes("explored")) {
          b.textContent = p.saved_reactions || 0;
        } else if (label.includes("saved")) {
          b.textContent = p.saved_molecules || 0;
        } else if (label.includes("streak")) {
          b.textContent = "—";
        } else if (label.includes("study time") || label.includes("time")) {
          b.textContent = p.flashcards_reviewed
            ? p.flashcards_reviewed + " reviews"
            : "—";
        }
      });

      // Build recent activity section if it exists
      const activityContainer = document.getElementById("recentActivity");
      if (activityContainer && p.recent_activity && p.recent_activity.length) {
        activityContainer.innerHTML = p.recent_activity.slice(0, 5).map((item) => {
          const typeIcon = item.type === "quiz"
            ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;flex-shrink:0;color:var(--accent)"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>`
            : item.type === "molecule"
            ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;flex-shrink:0;color:var(--accent)"><circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="9.5" ry="4.5" transform="rotate(35 12 12)"/><ellipse cx="12" cy="12" rx="9.5" ry="4.5" transform="rotate(-35 12 12)"/></svg>`
            : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;flex-shrink:0;color:var(--accent)"><path d="M3.5 8h3l2-2.5h7L17.5 8h3v11h-17z"/><circle cx="12" cy="13" r="3.2"/></svg>`;
          const date = new Date(item.created_at).toLocaleDateString();
          return `
            <div style="display:flex;align-items:center;gap:12px;padding:11px 14px;background:var(--panel);border:1px solid var(--line);border-radius:10px">
              ${typeIcon}
              <div style="flex:1;min-width:0">
                <div style="font-size:14px;font-weight:600;color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${api.escapeHtml(item.title)}</div>
                <div style="font-size:12px;color:var(--muted)">${api.escapeHtml(item.detail)} · ${date}</div>
              </div>
            </div>`;
        }).join("");
      }

      // Quiz accuracy
      if (p.total_quizzes_attempted > 0) {
        const quizEl = document.getElementById("quizStats");
        if (quizEl) {
          quizEl.textContent =
            `${p.total_quizzes_attempted} attempt${p.total_quizzes_attempted > 1 ? "s" : ""} · avg ${(p.average_quiz_score || 0).toFixed(0)}%`;
        }
      }

      // Flashcard progress
      const fcEl = document.getElementById("flashcardStats");
      if (fcEl) {
        fcEl.textContent =
          `${p.flashcards_reviewed} reviewed · ${p.flashcards_known} known · ${p.flashcards_needing_revision} to revise`;
      }

    } catch (_) {
      // Progress is non-critical; silently ignore
    }
  }

  ["openEdit", "camBadge"].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("click", () => window.setTimeout(fillEdit, 0));
  });

  const editForm = $("editForm");
  if (editForm) {
    editForm.addEventListener(
      "submit",
      async (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          const profile = await api.updateProfile({
            full_name: $("eFullName").value.trim(),
            field_of_study: $("eField").value.trim(),
            institution: $("eInstitution").value.trim(),
            learning_focus: $("eFocus").value.trim(),
          });
          api.saveSession({ user: profile });
          render(profile);
          $("overlay").classList.remove("open");
          document.body.style.overflow = "";
          showToast("Profile updated");
        } catch (error) {
          showToast(error.message);
        }
      },
      true
    );
  }

  document.querySelectorAll(".exit").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      api.logout();
    });
  });

  load();
})();
