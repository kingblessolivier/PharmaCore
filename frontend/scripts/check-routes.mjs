/* Every route must be reachable from the navigation.
 *
 * `/orders` was a 545-line B2B ordering screen, superseded by
 * `/distribution/orders`, still routed, and claimed by no nav group — so it
 * could only be reached by typing the URL, and when you did the sidebar came up
 * almost empty, because the app-scoped nav had no app to scope to. It read as a
 * broken page rather than a retired one.
 *
 * A screen nobody can navigate to is either dead or a bug. This says which, at
 * the moment it happens rather than months later.
 *
 * Deliberately not checked here: whether a page file is imported at all. An
 * unrouted page leaves an unused import, and `tsc --noEmit` already fails the
 * build on that — a second check would be a second thing to keep correct.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const src = "src";
const app = readFileSync(join(src, "App.tsx"), "utf8");
const shell = readFileSync(join(src, "components", "AppShell.tsx"), "utf8");

const routes = [...app.matchAll(/<Route path="(\/[^"]*)"/g)]
  .map((match) => match[1])
  // A catch-all is not a destination, and the sign-in page sits outside the shell.
  .filter((route) => !route.includes("*") && route !== "/login");

/* A group claims a set of path prefixes; an item links to one exact path. Both
   make a route reachable. */
const prefixes = new Set();
for (const block of shell.matchAll(/match:\s*\[([^\]]*)\]/gs)) {
  for (const quoted of block[1].matchAll(/"([^"]+)"/g)) prefixes.add(quoted[1]);
}
const links = new Set([...shell.matchAll(/to:\s*"([^"]+)"/g)].map((match) => match[1]));

const reachable = (route) => {
  // `/products/:id` is reachable if `/products` is.
  const base = route.split("/:")[0];
  return links.has(base) || [...prefixes].some((p) => base === p || base.startsWith(`${p}/`));
};

const orphans = routes.filter((route) => !reachable(route));

if (orphans.length > 0) {
  console.error("Routes no navigation group can reach:\n");
  for (const orphan of orphans) console.error(`  ${orphan}`);
  console.error("\nGive it a nav entry, add it to a group's `match`, or delete the screen.");
  process.exit(1);
}

console.log(`Routes: all ${routes.length} are reachable from the navigation.`);
