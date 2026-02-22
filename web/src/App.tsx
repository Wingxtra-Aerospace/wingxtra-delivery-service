import { Navigate, Route, Routes } from "react-router-dom";
import { Navigation } from "./components/Navigation";
import { HomePage } from "./pages/HomePage";
import { JobsPage } from "./pages/JobsPage";
import { OpsConsolePage } from "./pages/OpsConsolePage";
import { OrdersPage } from "./pages/OrdersPage";
import { TrackingPage } from "./pages/TrackingPage";

export default function App() {
  return (
    <div className="app-shell">
      <Navigation />
      <main className="app-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/tracking" element={<TrackingPage />} />
          <Route path="/ops-console" element={<OpsConsolePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
