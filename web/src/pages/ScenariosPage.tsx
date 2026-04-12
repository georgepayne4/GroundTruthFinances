import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { useReport } from "../lib/report-context";

export default function ScenariosPage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  return (
    <div>
      <PageHeader
        title="Scenarios"
        description="What-if analysis and compound scenario trees."
      />
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm text-sm text-gray-600 dark:text-gray-400">
        Full scenario analysis coming in v9.1-03.
      </div>
    </div>
  );
}
