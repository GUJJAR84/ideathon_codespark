import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
import { Doughnut } from "react-chartjs-2";
import { api } from "../services/api";

ChartJS.register(ArcElement, Tooltip, Legend);

const riskClass = (l) => (l || "").toLowerCase();
const tierClass = (t) => `badge-tier-${(t || "standard").toLowerCase()}`;

export default function Dashboard() {
  const [vendors, setVendors] = useState([]);
  const [assessments, setAssessments] = useState(null);
  const [profile, setProfile] = useState("balanced");
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);
  const [error, setError] = useState(null);
  const [tierFilter, setTierFilter] = useState("");
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  useEffect(() => { loadVendors(); }, [tierFilter]);
  useEffect(() => { runAssessAll(); }, []);

  async function loadVendors() {
    try {
      setLoading(true);
      const d = await api.getVendors(tierFilter || null);
      setVendors(d.vendors);
      setError(null);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function runAssessAll() {
    try {
      setAssessing(true);
      const d = await api.assessAll(profile);
      setAssessments(d);
    } catch (e) { setError(e.message); }
    finally { setAssessing(false); }
  }

  const filtered = useMemo(() => {
    if (!search) return vendors;
    const s = search.toLowerCase();
    return vendors.filter(v =>
      v.name.toLowerCase().includes(s) ||
      v.vendor_id.toLowerCase().includes(s) ||
      v.category.toLowerCase().includes(s)
    );
  }, [vendors, search]);

  const tierCounts = {
    CRITICAL: vendors.filter(v => v.tier === "CRITICAL").length,
    IMPORTANT: vendors.filter(v => v.tier === "IMPORTANT").length,
    STANDARD: vendors.filter(v => v.tier === "STANDARD").length,
  };

  const rd = assessments ? {
    CRITICAL: assessments.assessments.filter(a => a.risk_level === "CRITICAL").length,
    HIGH: assessments.assessments.filter(a => a.risk_level === "HIGH").length,
    MEDIUM: assessments.assessments.filter(a => a.risk_level === "MEDIUM").length,
    LOW: assessments.assessments.filter(a => a.risk_level === "LOW").length,
  } : null;

  const chartData = rd ? {
    labels: ["Critical", "High", "Medium", "Low"],
    datasets: [{
      data: [rd.CRITICAL, rd.HIGH, rd.MEDIUM, rd.LOW],
      backgroundColor: ["rgba(239,68,68,0.8)", "rgba(249,115,22,0.8)", "rgba(234,179,8,0.8)", "rgba(34,197,94,0.8)"],
      borderColor: ["#ef4444", "#f97316", "#eab308", "#22c55e"],
      borderWidth: 2, hoverOffset: 8, spacing: 2,
    }],
  } : null;

  const chartOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: "bottom", labels: { color: "#94a3b8", font: { family: "Inter", size: 11 }, padding: 12, usePointStyle: true, pointStyleWidth: 8 } },
    },
    cutout: "72%",
  };

  if (loading && !assessments) {
    return <div className="loading"><div className="spinner" /><div>Connecting to AI engine...</div></div>;
  }
  if (error && !vendors.length) {
    return <div className="error-box">⚠️ Cannot connect to AI engine at port 8000. Make sure it's running.</div>;
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>Risk Dashboard</h2>
          <p>{vendors.length} vendors monitored continuously</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select className="select" value={profile} onChange={e => { setProfile(e.target.value); }}>
            <option value="balanced">⚖️ Balanced</option>
            <option value="conservative">🏛️ Conservative</option>
            <option value="tech_focused">💻 Tech Focused</option>
          </select>
          <button className="btn btn-primary" onClick={runAssessAll} disabled={assessing}>
            {assessing ? "⏳ Assessing..." : "⚡ Assess All"}
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">🏢</div>
          <div className="stat-value">{vendors.length}</div>
          <div className="stat-label">Total Vendors</div>
        </div>
        <div className="stat-card" onClick={() => setTierFilter("CRITICAL")} style={{ cursor: "pointer" }}>
          <div className="stat-icon">🔴</div>
          <div className="stat-value" style={{ color: "var(--critical)" }}>{tierCounts.CRITICAL}</div>
          <div className="stat-label">Critical</div>
        </div>
        <div className="stat-card" onClick={() => setTierFilter("IMPORTANT")} style={{ cursor: "pointer" }}>
          <div className="stat-icon">🟡</div>
          <div className="stat-value" style={{ color: "var(--medium)" }}>{tierCounts.IMPORTANT}</div>
          <div className="stat-label">Important</div>
        </div>
        <div className="stat-card" onClick={() => setTierFilter("STANDARD")} style={{ cursor: "pointer" }}>
          <div className="stat-icon">🟢</div>
          <div className="stat-value" style={{ color: "var(--low)" }}>{tierCounts.STANDARD}</div>
          <div className="stat-label">Standard</div>
        </div>
        {assessments && (
          <>
            <div className="stat-card">
              <div className="stat-icon">📊</div>
              <div className="stat-value">{assessments.summary.avg_risk}</div>
              <div className="stat-label">Avg Risk</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">⚠️</div>
              <div className="stat-value" style={{ color: "var(--critical)" }}>{assessments.summary.critical}</div>
              <div className="stat-label">Critical Risk</div>
            </div>
          </>
        )}
      </div>

      {/* Chart + Top Risky */}
      {assessments && (
        <div className="grid-2" style={{ marginBottom: 24 }}>
          <div className="card">
            <div className="card-header"><span className="card-title">Risk Distribution</span></div>
            <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center" }}>
              {chartData && <Doughnut data={chartData} options={chartOpts} />}
            </div>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">Top Risk Vendors</span></div>
            {assessments.assessments
              .sort((a, b) => b.overall_risk_score - a.overall_risk_score)
              .slice(0, 5)
              .map((a, i) => (
                <div key={a.vendor_id}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: i < 4 ? "1px solid rgba(51,65,85,0.3)" : "none", cursor: "pointer" }}
                  onClick={() => navigate(`/vendor/${a.vendor_id}`)}
                >
                  <span style={{ width: 22, height: 22, borderRadius: 6, background: "var(--accent-glow)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, color: "var(--accent)", flexShrink: 0 }}>{i + 1}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.vendor_name}</div>
                    <span className={`badge ${tierClass(a.vendor_tier)}`} style={{ marginTop: 2 }}>{a.vendor_tier}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="risk-score" style={{ color: `var(--${riskClass(a.risk_level)})`, fontSize: 18 }}>{a.overall_risk_score}</div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)" }}>/100</div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Vendor Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Vendor Registry</span>
          <div style={{ display: "flex", gap: 10 }}>
            <div className="search-box">
              <span className="search-icon">🔍</span>
              <input placeholder="Search vendors..." value={search} onChange={e => setSearch(e.target.value)} />
            </div>
            <select className="select" value={tierFilter} onChange={e => setTierFilter(e.target.value)}>
              <option value="">All Tiers</option>
              <option value="CRITICAL">🔴 Critical</option>
              <option value="IMPORTANT">🟡 Important</option>
              <option value="STANDARD">🟢 Standard</option>
            </select>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Vendor</th>
              <th>Category</th>
              <th>Tier</th>
              <th>Certs</th>
              {assessments && <th>Risk</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map(v => {
              const a = assessments?.assessments.find(x => x.vendor_id === v.vendor_id);
              return (
                <tr key={v.vendor_id} onClick={() => navigate(`/vendor/${v.vendor_id}`)}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{v.name}</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{v.vendor_id}</div>
                  </td>
                  <td style={{ color: "var(--text-secondary)", fontSize: 12 }}>{v.category}</td>
                  <td><span className={`badge ${tierClass(v.tier)}`}>{v.tier}</span></td>
                  <td><span style={{ fontSize: 12, color: "var(--text-muted)" }}>{v.certifications.length} certs</span></td>
                  {a && (
                    <td>
                      <div className="risk-bar-container">
                        <div className="risk-bar">
                          <div className={`risk-bar-fill ${riskClass(a.risk_level)}`} style={{ width: `${a.overall_risk_score}%` }} />
                        </div>
                        <span className="risk-score" style={{ color: `var(--${riskClass(a.risk_level)})` }}>{a.overall_risk_score}</span>
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>No vendors match your search.</div>
        )}
      </div>
    </div>
  );
}
