import { createContext, useContext, useEffect, useState } from "react";

// index.html repeats this key and resolution to theme the page before React renders.
export const THEME_STORAGE_KEY = "gentians-theme";
export const themeChoices = [
  ["system", "Sistema"],
  ["light", "Claro"],
  ["dark", "Oscuro"],
];

export const validThemeChoice = (value) =>
  themeChoices.some(([choice]) => choice === value) ? value : "system";

export const resolveTheme = (choice, systemDark) =>
  choice === "system" ? (systemDark ? "dark" : "light") : choice;

const DARK_QUERY = "(prefers-color-scheme: dark)";

export const ThemeContext = createContext("light");
export const useResolvedTheme = () => useContext(ThemeContext);

/** Keep the chosen theme, follow the system when asked and apply it to <html>. */
export function useThemeChoice() {
  const [choice, setChoice] = useState(() =>
    validThemeChoice(window.localStorage.getItem(THEME_STORAGE_KEY)),
  );
  const [systemDark, setSystemDark] = useState(() => window.matchMedia(DARK_QUERY).matches);

  useEffect(() => {
    const query = window.matchMedia(DARK_QUERY);
    const update = (event) => setSystemDark(event.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  const theme = resolveTheme(choice, systemDark);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, choice);
  }, [choice, theme]);

  return { choice, setChoice, theme };
}
