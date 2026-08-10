/* Fail the build when a control is made to contain a layout.
 *
 * This existed as a real defect, not a hypothetical. The Price Lists page put a
 * four-tile coverage strip *inside* its "Create Price List" button:
 *
 *     <Button onClick={startCreate}>
 *       <Plus /> Create Price List
 *       <div className="grid grid-cols-2 sm:grid-cols-4"> …four stat tiles… </div>
 *     </Button>
 *
 * Nothing failed. tsc was happy — children are ReactNode, and a grid is a
 * ReactNode. eslint was happy. The build was happy. The page rendered: the
 * button stretched the full width of the screen, its brand fill showing through
 * the grid gaps as four teal stripes, and because the button centres its
 * content the tiles overflowed it top and bottom and painted over the page
 * title. Every tile was also a submit target, so reading the coverage figures
 * opened the create form.
 *
 * A control is phrasing content. The moment one contains a grid or a table the
 * result is not a styling mistake to be argued about — it is a control that
 * lies about what clicking it does. That is worth a gate.
 *
 * Two rules:
 *   1. <Button> — our design-system control — holds a label and an icon. No
 *      block-level anything.
 *   2. Any <button> may not contain another control: a button, a link, a form.
 *      Nesting them means the inner one's clicks fire the outer one too.
 *
 * Rule 2 deliberately permits <div>/<span>/<ul> inside a native <button>: the
 * clickable-row pattern (a mail row, a roster shift) is a real one and reads
 * correctly. It is the *control inside a control* that misbehaves.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/** Elements that may never appear inside our <Button>. */
const BLOCK = ["div", "table", "form", "section", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"];
/** Controls that may never appear inside any button, ours or native. */
const CONTROLS = ["button", "Button", "a", "Link", "NavLink", "form", "input", "select"];

const RULES = [
  { tag: "Button", forbidden: [...BLOCK, ...CONTROLS], why: "a Button holds a label, not a layout" },
  { tag: "button", forbidden: CONTROLS, why: "a control inside a control fires both" },
];

/** Every balanced `<tag …>…</tag>` in a source, as [openStart, childrenStart, childrenEnd].
 *
 * Written as a scanner rather than a regex because the pattern is recursive:
 * a <button> inside a <button> is exactly the case being looked for, so the
 * outer span has to be tracked by depth or the inner one closes it. */
function spans(src, tag) {
  const out = [];
  const open = new RegExp(`<${tag}(?=[\\s/>])`, "g");
  for (const m of src.matchAll(open)) {
    const gt = src.indexOf(">", m.index);
    if (gt === -1 || src[gt - 1] === "/") continue; // self-closing, no children
    let k = gt + 1;
    let depth = 1;
    while (depth > 0 && k < src.length) {
      const nextOpen = src.slice(k).search(new RegExp(`<${tag}(?=[\\s/>])`));
      const o = nextOpen === -1 ? -1 : k + nextOpen;
      const c = src.indexOf(`</${tag}`, k);
      if (c === -1) break;
      if (o !== -1 && o < c) {
        const e = src.indexOf(">", o);
        if (e !== -1 && src[e - 1] !== "/") depth += 1;
        k = e === -1 ? o + 1 : e + 1;
      } else {
        depth -= 1;
        k = c + 1;
      }
    }
    if (depth === 0) out.push([m.index, gt + 1, k]);
  }
  return out;
}

/** Findings for one file's source. Returned rather than printed, so the
 *  self-test below can call it on snippets that never touch the disk. */
function inspect(source, file = "<snippet>") {
  const found = [];
  for (const { tag, forbidden, why } of RULES) {
    for (const [start, from, to] of spans(source, tag)) {
      const body = source.slice(from, to);
      for (const bad of forbidden) {
        // Word-boundary on the tag name so `<a>` does not match `<article>`
        // and `<button>` does not match `<Button>` — JSX is case-sensitive and
        // the two are different rules.
        const hit = new RegExp(`<${bad}(?=[\\s/>])`).exec(body);
        if (!hit) continue;
        found.push({
          file,
          line: source.slice(0, start).split("\n").length,
          outer: tag,
          inner: bad,
          why,
        });
        break; // one finding per control; the first is enough to go and look
      }
    }
  }
  return found;
}

/* The gate checks itself before it checks anything else.
 *
 * A scanner that matches nothing and a codebase with nothing wrong print the
 * same line, and this project has shipped three separate checks that were
 * silently reading no input. So: prove it flags what it must, and — just as
 * important — prove it stays quiet on the patterns that are deliberately fine. */
const MUST_FLAG = [
  ['<Button onClick={x}>Go<div className="grid">a</div></Button>', "the original defect"],
  ["<Button>label<table><tr /></table></Button>", "a table in a control"],
  ["<button><button>inner</button></button>", "nested native buttons"],
  ['<button onClick={x}><Link to="/a">go</Link></button>', "a link inside a button"],
];
const MUST_PASS = [
  ['<Button onClick={x}><Plus className="h-4 w-4" /> Create Price List</Button>', "a normal button"],
  ['<button className="row"><div className="flex"><span>Row</span></div></button>', "clickable row"],
  ["<Button />", "self-closing"],
  ['<div className="grid"><Button>a</Button><Button>b</Button></div>', "buttons side by side"],
];
for (const [snippet, name] of MUST_FLAG) {
  if (inspect(snippet).length === 0) {
    console.error(`\ncheck-markup missed "${name}": ${snippet}\nThe gate proves nothing.\n`);
    process.exit(2);
  }
}
for (const [snippet, name] of MUST_PASS) {
  const noise = inspect(snippet);
  if (noise.length > 0) {
    console.error(`\ncheck-markup flagged "${name}", which is legal: ${snippet}\n`);
    console.error(`  reported: <${noise[0].outer}> containing <${noise[0].inner}>\n`);
    process.exit(2);
  }
}

const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : /\.tsx$/.test(path) ? [path] : [];
  });

const files = walk("src");
const findings = files.flatMap((file) => inspect(readFileSync(file, "utf8"), file));

if (findings.length > 0) {
  console.error(`\n${findings.length} control(s) containing something a control cannot hold:\n`);
  for (const f of findings) {
    console.error(`  ${f.file}:${f.line}  <${f.outer}> contains <${f.inner}> — ${f.why}`);
  }
  console.error("\nMove it out of the control. It is a sibling, not a child.\n");
  process.exit(1);
}
console.log(`Markup: ${files.length} files, no control holds a layout or another control.`);
