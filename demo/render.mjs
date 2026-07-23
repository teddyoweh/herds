// Render herds-demo.html to a real mp4 by capturing composited frames over CDP.
// Real-time screencast → timestamped PNGs → ffmpeg (honors holds + transitions).
import CDP from 'chrome-remote-interface';
import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';

const HERE = new URL('.', import.meta.url).pathname;
const HTML = `file://${HERE}herds-demo.html?render=1`;
const FRAMES = `${HERE}frames`;
const W = 2560, H = 1440, FPS = 60;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 9333;

rmSync(FRAMES, { recursive: true, force: true }); mkdirSync(FRAMES, { recursive: true });

console.log('· launching headless Chrome…');
const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  `--window-size=${W},${H}`, '--hide-scrollbars', '--force-device-scale-factor=1',
  '--disable-gpu', '--no-first-run', '--disable-extensions',
  'about:blank',
], { stdio: 'ignore' });

async function connect(retries = 40) {
  for (let i = 0; i < retries; i++) {
    try { return await CDP({ port: PORT }); } catch { await sleep(250); }
  }
  throw new Error('could not connect to Chrome');
}

const client = await connect();
const { Page, Runtime, Emulation } = client;
await Page.enable();
await Emulation.setDeviceMetricsOverride({ width: W, height: H, deviceScaleFactor: 1, mobile: false });

const frames = [];
Page.screencastFrame(async ({ data, metadata, sessionId }) => {
  frames.push({ t: metadata.timestamp, data });
  try { await Page.screencastFrameAck({ sessionId }); } catch {}
});

console.log('· loading film…');
await Page.navigate({ url: HTML });
await Page.loadEventFired();
await sleep(120);

console.log('· recording…');
await Page.startScreencast({ format: 'png', maxWidth: W, maxHeight: H, everyNthFrame: 1 });

// wait until the film signals it's done (with a hard cap)
const start = Date.now();
while (true) {
  const { result } = await Runtime.evaluate({ expression: 'window.__done === true' });
  if (result.value) break;
  if (Date.now() - start > 70000) { console.log('· cap hit'); break; }
  await sleep(150);
}
await sleep(200);
await Page.stopScreencast();
console.log(`· captured ${frames.length} frames over ${((frames.at(-1).t - frames[0].t)).toFixed(1)}s`);

// export beat markers so the score can lock to picture
try {
  const { result } = await Runtime.evaluate({ expression: 'JSON.stringify(window.__marks||{})' });
  writeFileSync(`${HERE}marks.json`, result.value || '{}');
  console.log('· marks:', result.value);
} catch {}

// write frames + a concat list that reproduces exact timing (holds included)
const t0 = frames[0].t;
let list = '';
frames.forEach((f, i) => {
  const name = `f_${String(i).padStart(5, '0')}.png`;
  writeFileSync(`${FRAMES}/${name}`, Buffer.from(f.data, 'base64'));
  const next = frames[i + 1] ? frames[i + 1].t : f.t + 1 / FPS;
  const dur = Math.max(1 / 240, next - f.t);
  list += `file '${name}'\nduration ${dur.toFixed(4)}\n`;
});
list += `file '${`f_${String(frames.length - 1).padStart(5, '0')}.png`}'\n`; // concat needs a trailing file
writeFileSync(`${FRAMES}/list.txt`, list);

await client.close();
chrome.kill();

console.log('· encoding mp4…');
const out = `${HERE}herds-demo.mp4`;
const ff = spawnSync('ffmpeg', [
  '-y', '-f', 'concat', '-safe', '0', '-i', `${FRAMES}/list.txt`,
  '-vf', `fps=${FPS},scale=${W}:${H}:flags=lanczos,format=yuv420p`,
  '-c:v', 'libx264', '-crf', '17', '-preset', 'medium', '-movflags', '+faststart',
  out,
], { stdio: 'inherit' });
if (ff.status !== 0) process.exit(ff.status);
console.log(`✓ ${out}`);
