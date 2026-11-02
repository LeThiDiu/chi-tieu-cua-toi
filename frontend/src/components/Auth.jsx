import { useState } from "react";
import { api } from "../api.js";

// Màn hình đăng nhập / đăng ký
export default function Auth({ onAuth, serverError, expired, onRetry }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [showPw, setShowPw] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  function switchMode() {
    setMode(isLogin ? "register" : "login");
    setErr("");
  }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    if (!isLogin) {
      if (!form.name.trim()) return setErr("Hãy nhập tên của bạn.");
      if (form.password.length < 8) return setErr("Mật khẩu cần có ít nhất 8 ký tự.");
      if (form.password !== form.confirm) return setErr("Hai mật khẩu chưa khớp nhau.");
    }
    setBusy(true);
    try {
      const res = isLogin
        ? await api.login(form.email.trim(), form.password)
        : await api.register(form.name.trim(), form.email.trim(), form.password);
      onAuth(res.token, res.user);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-brand"><span className="brand-mark">CT</span><span>Chi tiêu của tôi</span></div>
        <h1>{isLogin ? "Đăng nhập" : "Tạo tài khoản"}</h1>
        <p className="hint auth-sub">
          {isLogin ? "Đăng nhập để xem chi tiêu và ngân sách của bạn." : "Mỗi tài khoản có dữ liệu chi tiêu riêng, người khác không xem được."}
        </p>

        {expired && !err && <div className="banner warn" role="alert">Phiên đăng nhập đã hết hạn, hãy đăng nhập lại.</div>}
        {serverError && (
          <div className="banner error" role="alert">
            {serverError} Máy chủ có thể đang khởi động, hãy chờ khoảng một phút.
            <button type="button" className="link" onClick={onRetry}>Kết nối lại</button>
          </div>
        )}
        {err && <div className="banner error" role="alert">{err}</div>}

        <form className="auth-form" onSubmit={submit}>
          {!isLogin && (
            <label className="field">Tên của bạn
              <input value={form.name} onChange={set("name")} autoComplete="name" maxLength={60} required />
            </label>
          )}
          <label className="field">Email
            <input type="email" value={form.email} onChange={set("email")} autoComplete="email" required />
          </label>
          <label className="field">Mật khẩu
            <input type={showPw ? "text" : "password"} value={form.password} onChange={set("password")}
              autoComplete={isLogin ? "current-password" : "new-password"} minLength={isLogin ? undefined : 8} required />
          </label>
          {!isLogin && (
            <label className="field">Nhập lại mật khẩu
              <input type={showPw ? "text" : "password"} value={form.confirm} onChange={set("confirm")}
                autoComplete="new-password" required />
            </label>
          )}
          <label className="check">
            <input type="checkbox" checked={showPw} onChange={(e) => setShowPw(e.target.checked)} /> Hiện mật khẩu
          </label>
          <button className="primary" disabled={busy}>
            {busy ? "Đang xử lý…" : isLogin ? "Đăng nhập" : "Tạo tài khoản"}
          </button>
          {busy && <p className="hint">Lần đầu có thể mất khoảng một phút nếu máy chủ đang khởi động.</p>}
        </form>

        <p className="auth-switch">
          {isLogin ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
          <button type="button" className="link" onClick={switchMode}>{isLogin ? "Đăng ký" : "Đăng nhập"}</button>
        </p>
      </section>
    </main>
  );
}
