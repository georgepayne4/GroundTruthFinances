import { useState } from "react";
import { useUser, useClerk } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { Trash2, User, Mail, Calendar } from "lucide-react";
import { deleteAccount } from "../lib/api";

export default function ProfilePage() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
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
