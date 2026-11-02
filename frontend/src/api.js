// Lớp gọi API: gom xử lý lỗi (mất kết nối, timeout, lỗi 4xx/5xx) ở một chỗ.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

// ---- phiên đăng nhập: token lưu trong localStorage của trình duyệt
const TOKEN_KEY = "chitieu_token";
let unauthorizedHandler = null;

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token) {
  try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY); } catch { /* bỏ qua */ }
}
// App đăng ký hàm này để tự quay về màn hình đăng nhập khi token hết hạn / không hợp lệ
export function onUnauthorized(fn) { unauthorizedHandler = fn; }

async function request(path, options = {}, timeoutMs = 20000) {
  const { public: isPublic, ...fetchOptions } = options;
  const headers = { ...(fetchOptions.headers || {}) };
  const token = getToken();
  if (token && !isPublic) headers.Authorization = `Bearer ${token}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...fetchOptions, headers, signal: ctrl.signal });
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
  if (!res.ok) {
    if (res.status === 401 && !isPublic && token) {
      setToken(null);
      unauthorizedHandler?.();
    }
    const err = new Error(body?.detail || `Lỗi ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

const json = (method, data) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

const AUTH_TIMEOUT = 60000; // lần đầu sau khi máy chủ "ngủ" có thể mất gần một phút

export const api = {
  health: () => request("/api/health", {}, AUTH_TIMEOUT),
  login: (email, password) =>
    request("/api/auth/login", { ...json("POST", { email, password }), public: true }, AUTH_TIMEOUT),
  register: (name, email, password) =>
    request("/api/auth/register", { ...json("POST", { name, email, password }), public: true }, AUTH_TIMEOUT),
  me: () => request("/api/auth/me", {}, AUTH_TIMEOUT).then((r) => r.user),
  seedDemo: () => request("/api/demo/seed", { method: "POST" }),
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
