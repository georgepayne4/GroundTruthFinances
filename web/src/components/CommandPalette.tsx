import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  LayoutDashboard,
  ArrowLeftRight,
  CreditCard,
  Target,
  TrendingUp,
  Home,
  Calendar,
  GitBranch,
  Settings,
  UserCircle,
  Wand2,
  Play,
  LogOut,
  Moon,
  Sun,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useReport } from "../lib/report-context";

interface Command {
  id: string;
  label: string;
  group: "Navigate" | "Actions";
  icon: LucideIcon;
  keywords?: string;
  perform: () => void | Promise<void>;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSignOut?: () => Promise<void> | void;
}

export default function CommandPalette({ open, onClose, onSignOut }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { analyse, profileJson, loading } = useReport();

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  const commands: Command[] = useMemo(() => {
    const go = (path: string) => () => {
      navigate(path);
      onClose();
    };
    const nav: Command[] = [
      { id: "nav-overview", label: "Overview", group: "Navigate", icon: LayoutDashboard, perform: go("/") },
      { id: "nav-wizard", label: "Setup wizard", group: "Navigate", icon: Wand2, keywords: "wizard setup", perform: go("/wizard") },
      { id: "nav-cashflow", label: "Cashflow", group: "Navigate", icon: ArrowLeftRight, perform: go("/cashflow") },
      { id: "nav-debt", label: "Debt", group: "Navigate", icon: CreditCard, perform: go("/debt") },
      { id: "nav-goals", label: "Goals", group: "Navigate", icon: Target, perform: go("/goals") },
      { id: "nav-investments", label: "Investments", group: "Navigate", icon: TrendingUp, perform: go("/investments") },
      { id: "nav-mortgage", label: "Mortgage", group: "Navigate", icon: Home, perform: go("/mortgage") },
      { id: "nav-life-events", label: "Life Events", group: "Navigate", icon: Calendar, keywords: "timeline projection", perform: go("/life-events") },
      { id: "nav-scenarios", label: "Scenarios", group: "Navigate", icon: GitBranch, keywords: "stress test what-if", perform: go("/scenarios") },
      { id: "nav-settings", label: "Settings", group: "Navigate", icon: Settings, keywords: "profile yaml json upload", perform: go("/settings") },
      { id: "nav-profile", label: "Profile", group: "Navigate", icon: UserCircle, keywords: "account", perform: go("/profile") },
    ];

    const actions: Command[] = [
      {
        id: "action-analyse",
        label: loading ? "Re-analyse (running...)" : "Re-analyse profile",
        group: "Actions",
        icon: Play,
        keywords: "run compute refresh",
        perform: async () => {
          try {
            const parsed = JSON.parse(profileJson);
            onClose();
            await analyse(parsed);
            navigate("/");
          } catch {
            onClose();
            navigate("/settings");
          }
        },
      },
      {
        id: "action-theme",
        label: "Toggle light / dark theme",
        group: "Actions",
        icon: document.documentElement.classList.contains("dark") ? Sun : Moon,
        keywords: "dark mode light appearance",
        perform: () => {
          const root = document.documentElement;
          const nowDark = !root.classList.contains("dark");
          root.classList.toggle("dark", nowDark);
          localStorage.setItem("theme", nowDark ? "dark" : "light");
          onClose();
        },
      },
    ];

    if (onSignOut) {
      actions.push({
        id: "action-signout",
        label: "Sign out",
        group: "Actions",
        icon: LogOut,
        keywords: "logout exit",
        perform: async () => {
          onClose();
          await onSignOut();
        },
      });
    }

    return [...nav, ...actions];
  }, [navigate, onClose, analyse, profileJson, loading, onSignOut]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;

    // Subsequence match: every query char must appear in order in the haystack.
    // Score rewards consecutive matches and prefix matches on label.
    const scored = commands
      .map((c) => {
        const label = c.label.toLowerCase();
        const haystack = `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase();
        let qi = 0;
        let score = 0;
        let consecutive = 0;
        let lastMatchIdx = -1;
        for (let hi = 0; hi < haystack.length && qi < q.length; hi++) {
          if (haystack[hi] === q[qi]) {
            // Consecutive-match bonus
            if (lastMatchIdx === hi - 1) {
              consecutive++;
              score += 2 + consecutive;
            } else {
              consecutive = 0;
              score += 1;
            }
            lastMatchIdx = hi;
            qi++;
          }
        }
        if (qi < q.length) return null;
        // Prefix bonus if label starts with the query
        if (label.startsWith(q)) score += 10;
        // Small bonus if any label word starts with the query
        else if (label.split(/\s+/).some((w) => w.startsWith(q))) score += 5;
        return { cmd: c, score };
      })
      .filter((s): s is { cmd: Command; score: number } => s !== null);

    // Sort by score desc; preserve original order for ties
    scored.sort((a, b) => b.score - a.score);
    return scored.map((s) => s.cmd);
  }, [commands, query]);

  // Reset state on open/close; capture/restore focus
  useEffect(() => {
    if (open) {
      lastFocusedRef.current = document.activeElement as HTMLElement | null;
      setQuery("");
      setActive(0);
      // Defer to allow render before focus
      requestAnimationFrame(() => inputRef.current?.focus());
    } else {
      lastFocusedRef.current?.focus();
    }
  }, [open]);

  // Clamp active index when filtered list shrinks
  useEffect(() => {
    if (active >= filtered.length) setActive(Math.max(0, filtered.length - 1));
  }, [filtered.length, active]);

  // Scroll active item into view
  useEffect(() => {
    if (!open) return;
    const list = listRef.current;
    if (!list) return;
    const el = list.querySelector<HTMLElement>(`[data-index="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  if (!open) return null;

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const cmd = filtered[active];
      if (cmd) cmd.perform();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "Tab") {
      // Focus trap: cycle within dialog focusable elements
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusables = dialog.querySelectorAll<HTMLElement>(
        'input, [role="option"], button, [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;
      if (e.shiftKey && activeEl === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && activeEl === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  // Group commands for rendering, preserving filtered order
  const groups = filtered.reduce<Record<string, { items: Command[]; startIndex: number }>>((acc, cmd, idx) => {
    if (!acc[cmd.group]) acc[cmd.group] = { items: [], startIndex: idx };
    acc[cmd.group].items.push(cmd);
    return acc;
  }, {});

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[15vh]"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />
      <div
        ref={dialogRef}
        className="relative w-full max-w-xl overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-800 dark:bg-gray-900"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="flex items-center gap-3 border-b border-gray-200 px-4 py-3 dark:border-gray-800">
          <Search size={18} className="text-gray-400" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            placeholder="Search pages and actions..."
            className="flex-1 bg-transparent text-sm text-gray-900 placeholder-gray-400 outline-none dark:text-gray-100 dark:placeholder-gray-600"
            aria-label="Search commands"
            aria-controls="command-palette-list"
            aria-activedescendant={filtered[active] ? `cmd-${filtered[active].id}` : undefined}
          />
          <kbd className="hidden rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 sm:inline dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
            Esc
          </kbd>
        </div>

        {filtered.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
            No results for "{query}"
          </div>
        ) : (
          <ul
            id="command-palette-list"
            ref={listRef}
            role="listbox"
            className="max-h-80 overflow-y-auto py-1"
          >
            {Object.entries(groups).map(([groupName, { items, startIndex }]) => (
              <li key={groupName}>
                <div className="px-4 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                  {groupName}
                </div>
                <ul>
                  {items.map((cmd, i) => {
                    const globalIndex = startIndex + i;
                    const isActive = globalIndex === active;
                    const Icon = cmd.icon;
                    return (
                      <li
                        key={cmd.id}
                        id={`cmd-${cmd.id}`}
                        data-index={globalIndex}
                        role="option"
                        aria-selected={isActive}
                        onMouseEnter={() => setActive(globalIndex)}
                        onClick={() => cmd.perform()}
                        className={`flex cursor-pointer items-center gap-3 px-4 py-2 text-sm ${
                          isActive
                            ? "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100"
                            : "text-gray-700 dark:text-gray-300"
                        }`}
                      >
                        <Icon size={16} className="flex-shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true" />
                        <span className="flex-1">{cmd.label}</span>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
        )}

        <div className="flex items-center justify-between border-t border-gray-200 px-4 py-2 text-[11px] text-gray-500 dark:border-gray-800 dark:text-gray-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 dark:border-gray-700 dark:bg-gray-800">↑↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 dark:border-gray-700 dark:bg-gray-800">↵</kbd>
              select
            </span>
          </div>
          <span>{filtered.length} result{filtered.length === 1 ? "" : "s"}</span>
        </div>
      </div>
    </div>
  );
}
