import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { useReport } from "../lib/report-context";

export default function LifeEventsPage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  return (
    <div>
      <PageHeader
        title="Life Events"
        description="Impact analysis for major life changes."
      />
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm text-sm text-gray-600 dark:text-gray-400">
        Full life events analysis coming in v9.1-03.
      </div>
    </div>
  );
}
