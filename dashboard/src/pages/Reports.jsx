import { useState, useEffect } from "react";
import Markdown from "react-markdown";
import { api } from "../services/api";

export default function Reports() {
  const [vendors, setVendors] = useState([]);
  const [vendor, setVendor] = useState("");
  const [lang, setLang] = useState("english");
  const [fmt, setFmt] = useState("summary");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.getVendors().then(d => setVendors(d.vendors)).catch(() => {}); }, []);

  async function generate() {
    if (!vendor) return;
    setLoading(true); setReport(null);
    try { setReport(await api.getReport(vendor, lang, fmt)); }
    catch (e) { setReport({ error: e.message }); }
    finally { setLoading(false); }
  }

  function handlePrint() {
    window.print();
  }

  const reportText = report && !report.error
    ? (typeof report.report === "string" ? report.report : JSON.stringify(report.report, null, 2))
    : "";

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>Report Generator</h2>
          <p>AI-powered compliance reports in English & Hindi</p>
        </div>
      </div>

      {/* Controls */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <select className="select" value={vendor} onChange={e => setVendor(e.target.value)} style={{ minWidth: 240 }}>
            <option value="">Select Vendor...</option>
            {vendors.map(v => <option key={v.vendor_id} value={v.vendor_id}>{v.vendor_id} — {v.name}</option>)}
          </select>
          <div style={{ display: "flex", gap: 4, background: "rgba(15,23,42,0.8)", borderRadius: 10, padding: 3, border: "1px solid var(--border)" }}>
            <button className={lang === "english" ? "btn btn-sm btn-primary" : "btn btn-sm"} onClick={() => setLang("english")} style={{ border: "none" }}>🇬🇧 EN</button>
            <button className={lang === "hindi" ? "btn btn-sm btn-primary" : "btn btn-sm"} onClick={() => setLang("hindi")} style={{ border: "none" }}>🇮🇳 HI</button>
          </div>
          <div style={{ display: "flex", gap: 4, background: "rgba(15,23,42,0.8)", borderRadius: 10, padding: 3, border: "1px solid var(--border)" }}>
            <button className={fmt === "summary" ? "btn btn-sm btn-primary" : "btn btn-sm"} onClick={() => setFmt("summary")} style={{ border: "none" }}>📝 Summary</button>
            <button className={fmt === "rbi_audit" ? "btn btn-sm btn-primary" : "btn btn-sm"} onClick={() => setFmt("rbi_audit")} style={{ border: "none" }}>🏛️ RBI Audit</button>
          </div>
          <button className="btn btn-primary" onClick={generate} disabled={!vendor || loading}>
            {loading ? "⏳ Generating..." : "⚡ Generate"}
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="loading">
          <div className="spinner" />
          <div>Generating with Gemini AI...</div>
          <div style={{ fontSize: 12, marginTop: 6, color: "var(--text-muted)" }}>This takes 10-20 seconds</div>
        </div>
      )}

      {/* Report Output */}
      {report && !report.error && (
        <div className="slide-up">
          {/* Report Header Bar */}
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "14px 24px", borderRadius: "16px 16px 0 0",
            background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(168,85,247,0.1))",
            border: "1px solid var(--border)", borderBottom: "none",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--accent-gradient)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, boxShadow: "0 4px 12px rgba(99,102,241,0.3)" }}>
                {fmt === "rbi_audit" ? "🏛️" : "📄"}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{report.vendor_name}</div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "var(--text-muted)" }}>
                  <span>{fmt === "rbi_audit" ? "RBI Audit-Ready Report" : "Summary Report"}</span>
                  <span>·</span>
                  <span>{lang === "hindi" ? "हिंदी" : "English"}</span>
                  <span>·</span>
                  <span>{new Date(report.generated_at).toLocaleString()}</span>
                </div>
              </div>
            </div>
            <button className="btn btn-sm" onClick={handlePrint}>🖨️ Print / PDF</button>
          </div>

          {/* Report Body — Rendered Markdown */}
          <div className="report-body">
            <Markdown
              components={{
                h1: ({ children }) => <h1 className="rpt-h1">{children}</h1>,
                h2: ({ children }) => <h2 className="rpt-h2">{children}</h2>,
                h3: ({ children }) => <h3 className="rpt-h3">{children}</h3>,
                h4: ({ children }) => <h4 className="rpt-h4">{children}</h4>,
                p: ({ children }) => <p className="rpt-p">{children}</p>,
                ul: ({ children }) => <ul className="rpt-ul">{children}</ul>,
                ol: ({ children }) => <ol className="rpt-ol">{children}</ol>,
                li: ({ children }) => <li className="rpt-li">{children}</li>,
                strong: ({ children }) => <strong className="rpt-strong">{children}</strong>,
                hr: () => <hr className="rpt-hr" />,
                blockquote: ({ children }) => <blockquote className="rpt-blockquote">{children}</blockquote>,
                table: ({ children }) => <table className="rpt-table">{children}</table>,
                th: ({ children }) => <th className="rpt-th">{children}</th>,
                td: ({ children }) => <td className="rpt-td">{children}</td>,
              }}
            >
              {reportText}
            </Markdown>
          </div>
        </div>
      )}

      {report?.error && <div className="error-box">{report.error}</div>}

      {!report && !loading && (
        <div style={{ textAlign: "center", padding: 80, color: "var(--text-muted)" }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.4 }}>📄</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Select a vendor to generate a report</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>Choose RBI Audit format for regulatory submissions</div>
        </div>
      )}
    </div>
  );
}
