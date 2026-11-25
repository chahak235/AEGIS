import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth";
import { Layout } from "./components/Layout";
import { AdminPage } from "./pages/AdminPage";
import { DetectionsPage } from "./pages/DetectionsPage";
import { EventsPage } from "./pages/EventsPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SimulatorPage } from "./pages/SimulatorPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<OverviewPage />} />
            <Route path="incidents" element={<IncidentsPage />} />
            <Route path="incidents/:id" element={<IncidentDetailPage />} />
            <Route path="detections" element={<DetectionsPage />} />
            <Route path="events" element={<EventsPage />} />
            <Route path="simulator" element={<SimulatorPage />} />
            <Route path="admin" element={<RequireAuth role="admin"><AdminPage /></RequireAuth>} />
            <Route path="*" element={<div className="center">Page not found. <Link to="/">Go to Overview</Link></div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
