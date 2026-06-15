"use client";

/* ------------------------------------------------------------------ *
 * Docs UI primitives — light / white mode.
 * A tiny syntax highlighter (Python + bash), code blocks with copy,
 * callouts, parameter tables, headings with anchors, and prose helpers.
 * Brand-tinted light palette: green strings, purple keywords, amber
 * numbers, muted-gray comments — readable and on-brand.
 * ------------------------------------------------------------------ */

import { useState, type ReactNode } from "react";

/* ---- syntax highlighting -------------------------------------------------- */

const C = {
  comment: "text-stone-400 italic",
  string: "text-[#15803d]",
  keyword: "text-[#9333ea]",
  number: "text-[#b45309]",
  fn: "text-[#0f766e]",
  builtin: "text-stone-500",
  flag: "text-[#0550ae]",
  prop: "text-stone-800",
};

const PY_KW = new Set(
  "def class return if elif else for while with as in not and or is None True False lambda try except finally raise yield import from async await pass break continue global nonlocal assert del print with".split(
    " ",
  ),
);
const PY_BUILTIN = new Set("self len range dict list str int float bool open set tuple type isinstance enumerate".split(" "));

type Rule = { re: RegExp; cls?: string; classify?: (w: string, after: string) => string | undefined };

const PY_RULES: Rule[] = [
  { re: /\s+/y },
  { re: /#[^\n]*/y, cls: C.comment },
  { re: /"""[\s\S]*?"""|'''[\s\S]*?'''/y, cls: C.string },
  { re: /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/y, cls: C.string },
  { re: /@[A-Za-z_]\w*/y, cls: C.fn },
  { re: /\d[\w.]*/y, cls: C.number },
  {
    re: /[A-Za-z_]\w*/y,
    classify: (w, after) => {
      if (PY_KW.has(w)) return C.keyword;
      if (after.trimStart().startsWith("(")) return C.fn;
      if (PY_BUILTIN.has(w)) return C.builtin;
      return undefined;
    },
  },
];

const BASH_RULES: Rule[] = [
  { re: /\s+/y },
  { re: /#[^\n]*/y, cls: C.comment },
  { re: /"(?:[^"\\]|\\.)*"|'[^']*'/y, cls: C.string },
  { re: /--?[A-Za-z][\w-]*/y, cls: C.flag },
  { re: /\$[A-Za-z_]\w*/y, cls: C.flag },
  {
    re: /[A-Za-z_][\w.-]*/y,
    classify: (w) => (["herds", "herdsd", "pip", "uv", "curl", "sudo", "python3", "python", "npm", "git", "export", "cd", "sh"].includes(w) ? C.fn : undefined),
  },
];

function highlight(code: string, lang?: string): ReactNode[] {
  const rules = lang === "python" || lang === "py" ? PY_RULES : lang === "bash" || lang === "sh" || lang === "shell" ? BASH_RULES : null;
  if (!rules) return [code];
  const out: ReactNode[] = [];
  let i = 0,
    key = 0,
    buf = "";
  const flush = () => {
    if (buf) {
      out.push(buf);
      buf = "";
    }
  };
  while (i < code.length) {
    let hit = false;
    for (const r of rules) {
      r.re.lastIndex = i;
      const m = r.re.exec(code);
      if (m && m.index === i && m[0].length) {
        const text = m[0];
        let cls = r.cls;
        if (r.classify) cls = r.classify(text, code.slice(i + text.length, i + text.length + 4));
        if (cls) {
          flush();
          out.push(
            <span key={key++} className={cls}>
              {text}
            </span>,
          );
        } else {
          buf += text;
        }
        i += text.length;
        hit = true;
        break;
      }
    }
    if (!hit) {
      buf += code[i++];
    }
  }
  flush();
  return out;
}

/* ---- code block ----------------------------------------------------------- */

export function Code({ children, lang = "python", title }: { children: string; lang?: string; title?: string }) {
  const [copied, setCopied] = useState(false);
  const code = children.replace(/\n$/, "");
  return (
    <div className="group relative my-5 overflow-hidden rounded-2xl bg-[#faf9f6] ring-1 ring-stone-200/70">
      <div className="flex items-center gap-2 border-b border-stone-200/70 bg-[#f3f2ee] px-4 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-2 font-mono text-[11px] text-stone-400">{title || lang}</span>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 1300);
          }}
          className={`ml-auto rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${copied ? "text-signal-600" : "text-stone-400 hover:bg-stone-200/60 hover:text-stone-700"}`}
        >
          {copied ? "copied ✓" : "copy"}
        </button>
      </div>
      <pre className="overflow-x-auto px-5 py-4 font-mono text-[12.75px] leading-[1.75] text-stone-700">
        <code>{highlight(code, lang)}</code>
      </pre>
    </div>
  );
}

/* ---- callout -------------------------------------------------------------- */

const CALLOUTS = {
  note: { ring: "ring-stone-200", bg: "bg-stone-50", dot: "bg-stone-400", label: "Note", text: "text-stone-500" },
  tip: { ring: "ring-signal-500/25", bg: "bg-signal-500/[0.06]", dot: "bg-signal-500", label: "Tip", text: "text-signal-700" },
  warn: { ring: "ring-amber-300/60", bg: "bg-amber-50", dot: "bg-amber-500", label: "Heads up", text: "text-amber-700" },
} as const;

export function Callout({ type = "note", children, title }: { type?: keyof typeof CALLOUTS; children: ReactNode; title?: string }) {
  const c = CALLOUTS[type];
  return (
    <div className={`my-5 rounded-xl ${c.bg} px-4 py-3.5 ring-1 ${c.ring}`}>
      <div className={`mb-1 flex items-center gap-2 text-[12px] font-semibold ${c.text}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
        {title || c.label}
      </div>
      <div className="text-[14px] leading-relaxed text-stone-600 [&_a]:text-signal-600 [&_a:hover]:text-signal-500 [&_code]:rounded [&_code]:bg-white [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.86em] [&_code]:text-stone-700 [&_code]:ring-1 [&_code]:ring-stone-200">
        {children}
      </div>
    </div>
  );
}

/* ---- parameter table ------------------------------------------------------ */

export type Param = { name: string; type: string; default?: string; required?: boolean; desc: ReactNode };

export function Params({ rows }: { rows: Param[] }) {
  return (
    <div className="my-6 overflow-hidden rounded-2xl ring-1 ring-stone-200">
      {rows.map((p, i) => (
        <div key={p.name} className={`px-4 py-3.5 ${i > 0 ? "border-t border-stone-100" : ""}`}>
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <code className="font-mono text-[13px] font-semibold text-stone-900">{p.name}</code>
            <code className="font-mono text-[12px] text-signal-700">{p.type}</code>
            {p.required ? (
              <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-rose-600">required</span>
            ) : p.default !== undefined ? (
              <span className="font-mono text-[11.5px] text-stone-400">= {p.default}</span>
            ) : null}
          </div>
          <div className="mt-1.5 text-[13.5px] leading-relaxed text-stone-600 [&_code]:rounded [&_code]:bg-stone-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.86em] [&_code]:text-stone-700">
            {p.desc}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---- endpoint / generic table -------------------------------------------- */

const METHOD_COLORS: Record<string, string> = {
  GET: "text-sky-700 bg-sky-50 ring-sky-200",
  POST: "text-signal-700 bg-signal-500/10 ring-signal-500/25",
  PUT: "text-amber-700 bg-amber-50 ring-amber-200",
  DELETE: "text-rose-700 bg-rose-50 ring-rose-200",
  WS: "text-violet-700 bg-violet-50 ring-violet-200",
};

export function Endpoints({ rows }: { rows: { method: string; path: string; desc: string }[] }) {
  return (
    <div className="my-6 overflow-hidden rounded-2xl ring-1 ring-stone-200">
      {rows.map((r, i) => (
        <div key={i} className={`flex flex-col gap-1.5 px-4 py-3 sm:flex-row sm:items-center sm:gap-3 ${i > 0 ? "border-t border-stone-100" : ""}`}>
          <span className={`inline-flex w-fit items-center rounded-md px-2 py-0.5 font-mono text-[11px] font-semibold ring-1 ${METHOD_COLORS[r.method] || "text-stone-600 bg-stone-50 ring-stone-200"}`}>{r.method}</span>
          <code className="font-mono text-[12.5px] text-stone-800">{r.path}</code>
          <span className="text-[13px] text-stone-500 sm:ml-auto sm:text-right">{r.desc}</span>
        </div>
      ))}
    </div>
  );
}

/* ---- headings + prose ----------------------------------------------------- */

export function H2({ children, id }: { children: ReactNode; id?: string }) {
  const slug = id || slugify(children);
  return (
    <h2 id={slug} data-toc={typeof children === "string" ? children : slug} className="group ed scroll-mt-24 mt-14 text-[24px] leading-tight text-stone-900">
      <a href={`#${slug}`} className="relative">
        {children}
        <span className="absolute -left-5 top-1/2 -translate-y-1/2 text-signal-500 opacity-0 transition-opacity group-hover:opacity-100">#</span>
      </a>
    </h2>
  );
}

export function H3({ children, id }: { children: ReactNode; id?: string }) {
  const slug = id || slugify(children);
  return (
    <h3 id={slug} className="scroll-mt-24 mt-9 text-[16.5px] font-semibold tracking-tight text-stone-900">
      {children}
    </h3>
  );
}

export function P({ children }: { children: ReactNode }) {
  return <p className="my-4 text-[15px] leading-[1.75] text-stone-600">{children}</p>;
}

export function Lead({ children }: { children: ReactNode }) {
  return <p className="mt-3 text-[17px] leading-relaxed text-stone-500">{children}</p>;
}

export function UL({ children }: { children: ReactNode }) {
  return <ul className="my-4 space-y-2.5 pl-1">{children}</ul>;
}

export function LI({ children }: { children: ReactNode }) {
  return (
    <li className="flex gap-2.5 text-[15px] leading-relaxed text-stone-600">
      <span className="mt-[10px] h-1 w-1 shrink-0 rounded-full bg-signal-500" />
      <span>{children}</span>
    </li>
  );
}

export function Co({ children }: { children: ReactNode }) {
  return <code className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-[0.86em] text-stone-800 ring-1 ring-stone-200/70">{children}</code>;
}

export function A({ href, children }: { href: string; children: ReactNode }) {
  const ext = href.startsWith("http");
  return (
    <a href={href} {...(ext ? { target: "_blank", rel: "noreferrer" } : {})} className="text-signal-600 underline decoration-signal-500/30 underline-offset-2 transition-colors hover:text-signal-500">
      {children}
    </a>
  );
}

export function Divider() {
  return <div className="my-10 h-px w-full bg-stone-100" />;
}

/* a 2-up grid of link cards (used on the intro page) */
export function CardGrid({ children }: { children: ReactNode }) {
  return <div className="my-6 grid grid-cols-1 gap-3 sm:grid-cols-2">{children}</div>;
}

export function Card({ title, desc, onClick, kbd }: { title: string; desc: string; onClick?: () => void; kbd?: string }) {
  return (
    <button onClick={onClick} className="group flex flex-col rounded-2xl bg-white p-5 text-left ring-1 ring-stone-200 transition-all hover:-translate-y-0.5 hover:shadow-[0_12px_30px_-16px_rgba(0,0,0,0.18)] hover:ring-stone-300">
      <div className="flex items-center justify-between">
        <span className="text-[15px] font-semibold tracking-tight text-stone-900">{title}</span>
        {kbd && <span className="font-mono text-[11px] text-stone-400">{kbd}</span>}
        <span className="text-stone-300 transition-transform group-hover:translate-x-0.5 group-hover:text-signal-500">→</span>
      </div>
      <span className="mt-1.5 text-[13.5px] leading-relaxed text-stone-500">{desc}</span>
    </button>
  );
}

export function slugify(node: ReactNode): string {
  const s = typeof node === "string" ? node : Array.isArray(node) ? node.filter((n) => typeof n === "string").join(" ") : "section";
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
