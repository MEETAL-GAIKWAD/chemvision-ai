(function () {
  const API_BASE =
    localStorage.getItem("chemvision_api_base") ||
    window.CHEMVISION_API_BASE ||
    "http://127.0.0.1:8000";
  const TOKEN_KEY = "chemvision_token";
  const USER_KEY = "chemvision_user";

  function token() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function saveSession(data) {
    if (data && data.access_token) {
      localStorage.setItem(TOKEN_KEY, data.access_token);
    }
    if (data && data.user) {
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    }
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function cachedUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch (_error) {
      return null;
    }
  }

  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const body = options.body;
    if (body && !(body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (token()) {
      headers.set("Authorization", `Bearer ${token()}`);
    }

    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    } catch (_error) {
      // Network error — backend is not reachable
      throw new Error(
        "Cannot reach the ChemVision backend. Make sure FastAPI is running on port 8000."
      );
    }

    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_parseError) {
      data = null;
    }

    if (!response.ok) {
      if (response.status === 401) {
        clearSession();
        const detail = data && data.detail;
        throw new Error(detail || "Authentication failed. Please sign in again.");
      }
      if (response.status === 403) {
        const detail = data && data.detail;
        throw new Error(detail || "Access denied.");
      }
      if (response.status === 409) {
        const detail = data && data.detail;
        throw new Error(detail || "Conflict: resource already exists.");
      }
      if (response.status === 422) {
        // Pydantic validation error
        const detail = data && data.detail;
        if (Array.isArray(detail)) {
          const msgs = detail.map((e) => {
            const loc = e.loc && e.loc.slice(1).join(" → ");
            return loc ? `${loc}: ${e.msg}` : e.msg;
          });
          throw new Error("Validation error: " + msgs.join("; "));
        }
        throw new Error(detail || "Validation error.");
      }
      if (response.status >= 500) {
        const detail = data && data.detail;
        throw new Error("Server error: " + (detail || `HTTP ${response.status}`));
      }
      const detail = data && data.detail;
      throw new Error(
        Array.isArray(detail) ? detail[0].msg : detail || `Request failed (HTTP ${response.status}).`
      );
    }
    return data;
  }

  function requireAuth() {
    if (!token()) {
      window.location.href = "signup.html";
      return false;
    }
    return true;
  }

  function initials(name) {
    return (name || "CV")
      .replace(/^Dr\.?\s*/i, "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "CV";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatEquation(value) {
    return escapeHtml(value || "Equation unavailable")
      .replaceAll("-&gt;", "→")
      .replace(/\b([A-Z][a-z]?)(\d+)/g, "$1<sub>$2</sub>")
      .replace(/\bH(\d+)/g, "H<sub>$1</sub>")
      .replace(/\bO(\d+)/g, "O<sub>$1</sub>")
      .replace(/\bC(\d+)/g, "C<sub>$1</sub>")
      .replace(/\bN(\d+)/g, "N<sub>$1</sub>");
  }

  window.ChemVisionAPI = {
    API_BASE,
    token,
    saveSession,
    clearSession,
    cachedUser,
    request,
    requireAuth,
    initials,
    escapeHtml,
    formatEquation,
    signup: (payload) =>
      request("/api/auth/signup", { method: "POST", body: JSON.stringify(payload) }),
    login: (payload) =>
      request("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
    profile: () => request("/api/profile"),
    updateProfile: (payload) =>
      request("/api/profile", { method: "PUT", body: JSON.stringify(payload) }),
    reactions: () => request("/api/reactions"),
    reaction: (id) => request(`/api/reactions/${id}`),
    profileProgress: () => request("/api/profile/progress"),
    validateMolecule: (payload) =>
      request("/api/studio/validate", { method: "POST", body: JSON.stringify(payload) }),
    searchMolecules: (q) => request(`/api/studio/search?q=${encodeURIComponent(q)}`),
    saveMolecule: (payload) =>
      request("/api/studio/molecules", { method: "POST", body: JSON.stringify(payload) }),
    savedMolecules: () => request("/api/studio/molecules"),
    flashcards: (params = {}) => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value) query.set(key, value);
      });
      return request(`/api/flashcards${query.toString() ? "?" + query.toString() : ""}`);
    },
    reviewFlashcard: (id, payload) =>
      request(`/api/flashcards/${id}/review`, { method: "POST", body: JSON.stringify(payload) }),
    quizQuestions: (params = {}) => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value) query.set(key, value);
      });
      return request(`/api/quizzes/questions${query.toString() ? "?" + query.toString() : ""}`);
    },
    submitQuiz: (payload) =>
      request("/api/quizzes/submit", { method: "POST", body: JSON.stringify(payload) }),
    quizAttempts: () => request("/api/quizzes/attempts"),
    uploadReaction: (file) => {
      const form = new FormData();
      form.append("file", file);
      return request("/api/reactions/upload", { method: "POST", body: form });
    },
    logout: () => {
      clearSession();
      window.location.href = "home.html";
    },
  };
})();
