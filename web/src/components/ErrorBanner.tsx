import { AlertCircle, X } from "lucide-react";

interface ErrorBannerProps {
  title?: string;
  message: string;
  onDismiss?: () => void;
  action?: { label: string; onClick: () => void };
}

/**
 * Inline error banner. Dismissible, action-optional. Replaces browser alert().
 *
 * Use for recoverable errors that need user attention without blocking the UI.
 */
export default function ErrorBanner({ title, message, onDismiss, action }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm dark:border-red-900/50 dark:bg-red-950/40"
    >
      <AlertCircle size={18} className="mt-0.5 flex-shrink-0 text-red-600 dark:text-red-400" />
      <div className="flex-1">
        {title && (
          <p className="font-semibold text-red-800 dark:text-red-200">{title}</p>
        )}
        <p className="text-red-700 dark:text-red-300 whitespace-pre-wrap">{message}</p>
        {action && (
          <button
            onClick={action.onClick}
            className="mt-2 text-sm font-medium text-red-800 underline decoration-red-300 underline-offset-2 hover:text-red-900 dark:text-red-200 dark:decoration-red-700 dark:hover:text-red-100"
          >
            {action.label}
          </button>
        )}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="flex-shrink-0 rounded-md p-1 text-red-500 hover:bg-red-100 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-900/40 dark:hover:text-red-200"
          aria-label="Dismiss"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}
