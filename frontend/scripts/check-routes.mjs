/* Every route must be reachable from the navigation, and every navigation
 * link must lead to a route.
 *
 * The second half was missing, and it cost immediately: a simplified menu
 * written for two-person pharmacies shipped with six of its fourteen links
 * pointing at paths that had never existed — /inventory/stock, /finance/money-in,
 * /apps. The build was clean, this gate was green, and every one of those
 * entries would have dropped the user on the home page with no explanation.
 *
 * A link is a promise. Checking only that routes have menus proves nothing
 * about whether the menus have routes.
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

/* `path` may sit on the same line as `<Route` or on its own, because prettier
   breaks a long element across lines. The original pattern demanded
   `<Route path="` adjacently and so never saw the multi-line ones — it reported
   "all 85 routes are reachable" while nine of them were invisible to it, and
   the check for dangling links added later then accused them of not existing. */
const routes = [...app.matchAll(/<Route\b[^>]*?\bpath="(\/[^"]*)"/gs)]
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

/* The gate checks itself first. A pattern that matches nothing and a codebase
   with nothing wrong print the same line, and this project has shipped three
   checks that were silently reading no input. */
if (routes.length < 50 || links.size < 50) {
  console.error(
    `\ncheck-routes read ${routes.length} route(s) and ${links.size} link(s), which is far ` +
      `too few.\nThe patterns are broken, so this gate proves nothing.\n`,
  );
  process.exit(2);
}

const orphans = routes.filter((route) => !reachable(route));

/* The other direction. A nav entry pointing at a path with no <Route> lands the
   user on the home page via the catch-all — indistinguishable, from the outside,
   from a menu item that simply does nothing. */
const routeSet = new Set(routes);
const bases = new Set(routes.map((route) => route.split("/:")[0]));
const dangling = [...links].filter(
  (link) => !routeSet.has(link) && !bases.has(link) && !link.startsWith("http"),
);

if (orphans.length > 0 || dangling.length > 0) {
  if (orphans.length > 0) {
    console.error("Routes no navigation group can reach:\n");
    for (const orphan of orphans) console.error(`  ${orphan}`);
    console.error("\nGive it a nav entry, add it to a group's `match`, or delete the screen.");
  }
  if (dangling.length > 0) {
    console.error("\nNavigation links that lead nowhere:\n");
    for (const link of dangling) console.error(`  ${link}`);
    console.error(
      "\nEach of these drops the user on the home page. Point it at a real route, " +
        "or remove the entry.",
    );
  }
  process.exit(1);
}

console.log(
  `Routes: all ${routes.length} reachable from the navigation, ` +
    `all ${links.size} navigation links resolve.`,
);
