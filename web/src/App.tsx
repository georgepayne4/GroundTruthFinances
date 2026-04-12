import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ReportProvider } from "./lib/report-context";
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

export default function App() {
  return (
    <BrowserRouter>
      <ReportProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="cashflow" element={<CashflowPage />} />
            <Route path="debt" element={<DebtPage />} />
            <Route path="goals" element={<GoalsPage />} />
            <Route path="investments" element={<InvestmentsPage />} />
            <Route path="mortgage" element={<MortgagePage />} />
            <Route path="life-events" element={<LifeEventsPage />} />
            <Route path="scenarios" element={<ScenariosPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </ReportProvider>
    </BrowserRouter>
  );
}
