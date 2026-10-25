import { useEffect, useState } from "react";
import { api } from "../api.js";
import { catColor, monthLabel, shortDate, today, vnd } from "../format.js";

export default function Transactions({ month, categories, refreshKey, onChange }) {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ date: today(), name: "", amount: "", category: "" });
  const [adding, setAdding] = useState(false);

  const load = () => {
    const params = { month };
    if (category) params.category = category;
    if (q.trim()) params.q = q.trim();
    api.transactions(params).then(setItems).catch((e) => setError(e.message));
  };
  useEffect(load, [month, category, q, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  async function add(e) {
    e.preventDefault();
    setError("");
    if (!form.name.trim()) return setError("Hãy nhập tên khoản chi.");
    if (!(Number(form.amount) > 0)) return setError("Số tiền phải lớn hơn 0.");
    setAdding(true);
    try {
      await api.addTransaction({
        date: form.date, name: form.name.trim(), amount: Math.round(Number(form.amount)),
        quantity: 1, category: form.category || null,
      });
      setForm({ ...form, name: "", amount: "" });
      onChange();
    } catch (err) {
      setError(err.message);
    } finally {
      setAdding(false);
    }
  }

  async function changeCategory(t, cat) {
    setError("");
    try {
      await api.updateTransaction(t.id, { date: t.date, name: t.name, amount: t.amount, quantity: t.quantity,
        store: t.store, note: t.note, category: cat });
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(t) {
    if (!window.confirm(`Xóa khoản "${t.name}" (${vnd(t.amount)})?`)) return;
    try {
      await api.deleteTransaction(t.id);
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  const total = items.reduce((s, t) => s + t.amount, 0);

  return (
    <>
      <h1>Giao dịch {monthLabel(month)}</h1>
      {error && <div className="banner error" role="alert">{error}</div>}

      <form className="card add-form" onSubmit={add}>
        <h2>Thêm khoản chi</h2>
        <div className="add-grid">
          <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} aria-label="Ngày" />
          <input placeholder="Tên khoản chi (vd: Cà phê sữa đá)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} aria-label="Tên khoản chi" />
          <input type="number" min="0" placeholder="Số tiền (₫)" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} aria-label="Số tiền" />
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} aria-label="Danh mục">
            <option value="">Tự phân loại bằng AI</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
          <button className="primary" disabled={adding}>Thêm</button>
        </div>
      </form>

      <div className="filters">
        <input placeholder="Tìm theo tên…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Tìm theo tên" />
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Lọc theo danh mục">
          <option value="">Tất cả danh mục</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
        <span className="grow" />
        <span className="muted">{items.length} khoản · <strong>{vnd(total)}</strong></span>
      </div>

      {items.length === 0 ? (
        <p className="muted">Không có giao dịch nào khớp bộ lọc trong tháng này.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Ngày</th><th>Khoản chi</th><th>Danh mục</th><th className="r">Thành tiền</th><th /></tr></thead>
            <tbody>
              {items.map((t) => (
                <tr key={t.id}>
                  <td>{shortDate(t.date)}</td>
                  <td>{t.name}{t.quantity !== 1 && <small> ×{t.quantity}</small>}{t.store && <small> · {t.store}</small>}</td>
                  <td>
                    <select className="cat-select" style={{ borderLeftColor: catColor(t.category) }} value={t.category}
                      onChange={(e) => changeCategory(t, e.target.value)} aria-label={`Danh mục của ${t.name}`}>
                      {categories.map((c) => <option key={c}>{c}</option>)}
                    </select>
                  </td>
                  <td className="r num">{vnd(t.amount)}</td>
                  <td className="r"><button className="icon" onClick={() => remove(t)} aria-label={`Xóa ${t.name}`}>×</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
