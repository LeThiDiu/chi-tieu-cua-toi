import { useCallback, useEffect, useState } from "react";
import { api, getToken, onUnauthorized, setToken } from "./api.js";
import { monthLabel, shiftMonth, thisMonth } from "./format.js";
import Auth from "./components/Auth.jsx";
import Dashboard from "./components/Dashboard.jsx";
import Scan from "./components/Scan.jsx";
import Transactions from "./components/Transactions.jsx";
import Budgets from "./components/Budgets.jsx";

const TABS = [
  ["dashboard", "Tổng quan"],
  ["scan", "Quét hóa đơn"],
  ["transactions", "Giao dịch"],
  ["budgets", "Ngân sách"],
];

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [month, setMonth] = useState(thisMonth());
  const [categories, setCategories] = useState([]);
  const [health, setHealth] = useState({ state: "loading" });
  const [refreshKey, setRefreshKey] = useState(0);
  const [installPrompt, setInstallPrompt] = useState(null);
  // auth.status: "checking" (đang xác minh token đã lưu) | "in" | "out" | "error" (chưa kiểm tra được vì mạng)
  const [auth, setAuth] = useState(() => ({ status: getToken() ? "checking" : "out", user: null, expired: false }));
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  const loadHealth = useCallback(() => {
    setHealth({ state: "loading" });
    api
      .health()
      .then((h) => {
        setHealth({ state: "ok", ...h });
        return api.categories();
      })
      .then(setCategories)
      .catch((e) => setHealth({ state: "down", message: e.message }));
  }, []);

  useEffect(() => { loadHealth(); }, [loadHealth]);

  // token hết hạn / bị từ chối ở bất kỳ API nào -> về màn hình đăng nhập
  useEffect(() => {
    onUnauthorized(() => setAuth({ status: "out", user: null, expired: true }));
  }, []);

  const checkSession = useCallback(() => {
    setAuth({ status: "checking", user: null, expired: false });
    api
      .me()
      .then((user) => setAuth({ status: "in", user, expired: false }))
      .catch((e) => {
        if (e.status === 401) { setToken(null); setAuth({ status: "out", user: null, expired: true }); }
        else setAuth({ status: "error", user: null, expired: false, message: e.message });
      });
  }, []);

  useEffect(() => {
    if (getToken()) checkSession();
  }, [checkSession]);

  function handleAuth(token, user) {
    setToken(token);
    setTab("dashboard");
    setMonth(thisMonth());
    setAuth({ status: "in", user, expired: false });
  }

  function logout() {
    setToken(null);
    setTab("dashboard");
    setAuth({ status: "out", user: null, expired: false });
  }

  useEffect(() => {
    const onInstallAvailable = (event) => {
      event.preventDefault();
      setInstallPrompt(event);
    };
    const onInstalled = () => setInstallPrompt(null);
    window.addEventListener("beforeinstallprompt", onInstallAvailable);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onInstallAvailable);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  async function installApp() {
    if (!installPrompt) return;
    await installPrompt.prompt();
    setInstallPrompt(null);
  }

  if (auth.status === "checking") {
    return <main className="auth-shell"><p className="muted">Đang kiểm tra phiên đăng nhập… lần đầu có thể mất khoảng một phút.</p></main>;
  }
  if (auth.status === "error") {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="banner error" role="alert">{auth.message}</div>
          <button className="primary" onClick={checkSession}>Thử lại</button>
          <p className="auth-switch"><button className="link" onClick={logout}>Đăng nhập bằng tài khoản khác</button></p>
        </section>
      </main>
    );
  }
  if (auth.status !== "in") {
    return (
      <Auth onAuth={handleAuth} expired={auth.expired} onRetry={loadHealth}
        serverError={health.state === "down" ? health.message : ""} />
    );
  }

  const initial = (auth.user.name || auth.user.email || "?").trim().charAt(0).toUpperCase();

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><span className="brand-mark">CT</span><span>Chi tiêu của tôi</span></div>
        <nav className="nav" aria-label="Chức năng chính">
          {TABS.map(([id, label]) => (
            <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}
              aria-current={tab === id ? "page" : undefined}>
              <span className={`nav-icon icon-${id}`} aria-hidden="true" />
              {label}
            </button>
          ))}
        </nav>
        <div className="month-picker" aria-label="Chọn tháng">
          <button onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Tháng trước">‹</button>
          <span>{monthLabel(month)}</span>
          <button onClick={() => setMonth(shiftMonth(month, 1))} aria-label="Tháng sau">›</button>
        </div>
        <div className="user-box">
          <span className="user-avatar" aria-hidden="true">{initial}</span>
          <div className="user-info"><strong>{auth.user.name}</strong><small>{auth.user.email}</small></div>
          <button className="logout" onClick={logout}>Đăng xuất</button>
        </div>
      </aside>

      <main className="main">
        <header className="app-header">
          <div className="mobile-brand"><span className="brand-mark">CT</span><div><strong>Chi tiêu của tôi</strong><small>Quản lý tài chính cá nhân</small></div></div>
          <div className="header-actions">
            {installPrompt && <button className="install-button" onClick={installApp}>＋ Cài ứng dụng</button>}
            <button className="install-button logout-mobile" onClick={logout}>Đăng xuất</button>
          </div>
        </header>
        <div className="month-picker-mobile" aria-label="Chọn tháng">
          <button onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Tháng trước">‹</button>
          <span>{monthLabel(month)}</span>
          <button onClick={() => setMonth(shiftMonth(month, 1))} aria-label="Tháng sau">›</button>
        </div>
        {health.state === "down" && (
          <div className="banner error" role="alert">{health.message}</div>
        )}
        {health.state === "ok" && !health.model_ready && (
          <div className="banner warn" role="alert">
            Chưa có model phân loại danh mục. Chạy <code>cd model &amp;&amp; python train_export.py</code> rồi khởi động lại backend.
          </div>
        )}
        {tab === "dashboard" && (
          <Dashboard month={month} refreshKey={refreshKey} goScan={() => setTab("scan")}
            userName={auth.user.name} onSeeded={refresh} />
        )}
        {tab === "scan" && (
          <Scan categories={categories} geminiReady={!!health.gemini_configured}
            onSaved={() => { refresh(); setTab("transactions"); }} />
        )}
        {tab === "transactions" && <Transactions month={month} categories={categories} refreshKey={refreshKey} onChange={refresh} />}
        {tab === "budgets" && <Budgets onChange={refresh} />}
      </main>
    </div>
  );
}
