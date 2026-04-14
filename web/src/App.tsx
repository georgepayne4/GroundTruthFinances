import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ReportProvider } from "./lib/report-context";
import AuthInit from "./lib/AuthInit";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import CashflowPage from "./pages/CashflowPage";
import DebtPage from "./pages/DebtPage";
import GoalsPage from "./pages/GoalsPage";
import InvestmentsPage from "./pages/InvestmentsPage";
import MortgagePage from "./pages/MortgagePage";
import LifeEventsPage from "./pages/LifeEventsPage";
import ScenariosPage from "./pages/ScenariosPage";
import SettingsPage from "./pages/SettingsPage";
import WizardPage from "./wizard/WizardPage";
import SignInPage from "./pages/SignInPage";
import SignUpPage from "./pages/SignUpPage";
import ProfilePage from "./pages/ProfilePage";

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

function AppContent() {
  return (
    <BrowserRouter>
      <ReportProvider>
        <Routes>
          <Route path="/sign-in/*" element={<SignInPage />} />
          <Route path="/sign-up/*" element={<SignUpPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<HomePage />} />
              <Route path="wizard" element={<WizardPage />} />
              <Route path="cashflow" element={<CashflowPage />} />
              <Route path="debt" element={<DebtPage />} />
              <Route path="goals" element={<GoalsPage />} />
              <Route path="investments" element={<InvestmentsPage />} />
              <Route path="mortgage" element={<MortgagePage />} />
              <Route path="life-events" element={<LifeEventsPage />} />
              <Route path="scenarios" element={<ScenariosPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="profile" element={<ProfilePage />} />
            </Route>
          </Route>
        </Routes>
      </ReportProvider>
    </BrowserRouter>
  );
}

export default function App() {
  // AuthInit requires ClerkProvider — only wrap when Clerk is configured
  if (!CLERK_KEY) {
    return <AppContent />;
  }
  return (
    <AuthInit>
      <AppContent />
    </AuthInit>
  );
}
