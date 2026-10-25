import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { monthLabel, shiftMonth, thisMonth } from "./format.js";
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
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth({ state: "ok", ...h });
        return api.categories();
      })
      .then(setCategories)
      .catch((e) => setHealth({ state: "down", message: e.message }));
  }, []);

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
      </aside>

      <main className="main">
        <header className="app-header">
          <div className="mobile-brand"><span className="brand-mark">CT</span><div><strong>Chi tiêu của tôi</strong><small>Quản lý tài chính cá nhân</small></div></div>
          {installPrompt && <button className="install-button" onClick={installApp}>＋ Cài ứng dụng</button>}
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
        {tab === "dashboard" && <Dashboard month={month} refreshKey={refreshKey} goScan={() => setTab("scan")} />}
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
