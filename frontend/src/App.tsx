// Phase 0 walking skeleton: a branded shell that proves the design tokens are
// wired through Tailwind. Real screens arrive from Phase 1 onward.

const subsystems: { name: string; hue: string }[] = [
  { name: "Distribution", hue: "#3B5BDB" },
  { name: "Inventory", hue: "#0891B2" },
  { name: "Retail", hue: "#0D9488" },
  { name: "Insurance", hue: "#7C3AED" },
  { name: "Finance", hue: "#15803D" },
  { name: "People", hue: "#EA580C" },
  { name: "Insights", hue: "#DB2777" },
  { name: "Admin", hue: "#475569" },
];

function App() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 p-8">
      <header className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-brand-600">
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="white" strokeWidth={2}>
            <circle cx="7" cy="12" r="3" />
            <circle cx="17" cy="12" r="3" />
            <path d="M10 12h4" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
            Pharma<span className="text-brand-600">Core</span>
          </h1>
          <p className="text-sm text-ink-500">by Medlink · Phase 0 skeleton</p>
        </div>
      </header>

      <section className="rounded-lg border border-line bg-surface-0 p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">
          Sub-systems
        </h2>
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {subsystems.map((s) => (
            <li key={s.name} className="flex items-center gap-2 text-sm text-ink-700">
              <span
                className="h-5 w-5 rounded-md"
                style={{ backgroundColor: s.hue }}
                aria-hidden
              />
              {s.name}
            </li>
          ))}
        </ul>
      </section>

      <p className="text-sm text-ink-500">
        Design tokens are wired through Tailwind. The API health endpoint is at{" "}
        <code className="font-mono text-ink-700">/health</code>.
      </p>
    </main>
  );
}

export default App;
