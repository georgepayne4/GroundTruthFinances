import type { HTMLAttributes } from "react";

/**
 * Shimmer placeholder primitive. Compose page-shaped skeletons from these.
 *
 * Use `w-*` and `h-*` utilities to size; default is full width + single-line height.
 */
export function Skeleton({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={`gt-skeleton rounded-md bg-gray-200 dark:bg-gray-800 ${className}`}
      {...rest}
    />
  );
}

/** Full-page dashboard skeleton — matches the Home page layout at a glance. */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading analysis">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-1 flex items-center justify-center py-4">
          <Skeleton className="h-40 w-40 rounded-full" />
        </div>
        <div className="lg:col-span-4 grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CardSkeleton className="h-72" />
        <CardSkeleton className="h-72" />
      </div>
      <CardSkeleton className="h-48" />
    </div>
  );
}

/** Single-card skeleton — use for one-up page content (Debt, Goals, etc.). */
export function CardSkeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 ${className}`}
    >
      <Skeleton className="h-3 w-24 mb-4" />
      <Skeleton className="h-8 w-40 mb-3" />
      <Skeleton className="h-3 w-full mb-2" />
      <Skeleton className="h-3 w-3/4" />
    </div>
  );
}

/** Generic page skeleton — header + stacked cards. Use for detail pages. */
export function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading analysis">
      <div>
        <Skeleton className="h-7 w-48 mb-2" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
      <CardSkeleton className="h-80" />
    </div>
  );
}
