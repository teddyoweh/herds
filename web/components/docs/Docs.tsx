"use client";

/* ------------------------------------------------------------------ *
 * Herds docs — light / white mode.
 * Top bar · grouped sidebar · content (hash-routed pages) · on-this-page
 * TOC with scroll-spy · prev/next. Static-export friendly (all client).
 * ------------------------------------------------------------------ */

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Logo } from "@/components/Logo";
import { GROUPS, PAGES, type DocPage } from "./content";

const BY_ID = Object.fromEntries(PAGES.map((p) => [p.id, p])) as Record<string, DocPage>;
const IDS = new Set(PAGES.map((p) => p.id));

export function Docs() {
  const [active, setActive] = useState<string>("introduction");
  const [mobileNav, setMobileNav] = useState(false);
  const [filter, setFilter] = useState("");
  const [toc, setToc] = useState<{ id: string; text: string }[]>([]);
  const [tocActive, setTocActive] = useState<string>("");
  const contentRef = useRef<HTMLDivElement>(null);

  /* hash → page (ignore in-page anchor hashes that aren't page ids) */
  useEffect(() => {
    const sync = () => {
      const h = window.location.hash.replace(/^#/, "");
      if (IDS.has(h)) setActive(h);
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const go = (id: string) => {
    if (!IDS.has(id)) return;
    setActive(id);
    setMobileNav(false);
    if (window.location.hash !== `#${id}`) history.pushState(null, "", `#${id}`);
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  /* build the on-this-page TOC from rendered h2s + scroll-spy */
  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    const hs = Array.from(el.querySelectorAll<HTMLHeadingElement>("h2[id]"));
    setToc(hs.map((h) => ({ id: h.id, text: h.dataset.toc || h.textContent || h.id })));
    setTocActive(hs[0]?.id || "");
    const obs = new IntersectionObserver(
      (entries) => {
        const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (vis[0]) setTocActive((vis[0].target as HTMLElement).id);
      },
      { rootMargin: "-90px 0px -70% 0px", threshold: 0 },
    );
    hs.forEach((h) => obs.observe(h));
    return () => obs.disconnect();
  }, [active]);

  const page = BY_ID[active] || PAGES[0];
  const idx = PAGES.findIndex((p) => p.id === page.id);
  const prev = PAGES[idx - 1];
  const next = PAGES[idx + 1];

  const groups = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const match = (p: DocPage) => !q || p.title.toLowerCase().includes(q) || p.description.toLowerCase().includes(q) || p.group.toLowerCase().includes(q);
    return GROUPS.map((g) => ({ name: g, items: PAGES.filter((p) => p.group === g && match(p)) })).filter((g) => g.items.length);
  }, [filter]);

  const Body = page.Body;

  return (
    <div className="min-h-screen bg-white font-sans text-stone-900 antialiased">
      {/* ── top bar ──────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-stone-200/70 bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex h-[58px] max-w-[1320px] items-center gap-4 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <Logo size={24} />
            <span className="text-[15px] font-semibold tracking-tight text-stone-900">Herds</span>
            <span className="text-stone-300">/</span>
            <span className="text-[14px] text-stone-500">Docs</span>
          </Link>
          <div className="ml-auto flex items-center gap-1.5">
            <a href="https://github.com/teddyoweh/herds" target="_blank" rel="noreferrer" className="hidden rounded-lg px-3 py-1.5 text-[13px] text-stone-500 transition-colors hover:text-stone-900 sm:inline-flex">
              GitHub
            </a>
            <Link href="/skill" className="hidden rounded-lg px-3 py-1.5 text-[13px] text-stone-500 transition-colors hover:text-stone-900 sm:inline-flex">
              Agent skill
            </Link>
            <Link href="/signup" className="inline-flex items-center rounded-full bg-stone-900 px-4 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-stone-700">
              Start free
            </Link>
            <button onClick={() => setMobileNav((v) => !v)} className="ml-1 rounded-lg p-2 text-stone-500 hover:bg-stone-100 lg:hidden" aria-label="Menu">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" /></svg>
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1320px] gap-0 px-0 sm:px-6">
        {/* ── sidebar ────────────────────────────────────────────── */}
        <aside className={`${mobileNav ? "block" : "hidden"} fixed inset-x-0 top-[58px] z-40 max-h-[calc(100vh-58px)] overflow-y-auto border-b border-stone-200 bg-white px-5 pb-10 pt-5 lg:sticky lg:top-[58px] lg:z-0 lg:block lg:max-h-[calc(100vh-58px)] lg:w-[248px] lg:flex-none lg:border-b-0 lg:px-0 lg:pr-6`}>
          <div className="relative mb-5">
            <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" strokeLinecap="round" /></svg>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search docs"
              className="w-full rounded-lg bg-stone-100 py-2 pl-9 pr-3 text-[13px] text-stone-800 outline-none ring-1 ring-transparent transition placeholder:text-stone-400 focus:bg-white focus:ring-signal-500/40"
            />
          </div>
          <nav className="space-y-6">
            {groups.map((g) => (
              <div key={g.name}>
                <div className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-[0.13em] text-stone-400">{g.name}</div>
                <div className="space-y-0.5">
                  {g.items.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => go(p.id)}
                      className={`block w-full rounded-lg px-2.5 py-[7px] text-left text-[13.5px] transition-colors ${p.id === active ? "bg-signal-500/10 font-medium text-signal-700" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"}`}
                    >
                      {p.title}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {!groups.length && <div className="px-2 text-[13px] text-stone-400">No matches.</div>}
          </nav>
        </aside>

        {/* ── content ────────────────────────────────────────────── */}
        <main className="min-w-0 flex-1 px-5 py-10 sm:px-8 lg:px-12">
          <div className="mx-auto max-w-[720px]">
            <div className="text-[12px] font-medium uppercase tracking-[0.14em] text-signal-600">{page.group}</div>
            <h1 className="ed mt-2 text-[38px] leading-[1.05] text-stone-900">{page.title}</h1>

            <div ref={contentRef} className="mt-2">
              <Body go={go} />
            </div>

            {/* prev / next */}
            <div className="mt-16 grid grid-cols-1 gap-3 border-t border-stone-200 pt-8 sm:grid-cols-2">
              {prev ? (
                <button onClick={() => go(prev.id)} className="group flex flex-col rounded-xl px-4 py-3 text-left ring-1 ring-stone-200 transition-colors hover:bg-stone-50">
                  <span className="text-[12px] text-stone-400">← Previous</span>
                  <span className="mt-0.5 text-[14px] font-medium text-stone-800 group-hover:text-signal-700">{prev.title}</span>
                </button>
              ) : <span />}
              {next ? (
                <button onClick={() => go(next.id)} className="group flex flex-col rounded-xl px-4 py-3 text-right ring-1 ring-stone-200 transition-colors hover:bg-stone-50 sm:items-end">
                  <span className="text-[12px] text-stone-400">Next →</span>
                  <span className="mt-0.5 text-[14px] font-medium text-stone-800 group-hover:text-signal-700">{next.title}</span>
                </button>
              ) : <span />}
            </div>

            <footer className="mt-12 flex items-center gap-2 text-[13px] text-stone-400">
              <Logo size={16} />
              <span>Herds — your Mac is the cloud.</span>
              <a href="/skill.md" className="ml-auto font-mono text-[12px] text-stone-400 hover:text-stone-700">/skill.md ↗</a>
            </footer>
          </div>
        </main>

        {/* ── on this page ───────────────────────────────────────── */}
        <aside className="hidden w-[200px] flex-none py-10 xl:block">
          {toc.length > 0 && (
            <div className="sticky top-[80px]">
              <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.13em] text-stone-400">On this page</div>
              <ul className="space-y-1.5 border-l border-stone-200">
                {toc.map((t) => (
                  <li key={t.id}>
                    <a
                      href={`#${t.id}`}
                      className={`-ml-px block border-l-2 py-0.5 pl-3 text-[12.5px] leading-snug transition-colors ${tocActive === t.id ? "border-signal-500 text-signal-700" : "border-transparent text-stone-500 hover:text-stone-800"}`}
                    >
                      {t.text}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
