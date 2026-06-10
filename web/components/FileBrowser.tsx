"use client";

import { useEffect, useState } from "react";
import { type FileEntry, type FileContent } from "@/lib/api";
import { bytes, ago } from "@/lib/format";
import { tokenizeLine, langFromName } from "@/lib/highlight";

type ListFn = (path: string) => Promise<{ path: string; entries: FileEntry[] }>;
type ReadFn = (path: string) => Promise<FileContent>;

export function FileBrowser({
  list,
  read,
  initialPath = "",
  initialFile = null,
  fill = false,
  flat = false,
}: {
  list: ListFn;
  read: ReadFn;
  initialPath?: string;
  initialFile?: string | null;
  fill?: boolean;
  flat?: boolean;
}) {
  const [path, setPath] = useState(initialPath);
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [listErr, setListErr] = useState("");
  const [selected, setSelected] = useState<string | null>(initialFile);
  const [file, setFile] = useState<FileContent | null>(null);
  const [loadingFile, setLoadingFile] = useState(!!initialFile);

  useEffect(() => {
    let cancelled = false;
    setListErr("");
    list(path)
      .then((d) => !cancelled && setEntries(d.entries))
      .catch((e) => !cancelled && setListErr(e.message));
    return () => {
      cancelled = true;
    };
  }, [path]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadFile = (full: string) => {
    setSelected(full);
    setLoadingFile(true);
    setFile(null);
    read(full)
      .then(setFile)
      .catch(() => setFile({ path: full, size: 0, binary: false, truncated: false, content: "(failed to read)" }))
      .finally(() => setLoadingFile(false));
  };

  useEffect(() => {
    if (initialFile) loadFile(initialFile);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const open = (e: FileEntry) => {
    const next = path ? `${path}/${e.name}` : e.name;
    if (e.dir) {
      setPath(next);
      setSelected(null);
      setFile(null);
    } else {
      loadFile(next);
    }
  };

  const segments = path ? path.split("/") : [];

  // "flat" = seamless explorer columns (no card chrome); else discrete panels.
  const outerCls = flat
    ? "flex h-full min-h-0 flex-1"
    : `grid grid-cols-1 gap-3 lg:grid-cols-5 ${fill ? "h-full" : ""}`;
  const listCls = flat
    ? "flex w-[300px] shrink-0 flex-col min-h-0"
    : `surface overflow-hidden lg:col-span-2 ${fill ? "flex flex-col" : ""}`;
  const listScrollCls = flat
    ? "flex-1 overflow-auto py-1"
    : `hairline overflow-auto ${fill ? "flex-1" : "max-h-[480px]"}`;
  const previewCls = flat
    ? "flex min-h-0 flex-1 flex-col bg-black/20"
    : `surface overflow-hidden lg:col-span-3 ${fill ? "flex flex-col" : ""}`;
  const previewScrollCls = flat
    ? "flex-1 overflow-auto bg-black/15"
    : `overflow-auto bg-black/25 ${fill ? "flex-1" : "max-h-[480px]"}`;

  return (
    <div className={outerCls}>
      {/* File list */}
      <div className={listCls}>
        <div className="flex flex-wrap items-center gap-1 px-4 py-3 text-[12px]">
          <button onClick={() => setPath("")} className={path ? "text-zinc-500 hover:text-zinc-200" : "text-zinc-200"}>
            root
          </button>
          {segments.map((seg, i) => {
            const to = segments.slice(0, i + 1).join("/");
            const last = i === segments.length - 1;
            return (
              <span key={to} className="flex items-center gap-1">
                <span className="text-zinc-700">/</span>
                <button onClick={() => setPath(to)} className={last ? "text-zinc-200" : "text-zinc-500 hover:text-zinc-200"}>
                  {seg}
                </button>
              </span>
            );
          })}
        </div>

        <div className={listScrollCls}>
          {listErr && <div className="px-4 py-6 text-[12px] text-rose-400">{listErr}</div>}
          {!listErr && entries.length === 0 && <div className="px-4 py-6 text-[12px] text-zinc-600">empty</div>}
          {entries.map((e) => {
            const full = path ? `${path}/${e.name}` : e.name;
            const active = selected === full;
            return (
              <button
                key={e.name}
                onClick={() => open(e)}
                className={`row flex w-full items-center gap-3 px-4 py-2 text-left ${active ? "bg-white/[0.05]" : ""}`}
              >
                <span className={`min-w-0 flex-1 truncate font-mono text-[12px] ${e.dir ? "text-zinc-200" : "text-zinc-400"}`}>
                  {e.name}
                  {e.dir && <span className="text-zinc-600">/</span>}
                </span>
                <span className="tnum shrink-0 text-[11px] text-zinc-700">{e.dir ? "" : bytes(e.size)}</span>
                <span className="shrink-0 text-[11px] text-zinc-700">{ago(e.mtime_ms)}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Preview */}
      <div className={previewCls}>
        {!selected ? (
          <div className="grid h-full min-h-[200px] flex-1 place-items-center px-6 py-16 text-center text-[12px] text-zinc-600">
            Select a file to view its contents
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between px-5 py-3">
              <span className="truncate font-mono text-[12px] text-zinc-300">{selected}</span>
              <div className="flex shrink-0 items-center gap-4">
                <span className="text-[11px] text-zinc-600">
                  {file ? bytes(file.size) : ""}
                  {file?.truncated && " · truncated"}
                </span>
                {file && !file.binary && file.content != null && (
                  <button
                    onClick={() => download(selected.split("/").pop() || "file", file.content!)}
                    className="text-[11px] text-zinc-500 hover:text-zinc-200"
                  >
                    Download
                  </button>
                )}
              </div>
            </div>
            <div className={previewScrollCls}>
              {loadingFile && <div className="px-5 py-4 font-mono text-[12px] text-zinc-700">loading…</div>}
              {file?.binary && <div className="px-5 py-4 font-mono text-[12px] text-zinc-600">Binary file · {bytes(file.size)}</div>}
              {file && !file.binary && <CodeView content={file.content ?? ""} name={selected} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function CodeView({ content, name }: { content: string; name: string }) {
  const lang = langFromName(name);
  const lines = content.replace(/\n$/, "").split("\n");
  return (
    <div className="py-3 font-mono text-[12px] leading-[1.7]">
      {lines.map((l, i) => (
        <div key={i} className="flex">
          <span className="w-12 shrink-0 select-none pr-4 text-right text-zinc-700">{i + 1}</span>
          <span className="whitespace-pre">
            {l ? tokenizeLine(l, lang).map((t, j) => <span key={j} className={t.cls}>{t.text}</span>) : " "}
          </span>
        </div>
      ))}
    </div>
  );
}

function download(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
