import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Dashboard from "./pages/Dashboard";
import VendorDetail from "./pages/VendorDetail";
import BlastRadius from "./pages/BlastRadius";
import Reports from "./pages/Reports";
import AuditTrail from "./pages/AuditTrail";
import "./index.css";

function Sidebar() {
  const links = [
    { path: "/", icon: "📊", label: "Dashboard" },
    { path: "/blast-radius", icon: "💥", label: "Blast Radius" },
    { path: "/reports", icon: "📄", label: "Reports" },
    { path: "/audit", icon: "🔍", label: "Audit Trail" },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">🛡️</div>
        <div>
          <h1>VendorGuard AI</h1>
          <span>Risk Assessment Engine</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {links.map((l) => (
          <NavLink
            key={l.path}
            to={l.path}
            end={l.path === "/"}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            <span className="nav-icon">{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div style={{ fontWeight: 600, marginBottom: 2 }}>v2.0 Production</div>
        <div>Powered by Gemini AI</div>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/vendor/:id" element={<VendorDetail />} />
              <Route path="/blast-radius" element={<BlastRadius />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/audit" element={<AuditTrail />} />
              <Route path="*" element={
                <div className="loading">
                  <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
                  <h3>Page Not Found</h3>
                  <p style={{ marginTop: 8, color: "var(--text-muted)" }}>The page you're looking for doesn't exist.</p>
                </div>
              } />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </BrowserRouter>
  );
}
