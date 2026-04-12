import { Link } from "react-router-dom";
import { BarChart3 } from "lucide-react";

interface EmptyStateProps {
  title?: string;
  message?: string;
}

export default function EmptyState({
  title = "No analysis yet",
  message = "Run your first analysis to see your financial health dashboard.",
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="rounded-full bg-gray-100 dark:bg-gray-800 p-6 mb-6">
        <BarChart3 size={48} className="text-gray-400 dark:text-gray-500" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 max-w-md mb-6">{message}</p>
      <Link
        to="/settings"
        className="rounded-lg bg-gray-900 dark:bg-gray-100 px-5 py-2.5 text-sm font-medium text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-300 transition-colors"
      >
        Get Started
      </Link>
    </div>
  );
}
