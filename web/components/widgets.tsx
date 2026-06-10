"use client";

/** Bespoke, compact metric widgets — iOS-Weather-grade visualizations tuned to
 *  the dark theme. Each metric gets its own crafted treatment, not a generic chart. */

const clamp = (v: number) => Math.max(0, Math.min(100, v || 0));

function Head({ icon, title, tint }: { icon: React.ReactNode; title: string; tint: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="grid h-[18px] w-[18px] place-items-center" style={{ color: tint }}>{icon}</span>
      <span className="text-[12px] font-medium text-zinc-400">{title}</span>
    </div>
  );
}

/* ---- Memory: a tank that fills with liquid (Humidity widget) ------------- */
export function LiquidFill({ value, label, tint = "#2dd4bf" }: { value: number; label: string; tint?: string }) {
  const pct = clamp(value);
  return (
    <div className="surface relative h-full min-h-[156px] overflow-hidden">
      {/* liquid */}
      <div className="absolute inset-x-0 bottom-0 transition-[height] duration-700 ease-out" style={{ height: `${pct}%` }}>
        <svg viewBox="0 0 100 10" preserveAspectRatio="none" className="absolute -top-[9px] left-0 h-[10px] w-full" style={{ color: tint }}>
          <path d="M0,5 Q25,0 50,5 T100,5 V10 H0 Z" fill="currentColor" opacity={0.55} />
        </svg>
        <div className="h-full w-full" style={{ background: `linear-gradient(180deg, ${tint}cc, ${tint}55)` }} />
      </div>
      {/* content */}
      <div className="relative flex h-full flex-col p-4">
        <Head tint={tint} title="Memory" icon={<DropIcon />} />
        <div className="mt-auto">
          <div className="tnum text-[30px] font-semibold leading-none tracking-tightest text-white">{pct}<span className="text-[16px]">%</span></div>
          <div className="mt-1.5 text-[12px] text-white/75">{label}</div>
        </div>
      </div>
    </div>
  );
}

/* ---- CPU: a semicircle gauge with a needle (Pressure widget) ------------- */
export function GaugeNeedle({ value, sub, title = "CPU", color, icon }: { value: number; sub?: string; title?: string; color?: string; icon?: React.ReactNode }) {
  const pct = clamp(value);
  const cx = 60, cy = 56, r = 45;
  const pt = (deg: number) => [cx + r * Math.cos((deg * Math.PI) / 180), cy - r * Math.sin((deg * Math.PI) / 180)] as const;
  const arc = (a: number, b: number) => {
    const [x1, y1] = pt(a), [x2, y2] = pt(b);
    return `M${x1.toFixed(1)},${y1.toFixed(1)} A${r},${r} 0 0 ${a > b ? 1 : 0} ${x2.toFixed(1)},${y2.toFixed(1)}`;
  };
  const theta = 180 - (pct / 100) * 180;
  const [nx, ny] = pt(theta);
  return (
    <div className="surface flex h-full min-h-[156px] flex-col p-4">
      <Head tint={color ?? "#34d39e"} title={title} icon={icon ?? <GaugeIcon />} />
      <div className="relative grid flex-1 place-items-center">
        <svg viewBox="0 0 120 68" className="w-[160px] overflow-visible">
          <defs>
            <linearGradient id="gaugegrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#34d39e" />
              <stop offset="62%" stopColor="#fbbf24" />
              <stop offset="100%" stopColor="#fb7185" />
            </linearGradient>
          </defs>
          <path d={arc(180, 0)} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={9} strokeLinecap="round" />
          <path d={arc(180, theta)} fill="none" stroke={color ?? "url(#gaugegrad)"} strokeWidth={9} strokeLinecap="round" style={{ transition: "all 0.7s ease" }} />
          <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="white" strokeWidth={2.2} strokeLinecap="round" style={{ transition: "all 0.7s ease" }} />
          <circle cx={cx} cy={cy} r={3.4} fill="white" />
        </svg>
        <div className="absolute bottom-0 flex flex-col items-center">
          <span className="tnum text-[22px] font-semibold leading-none tracking-tightest text-white">
            {pct}<span className="text-[12px] text-zinc-500">%</span>
          </span>
          {sub && <span className="mt-1 text-[10px] uppercase tracking-[0.14em] text-zinc-600">{sub}</span>}
        </div>
      </div>
    </div>
  );
}

/* ---- A compact inline gauge for cards (no surface) ----------------------- */
export function MiniGauge({ value, label = "CPU" }: { value: number; label?: string }) {
  const pct = clamp(value);
  const col = pct < 60 ? "#34d39e" : pct < 85 ? "#fbbf24" : "#fb7185";
  const cx = 33, cy = 30, r = 25;
  const pt = (deg: number) => [cx + r * Math.cos((deg * Math.PI) / 180), cy - r * Math.sin((deg * Math.PI) / 180)] as const;
  const arc = (a: number, b: number) => {
    const [x1, y1] = pt(a), [x2, y2] = pt(b);
    return `M${x1.toFixed(1)},${y1.toFixed(1)} A${r},${r} 0 0 ${a > b ? 1 : 0} ${x2.toFixed(1)},${y2.toFixed(1)}`;
  };
  const theta = 180 - (pct / 100) * 180;
  const [nx, ny] = pt(theta);
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 66 34" width="58" className="overflow-visible">
        <path d={arc(180, 0)} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={6} strokeLinecap="round" />
        <path d={arc(180, theta)} fill="none" stroke={col} strokeWidth={6} strokeLinecap="round" style={{ transition: "all 0.7s ease" }} />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="white" strokeWidth={1.8} strokeLinecap="round" style={{ transition: "all 0.7s ease" }} />
        <circle cx={cx} cy={cy} r={2.6} fill="white" />
      </svg>
      <div className="leading-none">
        <div className="text-[9px] uppercase tracking-[0.14em] text-zinc-600">{label}</div>
        <div className="tnum mt-1 text-[14px] font-semibold text-white">
          {pct}<span className="text-[10px] text-zinc-500">%</span>
        </div>
      </div>
    </div>
  );
}

/* ---- Load: a number over a gradient track with a knob (UV Index) --------- */
export function GradientSlider({ value, decimals = 1, max = 10, label, title = "Load" }: { value: number; decimals?: number; max?: number; label: string; title?: string }) {
  const p = Math.max(0, Math.min(1, (value || 0) / max));
  return (
    <div className="surface flex h-full min-h-[156px] flex-col p-4">
      <Head tint="#a78bfa" title={title} icon={<BoltIcon />} />
      <div className="mt-3">
        <div className="tnum text-[28px] font-semibold leading-none tracking-tightest text-white">{value.toFixed(decimals)}</div>
        <div className="mt-1.5 text-[12px] text-zinc-500">{label}</div>
      </div>
      <div className="relative mt-auto pt-3">
        <div className="h-2 w-full rounded-full" style={{ background: "linear-gradient(90deg,#34d39e,#fbbf24,#fb7185)" }} />
        <div
          className="absolute top-[12px] h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-[0_1px_4px_rgba(0,0,0,0.5)] ring-[3px] ring-ink-900"
          style={{ left: `${p * 100}%`, transition: "left 0.7s ease" }}
        />
      </div>
    </div>
  );
}

/* ---- A line with the current point highlighted + time labels (Temperature) */
export function SpotLine({ points, tint = "#fb923c", title, icon, unit = "%" }: { points: { t: number; v: number }[]; tint?: string; title: string; icon?: React.ReactNode; unit?: string }) {
  const n = points.length;
  const max = Math.max(1, ...points.map((p) => p.v));
  const xs = (i: number) => (n <= 1 ? 100 : (i / (n - 1)) * 100);
  const ys = (v: number) => 40 - (v / (max * 1.15)) * 32 - 4;
  const line = points.map((p, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(p.v).toFixed(1)}`).join(" ");
  const last = points[n - 1];
  const t = (ms: number) => { const d = new Date(ms); return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`; };
  const labelIdx = [0, Math.floor(n / 2), n - 1].filter((v, i, a) => a.indexOf(v) === i);
  return (
    <div className="surface flex h-full min-h-[156px] flex-col p-4">
      <div className="flex items-center justify-between">
        <Head tint={tint} title={title} icon={icon ?? <PulseIcon />} />
        <span className="tnum text-[15px] font-semibold text-white">{last ? Math.round(last.v) : 0}{unit}</span>
      </div>
      <div className="relative mt-3 flex-1">
        <svg viewBox="0 0 100 44" preserveAspectRatio="none" className="h-full w-full overflow-visible">
          {n > 1 && <path d={line} fill="none" stroke={tint} strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />}
          {last && (
            <>
              <circle cx={xs(n - 1)} cy={ys(last.v)} r={4.5} fill={tint} vectorEffect="non-scaling-stroke" />
              <circle cx={xs(n - 1)} cy={ys(last.v)} r={4.5} fill="none" stroke={tint} strokeOpacity={0.3} strokeWidth={6} vectorEffect="non-scaling-stroke" />
            </>
          )}
        </svg>
      </div>
      <div className="mt-2 flex justify-between font-mono text-[10px] text-zinc-700">
        {labelIdx.map((i) => <span key={i}>{points[i] ? t(points[i].t) : ""}</span>)}
      </div>
    </div>
  );
}

/* ---- tiny inline icons --------------------------------------------------- */
function DropIcon() {
  return <svg viewBox="0 0 16 16" width="15" height="15" fill="none"><path d="M8 2C8 2 3.5 7 3.5 10.2A4.5 4.5 0 0 0 12.5 10.2C12.5 7 8 2 8 2Z" fill="currentColor" /></svg>;
}
function GaugeIcon() {
  return <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2.5 12a5.5 5.5 0 1 1 11 0" strokeLinecap="round" /><path d="M8 12l3-3.5" strokeLinecap="round" /></svg>;
}
function BoltIcon() {
  return <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor"><path d="M9 1L3 9h4l-1 6 6-8H8l1-6Z" /></svg>;
}
function PulseIcon() {
  return <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M1 8h3l2-5 3 10 2-5h4" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
