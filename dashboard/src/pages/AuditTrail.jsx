import { useState, useEffect } from "react";
import { api } from "../services/api";

const rc = (l) => (l || "").toLowerCase();

export default function AuditTrail() {
  const [entries, setEntries] = useState([]);
  const [filter, setFilter] = useState("");
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => load(), 300);
    return () => clearTimeout(timer);
  }, [filter]);

  async function load() {
    setLoading(true);
    try {
      const d = await api.getAuditTrail(filter || null, 100);
      setEntries(d.entries);
      setTotal(d.total);
    } catch { setEntries([]); }
    finally { setLoading(false); }
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>Audit Trail</h2>
          <p>Immutable log of every AI decision — RBI compliant</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input placeholder="Filter by Vendor ID..." value={filter} onChange={e => setFilter(e.target.value)} />
          </div>
          <button className="btn" onClick={load}>↻ Refresh</button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-icon">📋</div>
          <div className="stat-value">{total}</div>
          <div className="stat-label">Total Decisions</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">⚠️</div>
          <div className="stat-value" style={{ color: "var(--critical)" }}>{entries.filter(e => e.output?.requires_human_review).length}</div>
          <div className="stat-label">Needs Review</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🤖</div>
          <div className="stat-value" style={{ color: "var(--low)" }}>{entries.filter(e => !e.output?.requires_human_review).length}</div>
          <div className="stat-label">Auto-Approved</div>
        </div>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /><div>Loading audit trail...</div></div>
      ) : entries.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.4 }}>📋</div>
          <div>No entries found. Run assessments to generate audit data.</div>
        </div>
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Vendor</th>
                <th>Module</th>
                <th>Score</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: "monospace", fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                    {new Date(e.timestamp).toLocaleString()}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{e.vendor_id}</div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{e.vendor_name}</div>
                  </td>
                  <td>
                    <span className="badge" style={{ background: "var(--accent-glow)", color: "var(--accent)" }}>
                      {e.module?.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontWeight: 800, fontSize: 16, color: `var(--${rc(e.output?.level)})` }}>{e.output?.score}</span>
                    <span style={{ fontSize: 10, color: "var(--text-muted)" }}>/100</span>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{ width: 40, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                        <div style={{ width: `${e.output?.confidence || 0}%`, height: "100%", borderRadius: 2, background: `var(--${e.output?.confidence >= 80 ? "low" : e.output?.confidence >= 50 ? "medium" : "critical"})` }} />
                      </div>
                      <span style={{ fontSize: 12 }}>{e.output?.confidence}%</span>
                    </div>
                  </td>
                  <td>
                    {e.output?.requires_human_review ? (
                      <span className="badge badge-critical pulse" style={{ fontSize: 9 }}>⚠ REVIEW</span>
                    ) : (
                      <span className="badge badge-low" style={{ fontSize: 9 }}>✓ AUTO</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
