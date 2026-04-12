import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { useReport } from "../lib/report-context";

export default function GoalsPage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  return (
    <div>
      <PageHeader
        title="Goals"
        description="Track progress towards your financial goals."
      />
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm text-sm text-gray-600 dark:text-gray-400">
        Full goals analysis coming in v9.1-02.
      </div>
    </div>
  );
}
