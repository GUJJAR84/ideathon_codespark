import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../services/api";

const rc = (l) => (l || "").toLowerCase();

export default function VendorDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const [a, t] = await Promise.all([
          api.assessVendor(id, "balanced"),
          api.getTrend(id).catch(() => null),
        ]);
        setData(a);
        setTrend(t);
      } catch (e) { setError(e.message); }
      finally { setLoading(false); }
    })();
  }, [id]);

  if (loading) return <div className="loading"><div className="spinner" /><div>Analyzing {id}...</div></div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return null;

  const c = data.components;
  const modules = [
    { key: "news", label: "News", icon: "📰", ...c.news_sentiment },
    { key: "compliance", label: "Compliance", icon: "📋", ...c.compliance },
    { key: "financial", label: "Financial", icon: "💰", ...c.financial_health },
    { key: "fourth_party", label: "4th Party", icon: "🔗", ...c.fourth_party },
  ];

  return (
    <div className="fade-in">
      <button className="btn btn-sm" onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>← Back</button>

      {/* Hero */}
      <div className="card" style={{ display: "flex", alignItems: "center", gap: 28, marginBottom: 20, padding: 28 }}>
        <div className="score-circle">
          <span className="score-number" style={{ color: `var(--${rc(data.risk_level)})` }}>{data.overall_risk_score}</span>
          <span className="score-label">Risk</span>
        </div>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6 }}>{data.vendor_name}</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span className={`badge badge-tier-${rc(data.vendor_tier)}`}>{data.vendor_tier}</span>
            <span className={`badge badge-${rc(data.risk_level)}`}>{data.risk_level}</span>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{id} · {data.risk_profile_used}</span>
          </div>
        </div>
        {trend?.status === "ok" && (
          <div style={{ textAlign: "right", padding: "8px 16px", borderRadius: 12, background: trend.direction === "WORSENING" ? "var(--critical-bg)" : trend.direction === "IMPROVING" ? "var(--low-bg)" : "var(--medium-bg)" }}>
            <div style={{ fontSize: 22, marginBottom: 2 }}>{trend.direction === "WORSENING" ? "📈" : trend.direction === "IMPROVING" ? "📉" : "➡️"}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: `var(--${trend.direction === "WORSENING" ? "critical" : trend.direction === "IMPROVING" ? "low" : "medium"})` }}>{trend.direction}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{trend.delta > 0 ? "+" : ""}{trend.delta}</div>
          </div>
        )}
      </div>

      {/* Module Score Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
        {modules.map(m => (
          <div key={m.key} className="module-card" style={{ borderTop: `3px solid var(--${rc(m.level)})` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div className="module-icon">{m.icon}</div>
              <span className={`badge badge-${rc(m.level)}`} style={{ fontSize: 9 }}>{m.level}</span>
            </div>
            <div className="module-name">{m.label}</div>
            <div className="module-score" style={{ color: `var(--${rc(m.level)})` }}>{m.score}</div>
            <div className="risk-bar" style={{ height: 4, marginTop: 4 }}>
              <div className={`risk-bar-fill ${rc(m.level)}`} style={{ width: `${m.score}%` }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 10, color: "var(--text-muted)" }}>
              <span>Conf: {m.confidence}%</span>
              <span>{m.cadence?.replace("_", " ")}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid-2">
        {/* Alerts */}
        <div className="card">
          <div className="card-header"><span className="card-title">⚠️ Alerts ({(data.alerts || []).length})</span></div>
          {!(data.alerts || []).length ? (
            <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted)" }}>✅ No alerts</div>
          ) : (
            (data.alerts || []).map((a, i) => (
              <div key={i} className="alert-item">
                <div className="alert-icon" style={{ background: `var(--${rc(a.severity || a.type)}-bg)` }}>
                  {a.type === "COMPLIANCE" ? "📋" : a.type === "FINANCIAL" ? "💰" : "⚠️"}
                </div>
                <div>
                  <span className={`badge badge-${rc(a.severity || "medium")}`} style={{ marginRight: 6 }}>{a.type}</span>
                  <span style={{ fontSize: 13 }}>{a.message}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Remediation */}
        <div className="card">
          <div className="card-header"><span className="card-title">🔧 Remediation</span></div>
          {!(data.remediation || []).length ? (
            <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted)" }}>All clear</div>
          ) : (
            (data.remediation || []).map((r, i) => (
              <div key={i} className="alert-item">
                <div className="alert-icon" style={{ background: "var(--accent-glow)", color: "var(--accent)", fontWeight: 800, fontSize: 14 }}>{i + 1}</div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{r.action}</div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                    <span className={`badge badge-${rc(r.priority)}`}>{r.priority}</span>
                    {r.timeline && <span style={{ marginLeft: 8 }}>{r.timeline}</span>}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Contagion */}
      {(data.contagion_links || []).length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header"><span className="card-title">🔗 Shared Dependencies</span></div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {data.contagion_links.map((l, i) => (
              <div key={i} className="dep-node at-risk" style={{ minWidth: 160, cursor: "default" }}>
                <div className="dep-icon">☁️</div>
                <div className="dep-name">{l.shared_dependency}</div>
                <div style={{ marginTop: 6, display: "flex", gap: 4, flexWrap: "wrap", justifyContent: "center" }}>
                  {(l.linked_vendors || []).slice(0, 5).map(vid => (
                    <span key={vid} className="badge badge-medium" style={{ cursor: "pointer", fontSize: 9 }}
                      onClick={() => navigate(`/vendor/${vid}`)}>{vid}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
