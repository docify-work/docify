// Runs before first paint (loaded synchronously from index.html; external file so a strict CSP allows it).
// Public pages are always light; app pages follow the saved choice: "light" (default) | "dark" | "system".
(function () {
  try {
    var app = /^\/(app|new|account|w|dev)(\/|$)/.test(location.pathname);
    var pref = localStorage.getItem("docify-theme") || "light";
    var dark = app && (pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches));
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  } catch (e) {
    document.documentElement.dataset.theme = "light";
  }
})();
