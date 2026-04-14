import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Menu, X, Command as CommandIcon } from "lucide-react";
import { useClerk } from "@clerk/clerk-react";
import Sidebar from "./Sidebar";
import ThemeToggle from "./ThemeToggle";
import ClerkUserButton from "./ClerkUserButton";
import DisclaimerBanner from "./DisclaimerBanner";
import Footer from "./Footer";
import CommandPalette from "./CommandPalette";
import { useReport } from "../lib/report-context";

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

// Wrapper that binds Clerk's signOut into the palette.
// Kept as a separate component so `useClerk` is only called when ClerkProvider exists.
function ClerkCommandPalette(props: { open: boolean; onClose: () => void }) {
  const { signOut } = useClerk();
  return <CommandPalette {...props} onSignOut={() => signOut({ redirectUrl: "/sign-in" })} />;
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { report, loading, analyse, profileJson } = useReport();
  const navigate = useNavigate();

  // Global Cmd+K / Ctrl+K to toggle the command palette
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
            <button
              onClick={() => setPaletteOpen(true)}
              className="hidden items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700 sm:flex dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200"
              aria-label="Open command palette"
            >
              <CommandIcon size={12} aria-hidden="true" />
              <span>Search</span>
              <kbd className="ml-2 rounded border border-gray-200 bg-white px-1 text-[10px] font-medium text-gray-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-500">
                ⌘K
              </kbd>
            </button>
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
        className="pt-14 md:pl-16 lg:pl-60 min-h-screen flex flex-col"
        role="main"
      >
        <DisclaimerBanner />
        <div className="flex-1 mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
          <Outlet />
        </div>
        <Footer />
      </main>

      {/* Command palette */}
      {CLERK_KEY ? (
        <ClerkCommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      ) : (
        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      )}
    </div>
  );
}
