import { themeModeLabel } from "../theme.js";
import { useTheme } from "../hooks/useTheme.jsx";

export default function ThemeToggle({ className = "ghost" }) {
  const { mode, cycleTheme } = useTheme();

  return (
    <button
      type="button"
      className={className}
      onClick={cycleTheme}
      aria-label={`تم: ${themeModeLabel(mode)}`}
      title={`تم: ${themeModeLabel(mode)}`}
    >
      تم: {themeModeLabel(mode)}
    </button>
  );
}
