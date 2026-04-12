import { useNavigate } from "react-router-dom";
import { useReport } from "../lib/report-context";
import PageHeader from "../components/PageHeader";

export default function SettingsPage() {
  const { loading, error, analyse, profileJson, setProfileJson } = useReport();
  const navigate = useNavigate();

  async function handleAnalyse() {
    try {
      const parsed = JSON.parse(profileJson);
      await analyse(parsed);
      navigate("/");
    } catch (e) {
      if (e instanceof SyntaxError) {
        alert("Invalid JSON. Please check your profile data.");
      }
    }
  }

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Edit your financial profile and run analysis."
      />

      {error && (
        <div role="alert" className="mb-4 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-800 dark:text-red-200">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
        <label htmlFor="profile-json" className="block text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-3">
          Profile JSON
        </label>
        <textarea
          id="profile-json"
          value={profileJson}
          onChange={(e) => setProfileJson(e.target.value)}
          className="w-full h-96 font-mono text-xs border border-gray-300 dark:border-gray-700 rounded-lg p-3 bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
          spellCheck={false}
          aria-describedby="profile-json-help"
        />
        <p id="profile-json-help" className="mt-2 text-xs text-gray-600 dark:text-gray-400">
          Edit your profile above and click "Run Analysis" to generate your financial health report.
        </p>
        <button
          onClick={handleAnalyse}
          disabled={loading}
          aria-busy={loading}
          className="mt-4 rounded-lg bg-gray-900 dark:bg-gray-100 px-6 py-2.5 text-sm font-medium text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:ring-offset-2 disabled:opacity-50 transition-colors"
        >
          {loading ? "Analysing..." : "Run Analysis"}
        </button>
      </div>
    </div>
  );
}
