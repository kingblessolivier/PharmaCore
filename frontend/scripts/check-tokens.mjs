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

const FAMILIES = ["brand", "ink", "surface", "danger", "warning", "success", "info"];
const css = readFileSync("src/index.css", "utf8");
const defined = new Set([...css.matchAll(/--([a-z]+-(?:\d{1,3}|strong)):/g)].map((m) => m[1]));
defined.add("line");
defined.add("line-strong");

const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : /\.tsx?$/.test(path) ? [path] : [];
  });

const pattern = new RegExp(
  `\b(?:text|bg|border|ring|from|to|via|divide|placeholder|decoration|fill|stroke)-((?:${FAMILIES.join("|")})(?:-(?:\d{2,3}|strong))?)\b`,
  "g",
);

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
