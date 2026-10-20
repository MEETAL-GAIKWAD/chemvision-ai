/**
 * ChemVision AI — Theme Manager
 * Applies saved theme immediately on load (prevents flash).
 * Wires the #themeToggle button present on every app page.
 */
(function () {
  const THEME_KEY = "chemvision_theme";

  // ── apply theme immediately (before paint) ─────────────────────────────────
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    // Update toggle icon if button exists
    const icon = document.getElementById("themeIcon");
    if (!icon) return;
    if (theme === "dark") {
      // sun icon
      icon.innerHTML = `<circle cx="12" cy="12" r="5"/>
        <line x1="12" y1="1" x2="12" y2="3"/>
        <line x1="12" y1="21" x2="12" y2="23"/>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
        <line x1="1" y1="12" x2="3" y2="12"/>
        <line x1="21" y1="12" x2="23" y2="12"/>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>`;
    } else {
      // moon icon
      icon.innerHTML = `<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>`;
    }
  }

  function getSavedTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) return saved;
    // Respect OS preference
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  // Apply immediately to avoid FOUC
  applyTheme(getSavedTheme());

  // Wire toggle button after DOM is ready
  function wireToggle() {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;
    const syncLabel = (theme) => {
      const label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
      btn.setAttribute("aria-label", label);
      btn.setAttribute("title", label);
    };
    btn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next    = current === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
      syncLabel(next);
    });
    // Ensure icon matches current theme
    const current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current);
    syncLabel(current);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireToggle);
  } else {
    wireToggle();
  }

  // Expose for other scripts if needed
  window.ChemVisionTheme = { apply: applyTheme, get: getSavedTheme };
})();
