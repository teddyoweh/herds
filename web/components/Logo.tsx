/** Herds mark — three connected nodes (a herd of machines) on the signal gradient.
 *  A custom SVG, sized proportionally. Use everywhere instead of an emoji. */
export function Logo({ size = 28, className = "" }: { size?: number; className?: string }) {
  const g = Math.round(size * 0.66);
  return (
    <span
      className={`relative inline-grid shrink-0 place-items-center overflow-hidden bg-gradient-to-br from-signal-400 to-signal-600 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.22)] ${className}`}
      style={{ width: size, height: size, borderRadius: Math.max(4, Math.round(size * 0.28)) }}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" width={g} height={g} fill="none">
        <path
          d="M12 6.3 L6.4 16.3 M12 6.3 L17.6 16.3 M6.4 16.3 L17.6 16.3"
          stroke="white"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.72"
        />
        <circle cx="12" cy="5.9" r="2.55" fill="white" />
        <circle cx="6" cy="16.7" r="2.55" fill="white" />
        <circle cx="18" cy="16.7" r="2.55" fill="white" />
      </svg>
    </span>
  );
}
