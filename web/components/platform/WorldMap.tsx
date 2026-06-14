"use client";

import { MAP_W, MAP_H, MAP_DOTS, MAP_PINS } from "./worldmap";

/** Dotted world map with pulsing "Mac" nodes — the global herd. */
export function WorldMap({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox={`0 0 ${MAP_W} ${MAP_H}`}
      preserveAspectRatio="xMidYMid meet"
      className={className}
      aria-hidden
    >
      {/* land — a field of faint dots */}
      <g className="text-white/[0.11]" fill="currentColor">
        {MAP_DOTS.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={0.3} />
        ))}
      </g>

      {/* nodes — live Macs in the herd */}
      {MAP_PINS.map((p, i) => {
        const bright = i % 3 === 0; // a third glow brighter, on a stagger
        return (
          <g key={p.name} style={{ animationDelay: `${(i % 7) * 0.5}s` }} className="animate-breathe">
            <circle cx={p.x} cy={p.y} r={2.4} className="fill-signal-400/10" />
            <circle cx={p.x} cy={p.y} r={1.3} className="fill-signal-400/25" />
            <circle
              cx={p.x}
              cy={p.y}
              r={bright ? 0.75 : 0.6}
              className={bright ? "fill-signal-300" : "fill-signal-400"}
              style={{ filter: "drop-shadow(0 0 1.4px rgba(52,211,158,0.9))" }}
            />
          </g>
        );
      })}
    </svg>
  );
}
