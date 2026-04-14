import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  ArrowLeftRight,
  CreditCard,
  Target,
  TrendingUp,
  Home,
  Calendar,
  GitBranch,
  Settings,
  Wand2,
  UserCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/wizard", label: "Setup", icon: Wand2 },
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/cashflow", label: "Cashflow", icon: ArrowLeftRight },
  { to: "/debt", label: "Debt", icon: CreditCard },
  { to: "/goals", label: "Goals", icon: Target },
  { to: "/investments", label: "Investments", icon: TrendingUp },
  { to: "/mortgage", label: "Mortgage", icon: Home },
  { to: "/life-events", label: "Life Events", icon: Calendar },
  { to: "/scenarios", label: "Scenarios", icon: GitBranch },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/profile", label: "Profile", icon: UserCircle },
];

interface SidebarProps {
  onNavigate?: () => void;
}

export default function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <nav aria-label="Main navigation">
      <ul className="space-y-1 px-3 py-4">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === "/"}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800/50 dark:hover:text-gray-200"
                }`
              }
            >
              <Icon size={18} aria-hidden="true" />
              <span className="hidden lg:inline">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
