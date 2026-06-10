"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { SectionTitle, EmptyState } from "@/components/ui";
import { FileBrowser } from "@/components/FileBrowser";
import { useVolumes, fetchVolumeFiles, fetchVolumeFile } from "@/lib/api";
import { bytes, ago } from "@/lib/format";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <VolumeDetailInner />
    </Suspense>
  );
}

function VolumeDetailInner() {
  const name = useSearchParams().get("name") ?? "";
  const decoded = name;
  const sp = useSearchParams();
  const machine = sp.get("machine") ?? "";
  const { data } = useVolumes();
  const vol = (data?.volumes ?? []).find((v) => v.name === decoded && v.machine_id === machine)
    ?? (data?.volumes ?? []).find((v) => v.name === decoded);
  const mid = vol?.machine_id ?? machine;

  return (
    <div>
      <Link href="/volumes" className="mb-6 inline-block text-[12px] text-zinc-600 transition-colors hover:text-zinc-300">
        ← Volumes
      </Link>

      <div className="mb-8">
        <h1 className="text-[20px] font-semibold tracking-tight text-white">{decoded}</h1>
        <p className="mt-2 text-[13px] text-zinc-600">
          {vol ? `${bytes(vol.size_bytes)} · ${vol.file_count} files` : "—"} · on{" "}
          <span className="font-mono text-zinc-500">{mid}</span>
        </p>
      </div>

      <h2 className="mb-4 text-[13px] font-medium text-zinc-300">Files</h2>
      {!mid ? (
        <EmptyState title="Volume not found" hint="This volume isn't reporting from any connected Mac." />
      ) : (
        <FileBrowser
          list={(p) => fetchVolumeFiles(decoded, mid, p)}
          read={(p) => fetchVolumeFile(decoded, mid, p)}
          initialPath={sp.get("path") ?? ""}
          initialFile={sp.get("file")}
        />
      )}
    </div>
  );
}
