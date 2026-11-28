import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  applyTheme,
  cycleThemeMode,
  getStoredTheme,
  resolveTheme,
  setThemeMode,
} from "../theme.js";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState(getStoredTheme);
  const [resolved, setResolved] = useState(() => resolveTheme(mode));

  useEffect(() => {
    setResolved(applyTheme(mode));

    if (mode !== "system") return undefined;

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setResolved(applyTheme("system"));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [mode]);

  const setTheme = useCallback((nextMode) => {
    const stored = setThemeMode(nextMode);
    setMode(stored);
    setResolved(resolveTheme(stored));
  }, []);

  const cycleTheme = useCallback(() => {
    setMode((current) => {
      const stored = cycleThemeMode(current);
      setResolved(resolveTheme(stored));
      return stored;
    });
  }, []);

  const value = useMemo(
    () => ({ mode, resolved, setTheme, cycleTheme }),
    [mode, resolved, setTheme, cycleTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return ctx;
}
