import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { useReport } from "../lib/report-context";

export default function MortgagePage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  return (
    <div>
      <PageHeader
        title="Mortgage"
        description="Mortgage analysis, affordability, and overpayment scenarios."
      />
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm text-sm text-gray-600 dark:text-gray-400">
        Full mortgage analysis coming in v9.1-03.
      </div>
    </div>
  );
}
