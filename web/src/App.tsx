import { Navigate, Route, Routes } from "react-router-dom";
import { Navigation } from "./components/Navigation";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { HomePage } from "./pages/HomePage";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { OpsConsolePage } from "./pages/OpsConsolePage";
import { OrderDetailPage } from "./pages/OrderDetailPage";
import { OrdersPage } from "./pages/OrdersPage";
import { TrackingPage } from "./pages/TrackingPage";

export default function App() {
  return (
    <div className="app-shell">
      <Navigation />
      <main className="app-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/orders"
            element={
              <ProtectedRoute roles={["MERCHANT", "ADMIN"]}>
                <OrdersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders/:orderId"
            element={
              <ProtectedRoute roles={["MERCHANT", "ADMIN"]}>
                <OrderDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs"
            element={
              <ProtectedRoute roles={["OPS", "ADMIN"]}>
                <JobsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tracking"
            element={
              <ProtectedRoute roles={["MERCHANT", "ADMIN"]}>
                <TrackingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ops-console"
            element={
              <ProtectedRoute roles={["OPS", "ADMIN"]}>
                <OpsConsolePage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
