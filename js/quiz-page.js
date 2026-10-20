(function () {
  const api = window.ChemVisionAPI;
  if (!api || !api.requireAuth()) return;

  const $ = (id) => document.getElementById(id);

  // ── state ────────────────────────────────────────────────────────────────
  let questions   = [];
  let answers     = {};   // questionId → choiceId (null = skipped)
  let currentQ    = 0;
  let submitted   = false;
  let lastAttempt = null;

  // ── identity ──────────────────────────────────────────────────────────────
  async function loadIdentity() {
    try {
      const user = await api.profile();
      api.saveSession({ user });
      $("topName").textContent    = user.full_name;
      $("topField").textContent   = user.field_of_study || "Chemistry";
      $("topAvatar").textContent  = api.initials(user.full_name);
    } catch (_) {}
  }

  // ── screens ───────────────────────────────────────────────────────────────
  function showScreen(id) {
    ["setupScreen", "quizScreen", "resultsScreen"].forEach((s) =>
      $(s).classList.add("hidden")
    );
    $(id).classList.remove("hidden");
  }

  // ── history ───────────────────────────────────────────────────────────────
  async function loadHistory() {
    try {
      const attempts = await api.quizAttempts();
      if (!attempts.length) return;
      $("historySection").style.display = "block";
      const list = $("historyList");
      list.innerHTML = "";
      attempts.slice(0, 6).forEach((a) => {
        const cls = a.percentage >= 70 ? "high" : a.percentage >= 40 ? "mid" : "low";
        const topicLabel = a.topic || "Mixed";
        const diffLabel  = a.difficulty || "All levels";
        const date = new Date(a.created_at).toLocaleDateString();
        list.innerHTML += `
          <div class="history-item">
            <div class="history-score ${cls}">${Math.round(a.percentage)}%</div>
            <div class="history-meta">
              <b>${api.escapeHtml(topicLabel)} — ${api.escapeHtml(diffLabel)}</b>
              <span>${a.score}/${a.total_questions} correct &nbsp;·&nbsp; ${date}</span>
            </div>
          </div>`;
      });
    } catch (_) {}
  }

  // ── start quiz ────────────────────────────────────────────────────────────
  $("startBtn").addEventListener("click", async () => {
    const topic = $("topicSelect").value;
    const diff  = $("diffSelect").value;
    $("startBtn").disabled    = true;
    $("startBtn").textContent = "Loading…";
    try {
      const params = { limit: 10 };
      if (topic) params.topic      = topic;
      if (diff)  params.difficulty = diff;
      questions = await api.quizQuestions(params);
      if (!questions.length) {
        alert("No questions found for that combination. Try different filters.");
        return;
      }
      answers   = {};
      currentQ  = 0;
      submitted = false;
      buildNavDots();
      showScreen("quizScreen");
      renderQuestion();
    } catch (err) {
      alert("Could not load questions: " + err.message);
    } finally {
      $("startBtn").disabled    = false;
      $("startBtn").innerHTML   = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Start Quiz';
    }
  });

  // ── nav dots ──────────────────────────────────────────────────────────────
  function buildNavDots() {
    const nav = $("qNav");
    nav.innerHTML = "";
    questions.forEach((q, i) => {
      const btn = document.createElement("button");
      btn.className  = "q-dot";
      btn.textContent = i + 1;
      btn.addEventListener("click", () => { currentQ = i; renderQuestion(); });
      nav.appendChild(btn);
    });
  }

  function refreshDots() {
    const dots = $("qNav").querySelectorAll(".q-dot");
    dots.forEach((dot, i) => {
      dot.className = "q-dot";
      if (answers[questions[i].id] !== undefined) dot.classList.add("answered");
      if (i === currentQ) dot.classList.add("current");
    });
  }

  // ── render question ───────────────────────────────────────────────────────
  function renderQuestion() {
    const q = questions[currentQ];
    if (!q) return;

    $("qCurrent").textContent = currentQ + 1;
    $("qTotal").textContent   = questions.length;
    $("qTopic").textContent   = q.topic || "";
    $("qNum").textContent     = `Question ${currentQ + 1}`;
    $("qPrompt").textContent  = q.prompt;

    const pct = ((currentQ + 1) / questions.length) * 100;
    $("qProgress").style.width = pct + "%";

    // choices
    const container = $("choicesContainer");
    container.innerHTML = "";
    const labels = ["A", "B", "C", "D", "E"];
    q.choices.forEach((choice, ci) => {
      const btn = document.createElement("button");
      btn.className = "choice";
      btn.disabled  = submitted;
      const selected = answers[q.id] === choice.id;
      if (selected) btn.classList.add("selected");

      btn.innerHTML = `
        <span class="choice-label">${labels[ci] || ci + 1}</span>
        ${api.escapeHtml(choice.text)}`;

      if (!submitted) {
        btn.addEventListener("click", () => {
          answers[q.id] = choice.id;
          renderQuestion();   // re-render to show selection
        });
      }
      container.appendChild(btn);
    });

    $("qPrevBtn").disabled = currentQ === 0;
    $("qNextBtn").disabled = currentQ === questions.length - 1;
    refreshDots();
  }

  // ── navigation ────────────────────────────────────────────────────────────
  $("qPrevBtn").addEventListener("click", () => {
    if (currentQ > 0) { currentQ--; renderQuestion(); }
  });
  $("qNextBtn").addEventListener("click", () => {
    if (currentQ < questions.length - 1) { currentQ++; renderQuestion(); }
  });

  // ── submit ────────────────────────────────────────────────────────────────
  $("qSubmitBtn").addEventListener("click", async () => {
    const unanswered = questions.filter((q) => answers[q.id] === undefined).length;
    if (unanswered > 0) {
      const ok = confirm(`You have ${unanswered} unanswered question(s). Submit anyway?`);
      if (!ok) return;
    }

    $("qSubmitBtn").disabled    = true;
    $("qSubmitBtn").textContent = "Submitting…";

    const payload = {
      topic:      $("topicSelect").value || undefined,
      difficulty: $("diffSelect").value  || undefined,
      answers: questions.map((q) => ({
        question_id: q.id,
        choice_id:   answers[q.id] !== undefined ? answers[q.id] : null,
      })),
    };

    try {
      lastAttempt = await api.submitQuiz(payload);
      submitted   = true;
      showResults(lastAttempt);
      loadHistory();  // refresh history quietly
    } catch (err) {
      alert("Submission failed: " + err.message);
    } finally {
      $("qSubmitBtn").disabled    = false;
      $("qSubmitBtn").textContent = "Submit Quiz";
    }
  });

  // ── results ───────────────────────────────────────────────────────────────
  function showResults(attempt) {
    const pct     = Math.round(attempt.percentage);
    const correct = attempt.score;
    const wrong   = attempt.answered_questions - attempt.score;
    const skipped = attempt.total_questions - attempt.answered_questions;

    $("resPct").textContent      = pct + "%";
    $("resCorrect").textContent  = correct;
    $("resWrong").textContent    = wrong;
    $("resUnanswered").textContent = skipped;

    if (pct >= 80)      { $("resTitle").textContent = "Excellent Work!"; }
    else if (pct >= 60) { $("resTitle").textContent = "Good Effort!"; }
    else if (pct >= 40) { $("resTitle").textContent = "Keep Practising!"; }
    else               { $("resTitle").textContent = "More Study Needed"; }

    $("resSubtitle").textContent =
      `${correct}/${attempt.total_questions} correct · ${pct}%`;

    $("answersSection").classList.add("hidden");
    showScreen("resultsScreen");
  }

  // ── review answers ────────────────────────────────────────────────────────
  $("reviewBtn").addEventListener("click", () => {
    if (!lastAttempt || !lastAttempt.responses.length) return;
    const section = $("answersSection");
    if (!section.classList.contains("hidden")) {
      section.classList.add("hidden");
      return;
    }
    const list = $("answersList");
    list.innerHTML = "";
    lastAttempt.responses.forEach((r) => {
      const cls = r.is_correct ? "correct" : "wrong";
      const selChoice = questions
        .find((q) => q.id === r.question_id)
        ?.choices?.find((c) => c.id === r.selected_choice_id);
      const corrChoice = questions
        .find((q) => q.id === r.question_id)
        ?.choices?.find((c) => c.id === r.correct_choice_id);

      list.innerHTML += `
        <div class="answer-item ${cls}">
          <div class="answer-prompt">${api.escapeHtml(r.prompt)}</div>
          ${selChoice
            ? `<div class="answer-detail">Your answer: <b>${api.escapeHtml(selChoice.text)}</b></div>`
            : `<div class="answer-detail" style="color:#e57c1a">Skipped</div>`}
          ${!r.is_correct && corrChoice
            ? `<div class="answer-detail">Correct answer: <b>${api.escapeHtml(corrChoice.text)}</b></div>`
            : ""}
          ${r.explanation
            ? `<div class="answer-explanation">${api.escapeHtml(r.explanation)}</div>`
            : ""}
        </div>`;
    });
    section.classList.remove("hidden");
  });

  // ── retry ─────────────────────────────────────────────────────────────────
  $("retryBtn").addEventListener("click", () => {
    showScreen("setupScreen");
    loadHistory();
  });

  // ── exit ──────────────────────────────────────────────────────────────────
  document.querySelectorAll(".exit").forEach((el) => {
    el.addEventListener("click", (e) => { e.preventDefault(); api.logout(); });
  });

  // ── init ──────────────────────────────────────────────────────────────────
  async function init() {
    $("loadingState").classList.remove("hidden");
    await loadIdentity();
    await loadHistory();
    $("loadingState").classList.add("hidden");
    showScreen("setupScreen");
  }

  init();
})();
