/* -------------------------------------------------------------------------- */
/* Light or dark, chosen — not inherited from the operator's laptop.           */
/*                                                                             */
/* These screens follow the OS by default in most web apps, and that turned out */
/* to be wrong here: a pharmacy counter is a bright room, the screens are built */
/* against a light reference, and a cashier whose personal machine happens to   */
/* be in dark mode was getting a dark till. Light is the default; dark is a     */
/* deliberate choice, remembered per browser.                                   */
/* -------------------------------------------------------------------------- */

export type Theme = "light" | "dark";

const KEY = "pharmacore.theme";

export function storedTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
  } catch {
    // Private browsing, or storage disabled — light is the safe default.
    return "light";
  }
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* Nothing to do — the attribute is set, it simply will not persist. */
  }
}

/** Call once, before first paint, so the page never flashes the wrong theme. */
export function initTheme(): void {
  document.documentElement.setAttribute("data-theme", storedTheme());
}
