// Lớp gọi API: gom xử lý lỗi (mất kết nối, timeout, lỗi 4xx/5xx) ở một chỗ.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

async function request(path, options = {}, timeoutMs = 20000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...options, signal: ctrl.signal });
  } catch (e) {
    if (e.name === "AbortError") throw new Error("Máy chủ phản hồi quá lâu. Hãy thử lại.");
    throw new Error("Không kết nối được máy chủ. Hãy kiểm tra kết nối mạng hoặc cấu hình API.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return null;
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* không phải JSON */
  }
  if (!res.ok) throw new Error(body?.detail || `Lỗi ${res.status}`);
  return body;
}

const json = (method, data) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

export const api = {
  health: () => request("/api/health"),
  categories: () => request("/api/categories").then((r) => r.categories),
  stats: (month) => request(`/api/stats?month=${month}`),
  insights: (month) => request(`/api/insights?month=${month}`),
  transactions: (params) => request(`/api/transactions?${new URLSearchParams(params)}`).then((r) => r.items),
  addTransaction: (tx) => request("/api/transactions", json("POST", tx)),
  updateTransaction: (id, tx) => request(`/api/transactions/${id}`, json("PUT", tx)),
  deleteTransaction: (id) => request(`/api/transactions/${id}`, { method: "DELETE" }),
  budgets: () => request("/api/budgets").then((r) => r.budgets),
  setBudget: (category, monthly_limit) =>
    request(`/api/budgets/${encodeURIComponent(category)}`, json("PUT", { monthly_limit })),
  scan: (file, engine) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("engine", engine);
    return request("/api/invoices/scan", { method: "POST", body: fd }, 90000);
  },
  saveInvoice: (inv) => request("/api/invoices", json("POST", inv)),
};
