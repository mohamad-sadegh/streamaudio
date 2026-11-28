const STORAGE_KEY = "pezhvak-theme";

export const THEME_MODES = ["system", "light", "dark"];

export function getStoredTheme() {
  const value = localStorage.getItem(STORAGE_KEY);
  return THEME_MODES.includes(value) ? value : "system";
}

export function resolveTheme(mode = getStoredTheme()) {
  if (mode === "light" || mode === "dark") return mode;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function applyTheme(mode = getStoredTheme()) {
  const resolved = resolveTheme(mode);
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.style.colorScheme = resolved;
  return resolved;
}

export function setThemeMode(mode) {
  const next = THEME_MODES.includes(mode) ? mode : "system";
  localStorage.setItem(STORAGE_KEY, next);
  applyTheme(next);
  return next;
}

export function cycleThemeMode(current = getStoredTheme()) {
  const index = THEME_MODES.indexOf(current);
  const next = THEME_MODES[(index + 1) % THEME_MODES.length];
  return setThemeMode(next);
}

export function themeModeLabel(mode) {
  switch (mode) {
    case "light":
      return "روشن";
    case "dark":
      return "تیره";
    default:
      return "سیستم";
  }
}
