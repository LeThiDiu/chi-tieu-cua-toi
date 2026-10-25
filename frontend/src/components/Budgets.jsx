import { useEffect, useState } from "react";
import { api } from "../api.js";
import { catColor } from "../format.js";

export default function Budgets({ onChange }) {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.budgets().then((b) => setRows(b.map((x) => ({ ...x, value: x.monthly_limit || "" })))).catch((e) => setError(e.message));
  }, []);

  async function save(r) {
    setError(""); setMsg("");
    const v = Math.round(Number(r.value) || 0);
    if (v < 0) return setError("Ngân sách không được âm.");
    if (v === (r.monthly_limit || 0)) return;
    try {
      await api.setBudget(r.category, v);
      setRows((rs) => rs.map((x) => (x.category === r.category ? { ...x, monthly_limit: v } : x)));
      setMsg(v === 0 ? `Đã bỏ ngân sách ${r.category}.` : `Đã lưu ngân sách ${r.category}.`);
      onChange();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <>
      <h1>Ngân sách hằng tháng</h1>
      <p className="muted">Đặt hạn mức cho từng danh mục để nhận cảnh báo khi sắp vượt. Để trống hoặc 0 nếu không giới hạn.</p>
      {error && <div className="banner error" role="alert">{error}</div>}
      {msg && <div className="banner ok" aria-live="polite">{msg}</div>}
      <section className="card">
        <ul className="budget-edit">
          {rows.map((r) => (
            <li key={r.category}>
              <span className="dot" style={{ background: catColor(r.category) }} />
              <label htmlFor={`b-${r.category}`} className="grow">{r.category}</label>
              <input id={`b-${r.category}`} type="number" min="0" step="10000" placeholder="Không giới hạn" value={r.value}
                onChange={(e) => setRows((rs) => rs.map((x) => (x.category === r.category ? { ...x, value: e.target.value } : x)))}
                onBlur={() => save(r)} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
              <span className="muted">₫ / tháng</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
