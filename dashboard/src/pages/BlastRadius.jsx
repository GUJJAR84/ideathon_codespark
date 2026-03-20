import { useState, useEffect } from "react";
import { api } from "../services/api";

export default function BlastRadius() {
  const [map, setMap] = useState(null);
  const [sel, setSel] = useState(null);
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [impLoading, setImpLoading] = useState(false);

  useEffect(() => {
    api.getContagionMap().then(setMap).catch(() => {}).finally(() => setLoading(false));
  }, []);

  async function pick(name) {
    setSel(name);
    setImpLoading(true);
    try { setImpact(await api.getImpact(name)); }
    catch { setImpact(null); }
    finally { setImpLoading(false); }
  }

  const iconFor = (n) => {
    if (n.includes("AWS")) return "☁️";
    if (n.includes("Azure")) return "🔷";
    if (n.includes("GCP")) return "🟢";
    if (n.includes("Pay") || n.includes("Razor")) return "💳";
    if (n.includes("Cloud") || n.includes("Akamai")) return "🌐";
    if (n.includes("SAP") || n.includes("Sales")) return "🏢";
    if (n.includes("Mongo") || n.includes("Snow")) return "🗄️";
    return "🔌";
  };

  if (loading) return <div className="loading"><div className="spinner" /><div>Loading dependency network...</div></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>Blast Radius</h2>
          <p>What happens when a dependency goes down?</p>
        </div>
        {map && (
          <div style={{ display: "flex", gap: 20, fontSize: 13, color: "var(--text-muted)" }}>
            <span>🏢 {map.nodes?.length} vendors</span>
            <span>🔗 {map.edges?.length} connections</span>
            <span>☁️ {map.dependencies?.length} dependencies</span>
          </div>
        )}
      </div>

      {/* Dependency Grid */}
      <div className="dep-grid" style={{ marginBottom: 28 }}>
        {(map?.dependencies || []).map(dep => (
          <div
            key={dep.name}
            className={`dep-node ${dep.status === "RISK" ? "at-risk" : "healthy"} ${sel === dep.name ? "selected" : ""}`}
            onClick={() => pick(dep.name)}
          >
            <div className="dep-icon">{iconFor(dep.name)}</div>
            <div className="dep-name">{dep.name}</div>
            <div className="dep-count">{dep.connected_vendors?.length || 0} vendors</div>
            <span className={`badge ${dep.status === "RISK" ? "badge-critical" : "badge-low"}`} style={{ marginTop: 6, fontSize: 9 }}>
              {dep.status === "RISK" ? "⚠ AT RISK" : "✓ OK"}
            </span>
          </div>
        ))}
      </div>

      {/* Impact */}
      {impLoading && <div className="loading"><div className="spinner" /><div>Calculating blast radius...</div></div>}

      {impact && !impLoading && (
        <div className="slide-up">
          {/* Known Issues */}
          {impact.known_issues?.length > 0 && (
            <div className="card glow-critical" style={{ marginBottom: 16, borderLeft: "3px solid var(--critical)" }}>
              <div style={{ fontWeight: 700, marginBottom: 8, color: "var(--critical)" }}>🚨 Active Issues for {impact.dependency}</div>
              {impact.known_issues.map((issue, i) => (
                <div key={i} style={{ fontSize: 13, color: "var(--text-secondary)", padding: "4px 0" }}>• {issue}</div>
              ))}
            </div>
          )}

          {/* Impact Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
            <div className="impact-card">
              <div style={{ fontSize: 24, marginBottom: 4 }}>🏢</div>
              <div className="impact-value" style={{ color: "var(--critical)" }}>{impact.blast_radius.affected_vendors}</div>
              <div className="impact-label">Affected</div>
            </div>
            <div className="impact-card">
              <div style={{ fontSize: 24, marginBottom: 4 }}>🔴</div>
              <div className="impact-value" style={{ color: "var(--high)" }}>{impact.blast_radius.critical_vendors}</div>
              <div className="impact-label">Critical</div>
            </div>
            <div className="impact-card">
              <div style={{ fontSize: 24, marginBottom: 4 }}>💰</div>
              <div className="impact-value" style={{ color: "var(--medium)" }}>₹{impact.blast_radius.total_contract_value_cr}</div>
              <div className="impact-label">Crore Exposure</div>
            </div>
            <div className="impact-card">
              <div style={{ fontSize: 24, marginBottom: 4 }}>✅</div>
              <div className="impact-value" style={{ color: "var(--low)" }}>{impact.blast_radius.affected_vendors - impact.blast_radius.critical_vendors}</div>
              <div className="impact-label">Non-Critical</div>
            </div>
          </div>

          {/* Table */}
          <div className="card">
            <div className="card-header"><span className="card-title">Impacted Vendors</span></div>
            <table className="data-table">
              <thead><tr><th>Vendor</th><th>Tier</th><th>Category</th><th>Exposure</th></tr></thead>
              <tbody>
                {(impact.affected_vendors || []).sort((a, b) => b.contract_value - a.contract_value).map(v => (
                  <tr key={v.vendor_id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{v.name}</div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{v.vendor_id}</div>
                    </td>
                    <td><span className={`badge badge-tier-${v.tier.toLowerCase()}`}>{v.tier}</span></td>
                    <td style={{ color: "var(--text-secondary)", fontSize: 12 }}>{v.category}</td>
                    <td style={{ fontWeight: 700 }}>₹{(v.contract_value / 100000).toFixed(0)}L</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!impact && !impLoading && (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.5 }}>💥</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Select a dependency above</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>See how many vendors are affected if it goes down</div>
        </div>
      )}
    </div>
  );
}
