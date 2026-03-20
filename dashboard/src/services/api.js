const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY || "";

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
    },
  };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => request("GET", "/health"),
  getVendors: (tier, category) => {
    const params = new URLSearchParams();
    if (tier) params.set("tier", tier);
    if (category) params.set("category", category);
    const qs = params.toString();
    return request("GET", `/vendors${qs ? `?${qs}` : ""}`);
  },
  assessVendor: (id, profile = "balanced") =>
    request("GET", `/assess/${id}?profile=${profile}`),
  assessAll: (profile = "balanced") =>
    request("GET", `/assess/all?profile=${profile}`),
  getHistory: (id) => request("GET", `/history/${id}`),
  getTrend: (id) => request("GET", `/trend/${id}`),
  getReport: (id, lang = "english", format = "summary") =>
    request("GET", `/report/${id}?lang=${lang}&format=${format}`),
  getProfiles: () => request("GET", "/profiles"),
  getContagionMap: () => request("GET", "/contagion-map"),
  getImpact: (dep) => request("GET", `/contagion-map/impact?dependency=${dep}`),
  getAuditTrail: (vendorId, limit = 50) => {
    const params = new URLSearchParams({ limit });
    if (vendorId) params.set("vendor_id", vendorId);
    return request("GET", `/audit-trail?${params}`);
  },
  clearCache: () => request("POST", "/cache/clear"),
  clearVendorCache: (id) => request("POST", `/cache/clear/${id}`),
};
