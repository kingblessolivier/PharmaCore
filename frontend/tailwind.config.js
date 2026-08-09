/** @type {import('tailwindcss').Config} */
// Design tokens from docs/design/01-design-tokens.md, surfaced as Tailwind colors.
// Values reference CSS variables (see src/index.css) so light/dark swap in one place.
//
// Every step declared here must also exist in index.css. A Tailwind colour whose
// variable is missing still generates a rule — `color: var(--nope)` — which
// silently computes to `inherit`, so the failure looks like a design decision
// rather than a bug. `scripts/check-tokens.mjs` compares the two and fails the
// build when they diverge; that is how 696 dead colour utilities went unnoticed.

const ramp = (name, steps) =>
  Object.fromEntries(steps.map((s) => [s, `var(--${name}-${s})`]));

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: ramp("brand", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        ink: ramp("ink", [300, 400, 500, 600, 700, 800, 900]),
        surface: ramp("surface", [0, 50, 100, 200]),
        danger: ramp("danger", [50, 200, 300, 500, 600, 700, 800, 900]),
        warning: ramp("warning", [50, 200, 300, 400, 500, 600, 700, 800, 900]),
        success: ramp("success", [50, 200, 500, 600, 700, 800, 900]),
        info: ramp("info", [50, 200, 500, 600, 700]),
        line: {
          DEFAULT: "var(--line-200)",
          200: "var(--line-200)",
          strong: "var(--line-strong)",
        },
      },
      borderRadius: {
        md: "8px",
        lg: "12px",
      },
      spacing: {
        // Row heights an ERP grid is built on — a screen read for eight hours
        // needs a rhythm, not ad-hoc padding.
        row: "var(--row-h)",
        "row-compact": "var(--row-h-compact)",
        field: "var(--field-h)",
      },
      fontSize: {
        // Dense-form scale. 13px is the workhorse: small enough to fit a real
        // document on one screen, large enough to read all day.
        micro: ["11px", { lineHeight: "16px" }],
        form: ["13px", { lineHeight: "18px" }],

        // Tailwind's defaults are a website scale — 14px body, 24px headings —
        // and at 100% zoom that reads as oversized next to a real ERP. These
        // override the defaults so every existing `text-sm` / `text-2xl` in the
        // app tightens at once, rather than needing 200 files edited.
        xs: ["11px", { lineHeight: "16px" }],
        sm: ["12.5px", { lineHeight: "18px" }],
        base: ["13.5px", { lineHeight: "20px" }],
        lg: ["15px", { lineHeight: "22px" }],
        xl: ["17px", { lineHeight: "24px" }],
        "2xl": ["20px", { lineHeight: "28px" }],
        "3xl": ["24px", { lineHeight: "32px" }],
      },
      fontFamily: {
        // "Inter Variable" is the family name @fontsource-variable/inter
        // registers. Naming plain "Inter" — as this did — matched nothing and
        // fell through to system-ui, so the typeface was never actually used.
        sans: ['"Inter Variable"', "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"IBM Plex Mono"', "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
