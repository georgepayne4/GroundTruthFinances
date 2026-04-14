import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Menu, X } from "lucide-react";
import Sidebar from "./Sidebar";
import ThemeToggle from "./ThemeToggle";
import ClerkUserButton from "./ClerkUserButton";
import { useReport } from "../lib/report-context";

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { report, loading, analyse, profileJson } = useReport();
  const navigate = useNavigate();

  async function handleAnalyse() {
    try {
      const parsed = JSON.parse(profileJson);
      await analyse(parsed);
      navigate("/");
    } catch {
      navigate("/settings");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-gray-900 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to main content
      </a>

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-30 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900" role="banner">
        <div className="flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="rounded-lg p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800 md:hidden"
              aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">GroundTruth</h1>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <ClerkUserButton />
            {report && (
              <button
                onClick={handleAnalyse}
                disabled={loading}
                aria-busy={loading}
                className="rounded-lg bg-gray-900 dark:bg-gray-100 px-4 py-1.5 text-sm font-medium text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-300 disabled:opacity-50 transition-colors"
              >
                {loading ? "Analysing..." : "Re-analyse"}
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-14 bottom-0 z-40 w-60 lg:w-60 md:w-16 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 transition-transform ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } md:translate-x-0`}
        aria-label="Sidebar"
      >
        <Sidebar onNavigate={() => setMobileOpen(false)} />
      </aside>

      {/* Main content */}
      <main
        id="main-content"
        className="pt-14 md:pl-16 lg:pl-60 min-h-screen"
        role="main"
      >
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
