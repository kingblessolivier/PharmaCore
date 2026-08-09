/* Fail the build when a colour used in the app has no token behind it.
 *
 * This existed as a real defect, not a hypothetical: the palette defined ten
 * variables while the code referenced forty-eight, so 696 of 2,600 colour
 * utilities — every danger, warning and success — generated no CSS at all. The
 * screens looked designed; they just had no colour on them. A missing token
 * fails silently in Tailwind, which is why it needs a check rather than care.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const FAMILIES = ["brand", "ink", "surface", "danger", "warning", "success", "info", "chrome"];
/* Families this project invented but never registered with Tailwind. `bg-app`
 * read like a token, resolved to nothing, and slipped through because the
 * check only looked for families it already knew about. Anything named here is
 * reported wherever it appears. */
const UNREGISTERED = ["app", "accent", "muted", "paper"];
const css = readFileSync("src/index.css", "utf8");
const defined = new Set([...css.matchAll(/--([a-z]+-(?:\d{1,3}|strong)):/g)].map((m) => m[1]));
defined.add("line");
defined.add("line-strong");

const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : /\.tsx?$/.test(path) ? [path] : [];
  });

/* Built as a literal, not from a template string.
 *
 * It used to be assembled with backticks — where `\b` is a backspace character
 * and `\d` is a plain "d", so the pattern matched nothing at all. The check
 * that exists *because* a missing token fails silently in Tailwind was itself
 * failing silently, and reporting "every utility used resolves" while reading
 * no utilities. Proven by the self-test below, which is why it is here.
 *
 * The family list is interpolated with `source`, which keeps its escapes.
 */
const FAMILY_ALT = new RegExp([...FAMILIES, ...UNREGISTERED].join("|")).source;
const pattern = new RegExp(
  String.raw`\b(?:text|bg|border|ring|from|to|via|divide|placeholder|decoration|fill|stroke)-` +
    String.raw`((?:${FAMILY_ALT})(?:-(?:\d{1,3}|strong))?)\b`,
  "g",
);

/* The gate checks itself before it checks anything else. A silent regex is the
 * one failure mode this file cannot afford, and it is invisible from the
 * outside: a broken pattern and a clean codebase print the same line. */
for (const [probe, expected] of [
  ["bg-brand-600", "brand-600"],
  // One digit. `surface-0` used to capture as bare "surface" and be reported
  // missing on 89 files, because the step pattern demanded two digits.
  ["bg-surface-0", "surface-0"],
  ["text-ink-500", "ink-500"],
  ["border-chrome-400", "chrome-400"],
]) {
  const found = [...probe.matchAll(pattern)].map((m) => m[1]);
  if (found[0] !== expected) {
    console.error(
      `\ncheck-tokens is not matching anything: "${probe}" gave ${JSON.stringify(found)}, ` +
        `expected ["${expected}"].\nThe pattern is broken, so this gate proves nothing.\n`,
    );
    process.exit(2);
  }
}

const missing = new Map();
for (const file of walk("src")) {
  const source = readFileSync(file, "utf8");
  for (const match of source.matchAll(pattern)) {
    const token = match[1];
    // A bare family name (`text-danger`) is never defined and is always a typo.
    if (defined.has(token)) continue;
    if (!missing.has(token)) missing.set(token, new Set());
    missing.get(token).add(file);
  }
}

if (missing.size > 0) {
  console.error(`\n${missing.size} colour token(s) used with nothing behind them:\n`);
  for (const [token, files] of [...missing].sort()) {
    console.error(`  ${token}`);
    for (const file of [...files].slice(0, 3)) console.error(`      ${file}`);
    if (files.size > 3) console.error(`      … and ${files.size - 3} more`);
  }
  console.error("\nAdd the step to src/index.css and tailwind.config.js, or use a defined one.\n");
  process.exit(1);
}
console.log(`Colour tokens: every utility used resolves. ${defined.size} defined.`);
