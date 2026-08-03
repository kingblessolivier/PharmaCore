/** @type {import('tailwindcss').Config} */
// Design tokens from docs/design/01-design-tokens.md, surfaced as Tailwind colors.
// Values reference CSS variables (see src/index.css) so light/dark swap in one place.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "var(--brand-50)",
          500: "var(--brand-500)",
          600: "var(--brand-600)",
          700: "var(--brand-700)",
        },
        ink: {
          500: "var(--ink-500)",
          700: "var(--ink-700)",
          900: "var(--ink-900)",
        },
        surface: {
          0: "var(--surface-0)",
          100: "var(--surface-100)",
        },
        line: "var(--line-200)",
      },
      borderRadius: {
        md: "8px",
        lg: "12px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
