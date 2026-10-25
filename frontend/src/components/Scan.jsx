import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { today, vnd } from "../format.js";

const ENGINES = [
  ["auto", "Tự động (ưu tiên Gemini)"],
  ["gemini", "Gemini Vision"],
  ["tesseract", "Tesseract OCR (offline)"],
];
let rowId = 0;
const newRow = (r = {}) => ({
  key: ++rowId, name: "", quantity: 1, amount: "", category: "Khác", confidence: null,
  predicted_category: null, check: false, ...r,
});

export default function Scan({ categories, geminiReady, onSaved }) {
  const [file, setFile] = useState(null);
  const [engine, setEngine] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null); // {engine, elapsed_ms, warnings, total}
  const [store, setStore] = useState("");
  const [date, setDate] = useState(today());
  const [rows, setRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const sum = rows.reduce((s, r) => s + (Number(r.amount) || 0), 0);

  async function doScan() {
    setError(""); setResult(null); setRows([]);
    if (!file) return setError("Hãy chọn hoặc chụp một ảnh hóa đơn trước.");
    setBusy(true);
    try {
      const r = await api.scan(file, engine);
      setResult(r);
      setStore(r.store_name || "");
      setDate(r.date);
      setRows(r.items.map((i) => newRow({ ...i, predicted_category: i.category })));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const patch = (key, p) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

  async function save() {
    setError("");
    if (rows.length === 0) return setError("Chưa có dòng nào để lưu.");
    for (const [i, r] of rows.entries()) {
      if (!r.name.trim()) return setError(`Dòng ${i + 1}: tên sản phẩm đang trống.`);
      if (!(Number(r.amount) > 0)) return setError(`Dòng ${i + 1}: thành tiền phải lớn hơn 0.`);
      if (!(Number(r.quantity) > 0)) return setError(`Dòng ${i + 1}: số lượng phải lớn hơn 0.`);
    }
    setSaving(true);
    try {
      await api.saveInvoice({
        store_name: store.trim() || null, date, engine: result?.engine || null,
        items: rows.map((r) => ({
          name: r.name.trim(), quantity: Number(r.quantity), amount: Math.round(Number(r.amount)),
          category: r.category, predicted_category: r.predicted_category,
        })),
      });
      onSaved();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <h1>Quét hóa đơn</h1>
      <div className="scan-layout">
        <section className="card picker">
          <h2>1. Chọn ảnh hóa đơn</h2>
          <input ref={inputRef} type="file" accept="image/*" capture="environment" hidden
            onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); setRows([]); setError(""); }} />
          <button className="secondary" onClick={() => inputRef.current?.click()}>
            {file ? "Chọn ảnh khác" : "Chụp hoặc chọn ảnh"}
          </button>
          {preview && <img className="thumb" src={preview} alt="Ảnh hóa đơn đã chọn" />}
          <label className="field">
            <span>Cách đọc</span>
            <select value={engine} onChange={(e) => setEngine(e.target.value)}>
              {ENGINES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          {!geminiReady && engine !== "tesseract" && (
            <p className="hint">Chưa cấu hình GEMINI_API_KEY nên chế độ tự động sẽ dùng Tesseract.</p>
          )}
          <button className="primary" onClick={doScan} disabled={busy}>
            {busy ? "Đang đọc hóa đơn…" : "Đọc hóa đơn"}
          </button>
          <p className="hint">Ảnh sẽ được gửi tới máy chủ của bạn{engine !== "tesseract" && geminiReady ? " và tới Google Gemini để đọc" : ""}. Không chụp thông tin cá nhân nhạy cảm.</p>
        </section>

        <section className="result">
          <h2>2. Kiểm tra và sửa kết quả</h2>
          {error && <div className="banner error" role="alert">{error}</div>}
          {!result && !busy && <p className="muted">Kết quả đọc sẽ hiện ở đây dưới dạng một tờ hóa đơn bạn có thể chỉnh sửa trước khi lưu.</p>}
          {busy && <p className="muted" aria-live="polite">Đang xử lý ảnh, thường mất vài giây…</p>}

          {result && (
            <div className="receipt-wrap">
              <div className="receipt">
                <div className="r-head">
                  <input className="r-store" value={store} placeholder="Tên cửa hàng" onChange={(e) => setStore(e.target.value)} aria-label="Tên cửa hàng" />
                  <input className="r-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Ngày trên hóa đơn" />
                </div>
                <div className="r-cols"><span>Sản phẩm</span><span>SL</span><span>Thành tiền</span><span>Danh mục</span><span /></div>
                {rows.map((r) => (
                  <div key={r.key} className={`r-row ${r.check ? "check" : ""}`}>
                    <input value={r.name} onChange={(e) => patch(r.key, { name: e.target.value })} aria-label="Tên sản phẩm" />
                    <input type="number" min="0" step="any" value={r.quantity} onChange={(e) => patch(r.key, { quantity: e.target.value })} aria-label="Số lượng" />
                    <input type="number" min="0" value={r.amount} onChange={(e) => patch(r.key, { amount: e.target.value })} aria-label="Thành tiền (VND)" />
                    <div className="cat-cell">
                      <select value={r.category} onChange={(e) => patch(r.key, { category: e.target.value })} aria-label="Danh mục">
                        {categories.map((c) => <option key={c}>{c}</option>)}
                      </select>
                      {r.confidence !== null && r.category === r.predicted_category && (
                        <small className={r.confidence < 0.6 ? "low" : ""}>AI {Math.round(r.confidence * 100)}%</small>
                      )}
                    </div>
                    <button className="icon" onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))} aria-label={`Xóa dòng ${r.name || ""}`}>×</button>
                  </div>
                ))}
                <button className="link" onClick={() => setRows((rs) => [...rs, newRow({ predicted_category: null })])}>+ Thêm dòng</button>
                <div className="r-total">
                  <span>Tổng các dòng</span><strong>{vnd(sum)}</strong>
                </div>
                {result.total && result.total !== sum && (
                  <div className="r-mismatch">Tổng trên hóa đơn đọc được là {vnd(result.total)}, khác tổng các dòng. Hãy rà lại.</div>
                )}
              </div>
            </div>
          )}

          {result && result.warnings.length > 0 && (
            <ul className="warnings" aria-label="Cảnh báo khi đọc hóa đơn">
              {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
          {result && (
            <div className="actions">
              <button className="primary" onClick={save} disabled={saving}>{saving ? "Đang lưu…" : "Lưu hóa đơn"}</button>
              <span className="hint">Đọc bằng {result.engine === "gemini" ? "Gemini" : "Tesseract"} trong {(result.elapsed_ms / 1000).toFixed(1)} giây</span>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
