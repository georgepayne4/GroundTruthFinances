import { AlertCircle } from "lucide-react";

/**
 * Persistent strip shown at the top of every page.
 * Communicates FCA regulatory positioning: GroundTruth is an information
 * service, not a regulated financial adviser.
 */
export default function DisclaimerBanner() {
  return (
    <div
      role="region"
      aria-label="Legal disclaimer"
      className="border-b border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
    >
      <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-1.5 text-xs">
        <AlertCircle size={14} aria-hidden="true" className="shrink-0" />
        <span>
          <strong>Not financial advice.</strong> Educational information only. Not a substitute for
          regulated financial advice.
        </span>
      </div>
    </div>
  );
}
