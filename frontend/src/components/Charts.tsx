/** Chart primitives — inline SVG, no chart library, light/dark aware.
 *
 * Every chart here follows one method: the data's job picks the form, then the
 * form picks the colour job (categorical for identity, sequential for magnitude,
 * diverging for polarity, status for state). The palette below is validated —
 * worst adjacent CVD ΔE 9.1 light / 8.4 dark, normal-vision ΔE 19.6 / 19.3.
 *
 * Two consequences you will see repeated in the code and should not "tidy away":
 *
 * - Three light-mode hues sit under 3:1 against the light surface, so every mark
 *   that uses them carries a **visible direct label**. That is the relief rule,
 *   not decoration.
 * - Marks are separated by a **2px gap in the surface colour**, never by a stroke.
 *   A border is ink that isn't data.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/* -------------------------------------------------------------------------- */
/*  Sizing                                                                     */
/* -------------------------------------------------------------------------- */

/** The chart's own width in real pixels.
 *
 * Every chart here used to draw into a fixed 640-unit viewBox and then stretch
 * it with `w-full`. A viewBox scales *both* axes, so on a 1560px screen the
 * whole drawing — 10px axis text, 2px strokes, 30px bar rows — came out 2.4×
 * larger than designed. That is why the charts read as oversized on a wide
 * monitor and looked right on a laptop.
 *
 * Measuring the container and drawing at that width instead makes one SVG unit
 * exactly one CSS pixel, so type and stroke weights stay put at any size and
 * only the plot gets wider — which is the thing that should get wider. */
function useChartWidth(fallback = 640) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);

  useEffect(() => {
    const element = ref.current;
    if (element === null || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const next = Math.round(entries[0].contentRect.width);
      if (next > 0) setWidth(next);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return [ref, width] as const;
}

/* -------------------------------------------------------------------------- */
/*  Palette                                                                    */
/* -------------------------------------------------------------------------- */

/** Categorical slots, in fixed order. Never cycled, never generated. */
export const SERIES = ["s1", "s2", "s3", "s4", "s5", "s6"] as const;
export type SeriesSlot = (typeof SERIES)[number];

/** Ordinal steps for a magnitude ramp. Starts at step 250 so the lightest step
 *  still clears 2:1 on the light surface. */
const RAMP_LIGHT = ["#86b6ef", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab"];
const RAMP_DARK = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"];

/** Root wrapper. Owns the theme-swapped custom properties every chart reads. */
export function VizRoot({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`viz-root ${className}`}>
      <style>{`
.viz-root{
  color-scheme:light;
  --viz-surface:#fcfcfb; --viz-ink:#0b0b0b; --viz-ink-2:#52514e; --viz-muted:#898781;
  --viz-grid:#e1e0d9; --viz-axis:#c3c2b7;
  --viz-s1:#2a78d6; --viz-s2:#eb6834; --viz-s3:#1baf7a;
  --viz-s4:#eda100; --viz-s5:#e87ba4; --viz-s6:#008300;
  --viz-pos:#2a78d6; --viz-neg:#e34948; --viz-mid:#f0efec;
  --viz-good:#0ca30c; --viz-warn:#fab219; --viz-serious:#ec835a; --viz-critical:#d03b3b;
  --viz-r1:${RAMP_LIGHT[0]}; --viz-r2:${RAMP_LIGHT[1]}; --viz-r3:${RAMP_LIGHT[2]};
  --viz-r4:${RAMP_LIGHT[3]}; --viz-r5:${RAMP_LIGHT[4]}; --viz-r6:${RAMP_LIGHT[5]};
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])) .viz-root{
    color-scheme:dark;
    --viz-surface:#1a1a19; --viz-ink:#ffffff; --viz-ink-2:#c3c2b7; --viz-muted:#898781;
    --viz-grid:#2c2c2a; --viz-axis:#383835;
    --viz-s1:#3987e5; --viz-s2:#d95926; --viz-s3:#199e70;
    --viz-s4:#c98500; --viz-s5:#d55181; --viz-s6:#008300;
    --viz-pos:#3987e5; --viz-neg:#e66767; --viz-mid:#383835;
    --viz-r1:${RAMP_DARK[0]}; --viz-r2:${RAMP_DARK[1]}; --viz-r3:${RAMP_DARK[2]};
    --viz-r4:${RAMP_DARK[3]}; --viz-r5:${RAMP_DARK[4]}; --viz-r6:${RAMP_DARK[5]};
  }
}
:root[data-theme="dark"] .viz-root{
  color-scheme:dark;
  --viz-surface:#1a1a19; --viz-ink:#ffffff; --viz-ink-2:#c3c2b7; --viz-muted:#898781;
  --viz-grid:#2c2c2a; --viz-axis:#383835;
  --viz-s1:#3987e5; --viz-s2:#d95926; --viz-s3:#199e70;
  --viz-s4:#c98500; --viz-s5:#d55181; --viz-s6:#008300;
  --viz-pos:#3987e5; --viz-neg:#e66767; --viz-mid:#383835;
  --viz-r1:${RAMP_DARK[0]}; --viz-r2:${RAMP_DARK[1]}; --viz-r3:${RAMP_DARK[2]};
  --viz-r4:${RAMP_DARK[3]}; --viz-r5:${RAMP_DARK[4]}; --viz-r6:${RAMP_DARK[5]};
}
      `}</style>
      {children}
    </div>
  );
}

const slotVar = (i: number) => `var(--viz-${SERIES[i % SERIES.length]})`;
const rampVar = (i: number, of: number) => {
  // Map an ordinal position onto the 6-step ramp, darkest = highest magnitude.
  const step = of <= 1 ? 5 : Math.round((i / (of - 1)) * 5) + 1;
  return `var(--viz-r${Math.min(6, Math.max(1, step))})`;
};

const fmt = (n: number) =>
  Math.abs(n) >= 1_000_000
    ? `${(n / 1_000_000).toFixed(1)}M`
    : Math.abs(n) >= 1_000
      ? `${(n / 1_000).toFixed(0)}k`
      : n.toFixed(0);

/* -------------------------------------------------------------------------- */
/*  Shared chrome                                                              */
/* -------------------------------------------------------------------------- */

export function ChartFrame({
  title,
  subtitle,
  legend,
  children,
  action,
}: {
  title: string;
  subtitle?: string;
  legend?: { label: string; color: string }[];
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <figure className="m-0 rounded-lg border border-line bg-surface-0 p-4">
      <figcaption className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-ink-500">{subtitle}</p>}
        </div>
        {action}
      </figcaption>
      {/* A legend is always present for two or more series — identity is never
          carried by colour alone. One series needs none; the title names it. */}
      {legend && legend.length >= 2 && (
        <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1">
          {legend.map((l) => (
            <li key={l.label} className="flex items-center gap-1.5 text-xs text-ink-600">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: l.color }}
              />
              {l.label}
            </li>
          ))}
        </ul>
      )}
      {children}
    </figure>
  );
}

function Tip({ x, y, lines }: { x: number; y: number; lines: string[] }) {
  const w = Math.max(...lines.map((l) => l.length)) * 6.2 + 16;
  const h = lines.length * 15 + 10;
  return (
    <g transform={`translate(${x},${y})`} pointerEvents="none">
      <rect x={8} y={-h / 2} width={w} height={h} rx={5} fill="var(--viz-ink)" opacity={0.92} />
      {lines.map((line, i) => (
        <text key={i} x={16} y={-h / 2 + 16 + i * 15} fontSize={11} fill="var(--viz-surface)">
          {line}
        </text>
      ))}
    </g>
  );
}

export function EmptyChart({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dashed border-line py-10 text-center text-sm text-ink-500">
      {message}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Line trend — distinct series over time (categorical)                       */
/* -------------------------------------------------------------------------- */

export interface TrendPoint {
  label: string;
  values: number[];
}

export function LineTrend({
  points,
  seriesNames,
  height = 200,
  valueFormat = fmt,
}: {
  points: TrendPoint[];
  seriesNames: string[];
  height?: number;
  valueFormat?: (n: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useChartWidth();
  if (points.length === 0) return <EmptyChart message="No data in this period." />;

  const H = height;

  const all = points.flatMap((p) => p.values);
  const max = Math.max(...all, 0);
  const min = Math.min(...all, 0);
  const span = max - min || 1;
  const ticks = [min, min + span / 2, max];

  // Padding sized to the text that has to fit in it. It used to be fixed at
  // 46/56, which is fine for "1.2k" and clips "RWF 26,400" — and because the
  // SVG scales to its container, a wide screen made the clipping worse rather
  // than better. 6.2 units per character is close enough at these sizes.
  const CH = 6.2;
  const widest = (labels: string[]) => Math.max(0, ...labels.map((l) => l.length)) * CH;
  const last = points[points.length - 1];
  const pad = {
    top: 12,
    right: Math.min(
      190,
      Math.max(56, widest(seriesNames.map((_, s) => valueFormat(last.values[s] ?? 0))) + 18),
    ),
    bottom: 26,
    left: Math.max(46, widest(ticks.map(valueFormat)) + 16),
  };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const x = (i: number) =>
    pad.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => pad.top + innerH - ((v - min) / span) * innerH;

  return (
    <div className="relative" ref={box}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        role="img"
        aria-label={`Trend of ${seriesNames.join(" and ")}`}
        onMouseLeave={() => setHover(null)}
      >
        {/* Recessive hairline grid — solid, never dashed. */}
        {ticks.map((t, i) => (
          <g key={i}>
            <line
              x1={pad.left}
              x2={W - pad.right}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--viz-grid)"
              strokeWidth={1}
            />
            <text
              x={pad.left - 8}
              y={y(t) + 4}
              fontSize={10}
              textAnchor="end"
              fill="var(--viz-muted)"
            >
              {valueFormat(t)}
            </text>
          </g>
        ))}

        {seriesNames.map((_, s) => {
          const d = points
            .map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.values[s] ?? 0)}`)
            .join(" ");
          return (
            <path
              key={s}
              d={d}
              fill="none"
              stroke={slotVar(s)}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          );
        })}

        {/* End markers + direct labels. Labelling the endpoint only is what keeps
            direct labels working; a number on every point is noise. */}
        {seriesNames.map((name, s) => {
          const last = points[points.length - 1];
          const cx = x(points.length - 1);
          const cy = y(last.values[s] ?? 0);
          return (
            <g key={name}>
              <circle
                cx={cx}
                cy={cy}
                r={4}
                fill={slotVar(s === 0 ? 0 : 2)}
                stroke="var(--viz-surface)"
                strokeWidth={2}
              />
              <text x={cx + 9} y={cy + 4} fontSize={11} fill="var(--viz-ink-2)">
                {valueFormat(last.values[s] ?? 0)}
              </text>
            </g>
          );
        })}

        {/* Thinned to what actually fits. Fourteen dates across 600px collide
            into an unreadable smear — the axis then costs space and tells you
            nothing. Showing every nth keeps the ends, which are the two a
            reader actually looks for. */}
        {points.map((p, i) => {
          const widest = Math.max(...points.map((q) => q.label.length)) * 6.2 + 10;
          const every = Math.max(1, Math.ceil(widest / (innerW / Math.max(1, points.length - 1))));
          const isEnd = i === 0 || i === points.length - 1;
          if (!isEnd && i % every !== 0) return null;
          // Never let a thinned label sit on top of the last one.
          if (!isEnd && points.length - 1 - i < every / 2) return null;
          return (
            <text
              key={p.label}
              x={x(i)}
              y={H - 8}
              fontSize={10}
              textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
              fill="var(--viz-muted)"
            >
              {p.label}
            </text>
          );
        })}

        {/* Crosshair + tooltip: an SVG chart is interactive by default. */}
        {points.map((p, i) => (
          <rect
            key={`hit-${p.label}`}
            x={x(i) - innerW / Math.max(1, points.length) / 2}
            y={pad.top}
            width={innerW / Math.max(1, points.length)}
            height={innerH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
        {hover !== null && (
          <>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={pad.top}
              y2={pad.top + innerH}
              stroke="var(--viz-axis)"
              strokeWidth={1}
            />
            <Tip
              x={Math.min(x(hover), W - 190)}
              y={pad.top + innerH / 2}
              lines={[
                points[hover].label,
                ...seriesNames.map((n, s) => `${n}: ${valueFormat(points[hover].values[s] ?? 0)}`),
              ]}
            />
          </>
        )}
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Donut — part-to-whole across several classes (categorical)                 */
/* -------------------------------------------------------------------------- */

export interface Slice {
  label: string;
  value: number;
}

export function Donut({
  slices,
  centreLabel,
  centreValue,
  valueFormat = fmt,
}: {
  slices: Slice[];
  centreLabel?: string;
  centreValue?: string;
  valueFormat?: (n: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const clean = slices.filter((s) => s.value > 0);
  const total = clean.reduce((sum, s) => sum + s.value, 0);
  if (total <= 0) return <EmptyChart message="Nothing to break down in this period." />;

  // Past six classes colour stops discriminating — fold the tail into "Other"
  // rather than generating a seventh hue nobody can tell from the first.
  const sorted = [...clean].sort((a, b) => b.value - a.value);
  const shown = sorted.slice(0, 5);
  const rest = sorted.slice(5);
  if (rest.length) {
    shown.push({ label: "Other", value: rest.reduce((s, r) => s + r.value, 0) });
  }

  const size = 220;
  const c = size / 2;
  const rOuter = 92;
  const rInner = 58;
  const GAP = 2; // surface gap, in px of arc — white does the separating

  let angle = -Math.PI / 2;
  const arcs = shown.map((s, i) => {
    const sweep = (s.value / total) * Math.PI * 2;
    const gapAngle = shown.length > 1 ? GAP / rOuter : 0;
    const a0 = angle + gapAngle / 2;
    const a1 = angle + sweep - gapAngle / 2;
    angle += sweep;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p = (r: number, a: number) => `${c + r * Math.cos(a)},${c + r * Math.sin(a)}`;
    const d = [
      `M${p(rOuter, a0)}`,
      `A${rOuter},${rOuter} 0 ${large} 1 ${p(rOuter, a1)}`,
      `L${p(rInner, a1)}`,
      `A${rInner},${rInner} 0 ${large} 0 ${p(rInner, a0)}`,
      "Z",
    ].join(" ");
    const mid = (a0 + a1) / 2;
    return {
      ...s,
      d,
      i,
      pct: (s.value / total) * 100,
      labelX: c + (rOuter + 14) * Math.cos(mid),
      labelY: c + (rOuter + 14) * Math.sin(mid),
      anchor: Math.cos(mid) >= 0 ? "start" : "end",
    };
  });

  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        role="img"
        aria-label="Breakdown"
      >
        {arcs.map((a) => (
          <path
            key={a.label}
            d={a.d}
            fill={slotVar(a.i)}
            opacity={hover === null || hover === a.i ? 1 : 0.45}
            onMouseEnter={() => setHover(a.i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
        {centreValue && (
          <>
            <text
              x={c}
              y={c - 2}
              textAnchor="middle"
              /* Fit the figure to the hole. "RWF 1,713,148" at a fixed 20px is
                 wider than the 116px opening and spilled over the ring. */
              fontSize={Math.min(20, Math.max(11, (rInner * 2 - 14) / (centreValue.length * 0.58)))}
              fontWeight={600}
              fill="var(--viz-ink)"
            >
              {centreValue}
            </text>
            <text x={c} y={c + 16} textAnchor="middle" fontSize={10} fill="var(--viz-muted)">
              {centreLabel}
            </text>
          </>
        )}
      </svg>

      {/* Direct labels live in the list, not on the arcs — arc labels collide the
          moment two slices are thin. Percentages make the part-to-whole readable
          without measuring angles by eye. */}
      <ul className="min-w-[190px] flex-1">
        {arcs.map((a) => (
          <li
            key={a.label}
            onMouseEnter={() => setHover(a.i)}
            onMouseLeave={() => setHover(null)}
            className={`flex items-center justify-between gap-3 border-b border-line py-1.5 text-sm last:border-0 ${
              hover === a.i ? "bg-surface-50" : ""
            }`}
          >
            <span className="flex min-w-0 items-center gap-2">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ background: slotVar(a.i) }}
              />
              <span className="truncate text-ink-700">{a.label}</span>
            </span>
            <span className="shrink-0 tabular-nums text-ink-900">
              {valueFormat(a.value)}
              <span className="ml-1.5 text-xs text-ink-500">{a.pct.toFixed(1)}%</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Bars — compare magnitude (sequential, one hue)                             */
/* -------------------------------------------------------------------------- */

export interface BarDatum {
  label: string;
  value: number;
  /** Optional secondary read shown in the tooltip, e.g. a margin %. */
  note?: string;
  /** Force a status colour (expiry risk, breach). Otherwise the ramp is used. */
  tone?: "good" | "warning" | "serious" | "critical";
}

export function BarChart({
  data,
  height,
  valueFormat = fmt,
  ordinalRamp = false,
}: {
  data: BarDatum[];
  height?: number;
  valueFormat?: (n: number) => string;
  /** Colour by position (ordered severity) rather than one flat hue. */
  ordinalRamp?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useChartWidth();
  if (data.length === 0) return <EmptyChart message="Nothing to compare yet." />;

  const rowH = 30;
  const H = height ?? data.length * rowH + 12;
  const labelW = 150;
  const valueW = 74;
  const trackW = W - labelW - valueW;
  const max = Math.max(...data.map((d) => Math.abs(d.value)), 1);

  return (
    <div ref={box}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label="Comparison">
        {data.map((d, i) => {
          const w = Math.max(2, (Math.abs(d.value) / max) * trackW);
          const y = i * rowH + 6;
          const fill = d.tone
            ? `var(--viz-${d.tone === "good" ? "good" : d.tone === "warning" ? "warn" : d.tone})`
            : ordinalRamp
              ? rampVar(i, data.length)
              : "var(--viz-s1)";
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={0} y={y - 4} width={W} height={rowH - 4} fill="transparent" />
              <text x={0} y={y + 14} fontSize={11} fill="var(--viz-ink-2)">
                {d.label.length > 24 ? `${d.label.slice(0, 23)}…` : d.label}
              </text>
              {/* 4px rounded data-end, square at the baseline; capped thickness. */}
              <path
                d={`M${labelW},${y} h${Math.max(0, w - 4)} a4,4 0 0 1 4,4 v${18 - 8} a4,4 0 0 1 -4,4 h${-Math.max(0, w - 4)} z`}
                fill={fill}
                opacity={hover === null || hover === i ? 1 : 0.5}
              />
              <text
                x={labelW + w + 8}
                y={y + 14}
                fontSize={11}
                fill="var(--viz-ink)"
                className="tabular-nums"
              >
                {valueFormat(d.value)}
              </text>
            </g>
          );
        })}
        {hover !== null && data[hover].note && (
          <Tip x={labelW} y={hover * rowH + 20} lines={[data[hover].label, data[hover].note!]} />
        )}
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Waterfall — polarity: what adds days, what gives them back (diverging)     */
/* -------------------------------------------------------------------------- */

export interface WaterfallStep {
  label: string;
  value: number;
  isTotal?: boolean;
}

export function Waterfall({ steps, unit = "days" }: { steps: WaterfallStep[]; unit?: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useChartWidth();
  if (steps.length === 0) return <EmptyChart message="No cycle to show." />;

  const H = 210;
  const pad = { top: 16, bottom: 34, left: 8, right: 8 };
  const innerH = H - pad.top - pad.bottom;
  const slot = (W - pad.left - pad.right) / steps.length;
  const barW = Math.min(24, slot * 0.5);

  let running = 0;
  const bars = steps.map((s) => {
    const from = s.isTotal ? 0 : running;
    const to = s.isTotal ? s.value : running + s.value;
    if (!s.isTotal) running += s.value;
    return { ...s, from, to };
  });

  const values = bars.flatMap((b) => [b.from, b.to, 0]);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const y = (v: number) => pad.top + innerH - ((v - min) / span) * innerH;

  return (
    <div ref={box}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        role="img"
        aria-label={`Waterfall in ${unit}`}
      >
        <line
          x1={pad.left}
          x2={W - pad.right}
          y1={y(0)}
          y2={y(0)}
          stroke="var(--viz-axis)"
          strokeWidth={1}
        />
        {bars.map((b, i) => {
          const cx = pad.left + slot * i + slot / 2;
          const top = y(Math.max(b.from, b.to));
          const h = Math.max(3, Math.abs(y(b.to) - y(b.from)));
          const fill = b.isTotal
            ? "var(--viz-ink-2)"
            : b.value >= 0
              ? "var(--viz-pos)"
              : "var(--viz-neg)";
          return (
            <g key={b.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={cx - slot / 2} y={pad.top} width={slot} height={innerH} fill="transparent" />
              <rect
                x={cx - barW / 2}
                y={top}
                width={barW}
                height={h}
                rx={4}
                fill={fill}
                opacity={hover === null || hover === i ? 1 : 0.5}
              />
              <text
                x={cx}
                y={top - 6}
                fontSize={11}
                textAnchor="middle"
                fill="var(--viz-ink)"
                className="tabular-nums"
              >
                {b.value >= 0 && !b.isTotal ? "+" : ""}
                {b.value.toFixed(0)}
              </text>
              <text x={cx} y={H - 18} fontSize={10} textAnchor="middle" fill="var(--viz-muted)">
                {b.label}
              </text>
            </g>
          );
        })}
        <text x={W / 2} y={H - 4} fontSize={9} textAnchor="middle" fill="var(--viz-muted)">
          {unit}
        </text>
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Meter — one ratio against a limit                                          */
/* -------------------------------------------------------------------------- */

export function Meter({
  value,
  target,
  label,
  caption,
  format = (n: number) => n.toFixed(1),
}: {
  value: number;
  target: number;
  label: string;
  caption?: string;
  format?: (n: number) => string;
}) {
  const id = useId();
  const pct = target > 0 ? Math.min(150, (value / target) * 100) : 0;
  const tone =
    pct >= 100 ? "var(--viz-good)" : pct >= 70 ? "var(--viz-warn)" : "var(--viz-critical)";
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-ink-600">{label}</span>
        <span className="tabular-nums text-sm font-semibold text-ink-900">{format(value)}</span>
      </div>
      <div
        className="mt-1 h-2 overflow-hidden rounded-full"
        style={{ background: "var(--viz-mid)" }}
        role="meter"
        aria-labelledby={id}
        aria-valuenow={value}
        aria-valuemax={target}
      >
        <div className="h-full" style={{ width: `${Math.min(100, pct)}%`, background: tone }} />
      </div>
      {caption && (
        <p id={id} className="mt-1 text-[11px] text-ink-500">
          {caption}
        </p>
      )}
    </div>
  );
}
