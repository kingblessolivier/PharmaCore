import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  Columns3,
  Download,
  Rows3,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

/** A column in the grid. `value` feeds sorting/searching/export; `render` (optional)
 * controls display. Money/number columns should set `align: "right"` + `numeric`. */
export interface Column<T> {
  key: string;
  header: string;
  value?: (row: T) => string | number | null | undefined;
  render?: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  /** Render with tabular numerals so digits line up (money, quantities). */
  numeric?: boolean;
  width?: string;
  /** Exclude from the column picker (e.g. a row-actions column). */
  fixed?: boolean;
  /** Off until someone turns it on.
   *
   * A record can carry thirty fields and a reader wants eight of them — but
   * which eight depends on the job. Shipping the rest hidden rather than
   * omitting them means the data is one click away instead of unavailable,
   * and the default view stays readable. */
  defaultHidden?: boolean;
  sortable?: boolean;
}

type Density = "compact" | "comfortable";
const ROW_H: Record<Density, string> = {
  compact: "py-1.5",
  comfortable: "py-2.5",
};

function cellText(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

/** Enterprise data grid: sort, search, density, column show/hide, sticky header,
 * bulk selection with a bulk-action bar, CSV export, and empty/loading states.
 * Client-side over the rows you pass in — pages keep owning their data fetching. */
export function DataGrid<T>({
  rows,
  columns,
  getRowId,
  loading = false,
  searchPlaceholder = "Search…",
  emptyMessage = "Nothing to show yet.",
  storageKey,
  exportName = "export",
  bulkActions,
  toolbar,
  onRowClick,
  initialDensity = "comfortable",
}: {
  rows: T[];
  columns: Column<T>[];
  getRowId: (row: T) => string | number;
  loading?: boolean;
  searchPlaceholder?: string;
  emptyMessage?: string;
  /** Persist density + hidden columns per user/grid. */
  storageKey?: string;
  exportName?: string;
  bulkActions?: (selected: T[], clear: () => void) => ReactNode;
  toolbar?: ReactNode;
  onRowClick?: (row: T) => void;
  initialDensity?: Density;
}) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<Set<string | number>>(new Set());
  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(columns.filter((c) => c.defaultHidden).map((c) => c.key)),
  );
  const [density, setDensity] = useState<Density>(initialDensity);
  const [colsOpen, setColsOpen] = useState(false);
  const colsRef = useRef<HTMLDivElement>(null);

  // Restore persisted view (density + hidden columns).
  useEffect(() => {
    if (!storageKey) return;
    try {
      const raw = localStorage.getItem(`grid:${storageKey}`);
      if (raw) {
        const v = JSON.parse(raw) as { density?: Density; hidden?: string[] };
        if (v.density) setDensity(v.density);
        if (v.hidden) setHidden(new Set(v.hidden));
      }
    } catch {
      /* ignore malformed state */
    }
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey) return;
    localStorage.setItem(`grid:${storageKey}`, JSON.stringify({ density, hidden: [...hidden] }));
  }, [storageKey, density, hidden]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (colsRef.current && !colsRef.current.contains(e.target as Node)) setColsOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const visibleCols = columns.filter((c) => !hidden.has(c.key));
  const valueOf = (row: T, c: Column<T>) =>
    c.value ? c.value(row) : ((row as Record<string, unknown>)[c.key] as string | number);

  const filtered = useMemo(() => {
    if (!query.trim()) return rows;
    const q = query.toLowerCase();
    return rows.filter((r) =>
      columns.some((c) => cellText(valueOf(r, c)).toLowerCase().includes(q)),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, query, columns]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return filtered;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const av = valueOf(a, col);
      const bv = valueOf(b, col);
      if (av === bv) return 0;
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return cellText(av).localeCompare(cellText(bv), undefined, { numeric: true }) * dir;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, sortKey, sortDir, columns]);

  function toggleSort(c: Column<T>) {
    if (c.sortable === false) return;
    if (sortKey === c.key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(c.key);
      setSortDir("asc");
    }
  }

  const allSelected = sorted.length > 0 && sorted.every((r) => selected.has(getRowId(r)));
  const selectable = Boolean(bulkActions);
  const selectedRows = sorted.filter((r) => selected.has(getRowId(r)));
  const clearSelection = () => setSelected(new Set());

  function exportCsv() {
    const head = visibleCols.map((c) => `"${c.header}"`).join(",");
    const body = sorted
      .map((r) =>
        visibleCols.map((c) => `"${cellText(valueOf(r, c)).replace(/"/g, '""')}"`).join(","),
      )
      .join("\n");
    const blob = new Blob([`${head}\n${body}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${exportName}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex min-w-[200px] flex-1 items-center gap-2 rounded-md border border-line bg-surface-0 px-2.5 py-1.5">
          <Search className="h-4 w-4 shrink-0 text-ink-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full bg-transparent text-sm outline-none placeholder:text-ink-500"
            aria-label="Search rows"
          />
        </div>
        {toolbar}
        <button
          onClick={() => setDensity((d) => (d === "compact" ? "comfortable" : "compact"))}
          className="flex items-center gap-1.5 rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:bg-surface-100"
          title={`Density: ${density}`}
        >
          <Rows3 className="h-3.5 w-3.5" />
          {density === "compact" ? "Compact" : "Comfortable"}
        </button>
        <div className="relative" ref={colsRef}>
          <button
            onClick={() => setColsOpen((o) => !o)}
            className="flex items-center gap-1.5 rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:bg-surface-100"
          >
            <Columns3 className="h-3.5 w-3.5" /> Columns
          </button>
          {colsOpen && (
            <div className="absolute right-0 z-30 mt-1 w-56 rounded-lg border border-line bg-surface-0 p-2 shadow-lg">
              {columns
                .filter((c) => !c.fixed)
                .map((c) => (
                  <label
                    key={c.key}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-ink-700 hover:bg-surface-100"
                  >
                    <input
                      type="checkbox"
                      checked={!hidden.has(c.key)}
                      onChange={() =>
                        setHidden((h) => {
                          const n = new Set(h);
                          if (n.has(c.key)) n.delete(c.key);
                          else n.add(c.key);
                          return n;
                        })
                      }
                      className="h-3.5 w-3.5 accent-brand-600"
                    />
                    {c.header}
                  </label>
                ))}
            </div>
          )}
        </div>
        <button
          onClick={exportCsv}
          className="flex items-center gap-1.5 rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:bg-surface-100"
        >
          <Download className="h-3.5 w-3.5" /> CSV
        </button>
      </div>

      {/* Bulk action bar */}
      {selectable && selectedRows.length > 0 && (
        <div className="flex items-center gap-3 rounded-md border border-brand-600 bg-brand-50/60 px-3 py-2 text-sm">
          <span className="font-medium text-brand-700">{selectedRows.length} selected</span>
          <div className="flex flex-1 items-center gap-2">
            {bulkActions?.(selectedRows, clearSelection)}
          </div>
          <button onClick={clearSelection} className="text-xs text-ink-500 hover:text-ink-900">
            Clear
          </button>
        </div>
      )}

      {/* Grid */}
      <div className="overflow-auto rounded-lg border border-line bg-surface-0">
        <table className="list-grid w-full text-form">
          <thead className="sticky top-0 z-10">
            <tr className="text-left text-micro">
              {selectable && (
                <th className="w-8 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={() =>
                      setSelected(allSelected ? new Set() : new Set(sorted.map(getRowId)))
                    }
                    className="h-3.5 w-3.5 accent-brand-600"
                    aria-label="Select all rows"
                  />
                </th>
              )}
              {visibleCols.map((c) => {
                const active = sortKey === c.key;
                const sortable = c.sortable !== false;
                return (
                  <th
                    key={c.key}
                    style={c.width ? { width: c.width } : undefined}
                    className={`px-3 py-2 font-semibold ${
                      c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : ""
                    }`}
                  >
                    {sortable ? (
                      <button
                        onClick={() => toggleSort(c)}
                        className={`inline-flex items-center gap-1 hover:text-ink-900 ${
                          active ? "text-ink-900" : ""
                        }`}
                      >
                        {c.header}
                        {active ? (
                          sortDir === "asc" ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : (
                            <ArrowDown className="h-3 w-3" />
                          )
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td
                  colSpan={visibleCols.length + (selectable ? 1 : 0)}
                  className="px-3 py-10 text-center text-ink-500"
                >
                  Loading…
                </td>
              </tr>
            )}
            {!loading &&
              sorted.map((row) => {
                const id = getRowId(row);
                const isSel = selected.has(id);
                return (
                  <tr
                    key={id}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={`border-b border-line last:border-0 ${
                      isSel ? "bg-brand-50/40" : "hover:bg-surface-100"
                    } ${onRowClick ? "cursor-pointer" : ""}`}
                  >
                    {selectable && (
                      <td className={`px-3 ${ROW_H[density]}`} onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSel}
                          onChange={() =>
                            setSelected((s) => {
                              const n = new Set(s);
                              if (n.has(id)) n.delete(id);
                              else n.add(id);
                              return n;
                            })
                          }
                          className="h-3.5 w-3.5 accent-brand-600"
                          aria-label={`Select row ${id}`}
                        />
                      </td>
                    )}
                    {visibleCols.map((c) => (
                      <td
                        key={c.key}
                        className={`px-3 ${ROW_H[density]} ${
                          c.align === "right"
                            ? "text-right"
                            : c.align === "center"
                              ? "text-center"
                              : ""
                        } ${c.numeric ? "tabular-nums" : ""}`}
                      >
                        {c.render ? c.render(row) : cellText(valueOf(row, c))}
                      </td>
                    ))}
                  </tr>
                );
              })}
            {!loading && sorted.length === 0 && (
              <tr>
                <td
                  colSpan={visibleCols.length + (selectable ? 1 : 0)}
                  className="px-3 py-10 text-center text-ink-500"
                >
                  {query ? `No rows match “${query}”.` : emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer count */}
      {!loading && (
        <div className="px-1 text-xs text-ink-500">
          {sorted.length} {sorted.length === 1 ? "row" : "rows"}
          {query && rows.length !== sorted.length ? ` (filtered from ${rows.length})` : ""}
        </div>
      )}
    </div>
  );
}
