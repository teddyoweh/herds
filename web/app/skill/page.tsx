"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Logo } from "@/components/Logo";

/* ---- tiny markdown renderer (just the constructs skill.md uses) ---------- */

function Inline({ text }: { text: string }) {
  const out: React.ReactNode[] = [];
  const re = /(`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*)/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("`")) out.push(<code key={k++} className="rounded bg-white/[0.07] px-1.5 py-0.5 font-mono text-[0.86em] text-signal-300">{t.slice(1, -1)}</code>);
    else if (t.startsWith("**")) out.push(<strong key={k++} className="font-semibold text-zinc-100">{t.slice(2, -2)}</strong>);
    else { const lm = /\[([^\]]+)\]\(([^)]+)\)/.exec(t)!; out.push(<a key={k++} href={lm[2]} className="text-signal-400 underline decoration-signal-500/40 underline-offset-2 hover:text-signal-300">{lm[1]}</a>); }
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="surface group relative my-5 overflow-hidden">
      <div className="flex items-center gap-2 bg-white/[0.025] px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <button
          onClick={() => { navigator.clipboard?.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1300); }}
          className={`ml-auto text-[11px] ${copied ? "text-signal-400" : "text-zinc-600 hover:text-zinc-300"}`}
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-x-auto px-5 py-4 font-mono text-[12.5px] leading-[1.7] text-zinc-300">{code}</pre>
    </div>
  );
}

function Markdown({ body }: { body: string }) {
  const blocks: React.ReactNode[] = [];
  const lines = body.split("\n");
  let i = 0, k = 0, list: string[] = [];
  const flush = () => { if (list.length) { blocks.push(<ul key={k++} className="my-4 space-y-2 pl-1">{list.map((li, j) => <li key={j} className="flex gap-2.5 text-[15px] leading-relaxed text-zinc-400"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-signal-500" /><span><Inline text={li} /></span></li>)}</ul>); list = []; } };
  while (i < lines.length) {
    const ln = lines[i];
    if (ln.startsWith("```")) { const buf: string[] = []; i++; while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]); i++; flush(); blocks.push(<CodeBlock key={k++} code={buf.join("\n")} />); continue; }
    if (ln.startsWith("### ")) { flush(); blocks.push(<h3 key={k++} className="mt-8 text-[15px] font-semibold tracking-tight text-white">{ln.slice(4)}</h3>); }
    else if (ln.startsWith("## ")) { flush(); blocks.push(<h2 key={k++} className="mt-12 text-[20px] font-semibold tracking-tightest text-white">{ln.slice(3)}</h2>); }
    else if (ln.startsWith("# ")) { flush(); blocks.push(<h1 key={k++} className="text-[30px] font-semibold tracking-tightest text-white sm:text-[34px]">{ln.slice(2)}</h1>); }
    else if (ln.startsWith("- ")) { list.push(ln.slice(2)); }
    else if (ln.trim() === "") { flush(); }
    else { flush(); blocks.push(<p key={k++} className="my-4 text-[15px] leading-relaxed text-zinc-400"><Inline text={ln} /></p>); }
    i++;
  }
  flush();
  return <>{blocks}</>;
}

/* ---- page ----------------------------------------------------------------- */

type Front = { name?: string; description?: string };

export default function SkillPage() {
  const [raw, setRaw] = useState("");
  const [front, setFront] = useState<Front>({});
  const [body, setBody] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch("/skill.md").then((r) => r.text()).then((text) => {
      setRaw(text);
      const fm = /^---\n([\s\S]*?)\n---\n?/.exec(text);
      const f: Front = {};
      if (fm) {
        for (const line of fm[1].split("\n")) {
          const m = /^(\w+):\s*(.*)$/.exec(line);
          if (m) (f as any)[m[1]] = m[2];
        }
        setBody(text.slice(fm[0].length));
      } else setBody(text);
      setFront(f);
    }).catch(() => setBody("Could not load skill.md."));
  }, []);

  return (
    <div className="min-h-screen">
      {/* top bar */}
      <header className="sticky top-0 z-40 bg-ink-950/70 backdrop-blur-xl">
        <div className="mx-auto flex h-[60px] max-w-3xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <Logo size={24} />
            <span className="text-[15px] font-semibold tracking-tightest text-white">Herds</span>
            <span className="text-zinc-700">/</span>
            <span className="font-mono text-[13px] text-zinc-500">skill.md</span>
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { navigator.clipboard?.writeText(raw); setCopied(true); setTimeout(() => setCopied(false), 1300); }}
              className="rounded-lg bg-white/[0.06] px-3 py-1.5 text-[13px] font-medium text-zinc-200 transition-colors hover:bg-white/[0.1]"
            >
              {copied ? "Copied ✓" : "Copy skill.md"}
            </button>
            <a href="/skill.md" className="rounded-lg px-3 py-1.5 text-[13px] text-zinc-500 transition-colors hover:text-zinc-200">
              Raw ↗
            </a>
          </div>
        </div>
        <div className="h-px w-full bg-white/[0.05]" />
      </header>

      <main className="mx-auto max-w-3xl px-6 py-14">
        <div className="label !text-signal-500">Agent skill</div>
        {/* frontmatter card */}
        {front.name && (
          <div className="surface mt-4 p-5">
            <div className="flex items-center gap-2.5">
              <Logo size={28} />
              <span className="font-mono text-[14px] text-zinc-200">{front.name}</span>
            </div>
            {front.description && (
              <p className="mt-3 text-[13.5px] leading-relaxed text-zinc-500">{front.description}</p>
            )}
          </div>
        )}
        <div className="mt-8">
          {body ? <Markdown body={body} /> : <div className="text-[14px] text-zinc-600">Loading…</div>}
        </div>

        <div className="mt-16 border-t border-white/[0.06] pt-6 text-[13px] text-zinc-600">
          Drop this into your agent so it can drive a real Mac. <Link href="/signup" className="text-signal-400 hover:text-signal-300">Start free →</Link>
        </div>
      </main>
    </div>
  );
}
