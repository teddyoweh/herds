"use client";

/** Lightweight, dependency-free SVG charts tuned to the dark, minimal theme.
 *  Stretched horizontally with preserveAspectRatio="none"; strokes kept crisp
 *  via vector-effect="non-scaling-stroke". */

function clock(ms: number): string {
  const d = new Date(ms);
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function ticks(times: number[], n = 4): { i: number; label: string }[] {
  if (times.length < 2) return [];
  const step = (times.length - 1) / (n - 1);
  return Array.from({ length: n }, (_, k) => {
    const i = Math.round(k * step);
    return { i, label: clock(times[i]) };
  });
}

const H = 116;

/** Tiny inline activity sparkline for headers ("N live"). */
export function Sparkline({
  data,
  color = "#34d39e",
  height = 30,
}: {
  data: number[];
  color?: string;
  height?: number;
}) {
  const max = Math.max(1, ...data);
  const n = data.length || 1;
  const bw = 100 / n;
  return (
    <svg viewBox={`0 0 100 ${height}`} height={height} preserveAspectRatio="none" className="w-full">
      {data.map((v, i) => {
        const h = (v / max) * (height - 2);
        return (
          <rect
            key={i}
            x={i * bw + bw * 0.15}
            y={height - h}
            width={bw * 0.7}
            height={Math.max(v ? 1.5 : 1, h)}
            fill={color}
            opacity={v ? 0.85 : 0.12}
          />
        );
      })}
    </svg>
  );
}

/** Radial gauge widget — a donut with the % in the center. */
export function RingGauge({
  value,
  color = "#34d39e",
  size = 116,
  stroke = 9,
  sub,
}: {
  value: number;
  color?: string;
  size?: number;
  stroke?: number;
  sub?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value || 0));
  const dash = (pct / 100) * c;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          style={{ transition: "stroke-dasharray 0.7s ease", filter: `drop-shadow(0 0 6px ${color}55)` }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="tnum text-[26px] font-semibold leading-none tracking-tightest text-white">
          {Math.round(pct)}
          <span className="text-[13px] font-medium text-zinc-500">%</span>
        </span>
        {sub && <span className="mt-1 text-[10px] uppercase tracking-[0.14em] text-zinc-600">{sub}</span>}
      </div>
    </div>
  );
}

export function BarChart({
  data,
  color = "#34d39e",
}: {
  data: { t: number; count: number }[];
  color?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const n = data.length || 1;
  const bw = 1000 / n;
  const xticks = ticks(data.map((d) => d.t));

  return (
    <div>
      <svg viewBox={`0 0 1000 ${H}`} width="100%" height={H} preserveAspectRatio="none" className="overflow-visible">
        <line x1={0} y1={H - 1} x2={1000} y2={H - 1} stroke="rgba(255,255,255,0.06)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        {data.map((d, i) => {
          const h = (d.count / max) * (H - 10);
          return (
            <rect
              key={i}
              x={i * bw + bw * 0.18}
              y={H - h - 1}
              width={bw * 0.64}
              height={Math.max(0, h)}
              rx={1}
              fill={color}
              opacity={d.count ? 0.85 : 0}
            />
          );
        })}
      </svg>
      <Axis ticks={xticks} />
    </div>
  );
}

export function AreaChart({
  points,
  id,
  color = "#34d39e",
  max = 100,
}: {
  points: { t: number; v: number }[];
  id: string;
  color?: string;
  max?: number;
}) {
  const n = points.length;
  const xs = (i: number) => (n <= 1 ? 1000 : (i / (n - 1)) * 1000);
  const ys = (v: number) => H - (Math.min(v, max) / max) * (H - 12) - 4;

  let line = "";
  let area = "";
  if (n === 1) {
    const y = ys(points[0].v);
    line = `M0,${y} L1000,${y}`;
    area = `${line} L1000,${H} L0,${H} Z`;
  } else if (n > 1) {
    line = points.map((p, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(p.v).toFixed(1)}`).join(" ");
    area = `${line} L1000,${H} L0,${H} Z`;
  }
  const xticks = ticks(points.map((p) => p.t));

  return (
    <div>
      <svg viewBox={`0 0 1000 ${H}`} width="100%" height={H} preserveAspectRatio="none" className="overflow-visible">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <line x1={0} y1={ys(max)} x2={1000} y2={ys(max)} stroke="rgba(255,255,255,0.05)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        <line x1={0} y1={ys(max / 2)} x2={1000} y2={ys(max / 2)} stroke="rgba(255,255,255,0.04)" strokeDasharray="3 4" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        {n > 0 && <path d={area} fill={`url(#${id})`} />}
        {n > 0 && <path d={line} fill="none" stroke={color} strokeWidth={1.75} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />}
      </svg>
      <Axis ticks={xticks} />
    </div>
  );
}

function Axis({ ticks }: { ticks: { i: number; label: string }[] }) {
  if (!ticks.length) return <div className="h-4" />;
  return (
    <div className="relative mt-1.5 h-4">
      {ticks.map((t, k) => (
        <span
          key={k}
          className="absolute -translate-x-1/2 font-mono text-[10px] text-zinc-700"
          style={{ left: `${ticks.length > 1 ? (t.i / (ticks[ticks.length - 1].i || 1)) * 100 : 50}%` }}
        >
          {t.label}
        </span>
      ))}
    </div>
  );
}
