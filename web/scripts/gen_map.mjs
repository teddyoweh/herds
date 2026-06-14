// Generate the dotted world-map geometry for the landing hero.
// Run from web/:  node scripts/gen_map.mjs
import fs from "node:fs";
import path from "node:path";

const { default: DottedMap } = await import("dotted-map");

const map = new DottedMap({ height: 52, grid: "diagonal" });
const points = map.getPoints();

const cities = [
  ["San Francisco", 37.77, -122.42], ["New York", 40.71, -74.0], ["Toronto", 43.65, -79.38],
  ["Sao Paulo", -23.55, -46.63], ["London", 51.5, -0.12], ["Paris", 48.85, 2.35], ["Berlin", 52.52, 13.4],
  ["Lagos", 6.52, 3.37], ["Tel Aviv", 32.08, 34.78], ["Bengaluru", 12.97, 77.59], ["Singapore", 1.35, 103.8],
  ["Tokyo", 35.68, 139.7], ["Seoul", 37.56, 126.97], ["Sydney", -33.87, 151.2], ["Amsterdam", 52.37, 4.9],
  ["Austin", 30.27, -97.74], ["Seattle", 47.6, -122.33], ["Dubai", 25.2, 55.27], ["Mumbai", 19.07, 72.87],
  ["Nairobi", -1.29, 36.82], ["Stockholm", 59.33, 18.06], ["Mexico City", 19.43, -99.13], ["Bogota", 4.71, -74.07],
];

const r1 = (n) => Math.round(n * 10) / 10;
const pins = cities.map(([name, lat, lng]) => {
  const p = map.getPin({ lat, lng });
  return { x: r1(p.x), y: r1(p.y), name };
});
const W = Math.ceil(Math.max(...points.map((p) => p.x)));
const H = Math.ceil(Math.max(...points.map((p) => p.y)));
const dots = points.map((p) => [r1(p.x), r1(p.y)]);

const out = path.resolve(import.meta.dirname, "../components/platform/world-grid.ts");
fs.writeFileSync(
  out,
  `// AUTO-GENERATED (scripts/gen_map.mjs) — dotted world map dots + city pins.
export const MAP_W = ${W};
export const MAP_H = ${H};
export const MAP_DOTS: [number, number][] = ${JSON.stringify(dots)};
export const MAP_PINS: { x: number; y: number; name: string }[] = ${JSON.stringify(pins)};
`
);
console.log("dots:", points.length, "pins:", pins.length, "viewBox:", W, "x", H, "->", out);
