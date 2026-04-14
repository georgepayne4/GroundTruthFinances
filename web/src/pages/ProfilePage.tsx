import { useState } from "react";
import { useUser, useClerk } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { Trash2, User, Mail, Calendar, Download } from "lucide-react";
import { deleteAccount, exportAccount } from "../lib/api";

export default function ProfilePage() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900 dark:border-gray-700 dark:border-t-gray-100" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="py-20 text-center text-gray-500 dark:text-gray-400">
        Sign in to view your profile.
      </div>
    );
  }

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      const data = await exportAccount();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `groundtruth-data-${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export data");
    } finally {
      setExporting(false);
    }
  }

  async function handleDelete() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount();
      await signOut();
      navigate("/sign-in");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete account");
      setDeleting(false);
      setConfirming(false);
    }
  }

  const memberSince = user.createdAt
    ? new Date(user.createdAt).toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })
    : "Unknown";

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Profile</h2>

      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <User size={18} className="text-gray-400" />
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Name</p>
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {user.fullName || "Not set"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Mail size={18} className="text-gray-400" />
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Email</p>
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {user.primaryEmailAddress?.emailAddress || "Not set"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Calendar size={18} className="text-gray-400" />
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Member since</p>
              <p className="font-medium text-gray-900 dark:text-gray-100">{memberSince}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Your data (GDPR right to access) */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Your Data</h3>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Download a complete JSON export of all data we hold about you, including profiles,
          reports, and account history.
        </p>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          <Download size={16} />
          {exporting ? "Preparing export..." : "Download my data"}
        </button>
      </div>

      {/* Danger zone */}
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 dark:border-red-900/50 dark:bg-red-950/30">
        <h3 className="text-lg font-semibold text-red-800 dark:text-red-300">Danger Zone</h3>
        <p className="mt-1 text-sm text-red-600 dark:text-red-400">
          Permanently delete your account and all associated data. This cannot be undone.
        </p>

        {error && (
          <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-300">{error}</p>
        )}

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleDelete}
            disabled={deleting}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              confirming
                ? "bg-red-600 text-white hover:bg-red-700"
                : "border border-red-300 text-red-700 hover:bg-red-100 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
            } disabled:opacity-50`}
          >
            <Trash2 size={16} />
            {deleting ? "Deleting..." : confirming ? "Confirm deletion" : "Delete my account"}
          </button>
          {confirming && !deleting && (
            <button
              onClick={() => setConfirming(false)}
              className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
