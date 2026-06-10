"use client";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** A stat-strip placeholder matching the real metric layout. */
export function StatSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-y-8 sm:grid-cols-4 sm:gap-y-0">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i}>
          <Skeleton className="h-8 w-14" />
          <Skeleton className="mt-3 h-3 w-20" />
          <Skeleton className="mt-2 h-2.5 w-14" />
        </div>
      ))}
    </div>
  );
}

/** Rows of list placeholders. */
export function RowSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2.5">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}
