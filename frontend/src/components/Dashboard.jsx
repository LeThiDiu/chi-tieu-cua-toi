import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { catColor, monthLabel, shortDate, vnd } from "../format.js";

const STATUS_TEXT = { over: "Vượt ngân sách", warning: "Sắp hết", at_risk: "Có nguy cơ vượt", ok: "Ổn" };
const CONF_TEXT = { high: "độ tin cậy cao", medium: "độ tin cậy vừa", low: "mới đầu tháng nên chỉ mang tính tham khảo" };

export default function Dashboard({ month, refreshKey, goScan, userName, onSeeded }) {
  const [stats, setStats] = useState(null);
  const [ins, setIns] = useState(null);
  const [err, setErr] = useState("");
  const [seedMsg, setSeedMsg] = useState("");
  const [seeding, setSeeding] = useState(false);

  async function seedDemo() {
    setSeeding(true);
    setSeedMsg("");
    try {
      const res = await api.seedDemo();
      if (res.seeded) onSeeded();
      else setSeedMsg("Tài khoản của bạn đã có giao dịch ở tháng khác, hãy đổi tháng ở thanh bên (‹ ›).");
    } catch (e) {
      setSeedMsg(e.message);
    } finally {
      setSeeding(false);
    }
  }

  useEffect(() => {
    setErr("");
    Promise.all([api.stats(month), api.insights(month)])
      .then(([s, i]) => { setStats(s); setIns(i); })
      .catch((e) => setErr(e.message));
  }, [month, refreshKey]);

  if (err) return <div className="banner error" role="alert">{err}</div>;
  if (!stats || !ins) return <p className="muted">Đang tải số liệu…</p>;

  if (stats.total === 0) {
    return (
      <section className="empty">
        <h1>{monthLabel(month)} chưa có chi tiêu</h1>
        <p>Chụp một hóa đơn để app tự đọc tên sản phẩm, số lượng và thành tiền.</p>
        <div className="empty-actions">
          <button className="primary" onClick={goScan}>Quét hóa đơn</button>
          <button className="secondary" onClick={seedDemo} disabled={seeding}>
            {seeding ? "Đang nạp…" : "Nạp dữ liệu mẫu"}
          </button>
        </div>
        {seedMsg && <p className="hint">{seedMsg}</p>}
        <p className="hint">Dữ liệu mẫu chỉ nạp được khi tài khoản chưa có giao dịch nào, và chỉ hiện trong tài khoản của bạn.</p>
      </section>
    );
  }

  const prev = ins.previous_month_total;
  const diff = prev ? ((ins.forecast.value - prev) / prev) * 100 : null;
  const pie = stats.by_category.map((c) => ({ name: c.category, value: c.total }));

  return (
    <>
      <section className="welcome-banner">
        <div>
          <span className="eyebrow">TÀI CHÍNH CỦA BẠN, RÕ RÀNG HƠN</span>
          <h1>{userName ? `Chào ${userName}, cùng xem lại chi tiêu nhé` : "Chào bạn, cùng xem lại chi tiêu nhé"}</h1>
          <p>Theo dõi ngân sách, hiểu thói quen và giữ mọi khoản chi trong tầm tay.</p>
        </div>
        <button className="primary" onClick={goScan}>＋ Quét hóa đơn</button>
      </section>
      <h1>{monthLabel(month)}</h1>

      <section className="figures">
        <div>
          <div className="fig-label">Đã chi</div>
          <div className="fig-value">{vnd(ins.spent)}</div>
        </div>
        <div>
          <div className="fig-label">Dự báo cả tháng</div>
          <div className="fig-value">{vnd(ins.forecast.value)}</div>
          <div className="fig-note">{CONF_TEXT[ins.forecast.confidence]}</div>
        </div>
        <div>
          <div className="fig-label">Tháng trước</div>
          <div className="fig-value">{prev ? vnd(prev) : "—"}</div>
          {diff !== null && (
            <div className={`fig-note ${diff > 10 ? "bad" : ""}`}>
              Dự báo {diff >= 0 ? "cao" : "thấp"} hơn {Math.abs(diff).toFixed(0)}%
            </div>
          )}
        </div>
      </section>

      {ins.tips.length > 0 && (
        <section className="card">
          <h2>Nên chú ý</h2>
          <ul className="tips">{ins.tips.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </section>
      )}

      <div className="grid2">
        <section className="card">
          <h2>Chi theo danh mục</h2>
          <div className="pie-row">
            <div className="pie-box">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={pie} dataKey="value" innerRadius={55} outerRadius={90} paddingAngle={1} stroke="none">
                    {pie.map((p) => <Cell key={p.name} fill={catColor(p.name)} />)}
                  </Pie>
                  <Tooltip formatter={(v) => vnd(v)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="legend">
              {stats.by_category.map((c) => (
                <li key={c.category}>
                  <span className="dot" style={{ background: catColor(c.category) }} />
                  <span className="grow">{c.category}</span>
                  <span className="num">{vnd(c.total)}</span>
                  <span className="pct">{((c.total / stats.total) * 100).toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="card">
          <h2>6 tháng gần nhất</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.trend.map((t) => ({ ...t, label: `T${Number(t.month.slice(5))}` }))}>
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis hide />
              <Tooltip formatter={(v) => vnd(v)} cursor={{ fill: "rgba(22,125,88,.08)" }} />
              <Bar dataKey="total" radius={[3, 3, 0, 0]}>
                {stats.trend.map((t) => <Cell key={t.month} fill={t.month === month ? "#167D58" : "#B8D9C6"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>
      </div>

      {ins.budget_alerts.length > 0 && (
        <section className="card">
          <h2>Ngân sách theo danh mục</h2>
          <ul className="budget-list">
            {ins.budget_alerts.map((b) => (
              <li key={b.category}>
                <div className="b-head">
                  <span>{b.category}</span>
                  <span className={`status ${b.status}`}>{STATUS_TEXT[b.status]}</span>
                  <span className="grow" />
                  <span className="num">{vnd(b.spent)} / {vnd(b.limit)}</span>
                </div>
                <div className="bar" role="progressbar" aria-valuenow={Math.round(b.ratio * 100)} aria-valuemin={0} aria-valuemax={100}>
                  <div className={`fill ${b.status}`} style={{ width: `${Math.min(100, b.ratio * 100)}%` }} />
                </div>
                <div className="fig-note">Dự báo cuối tháng: {vnd(b.forecast)}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid2">
        <section className="card">
          <h2>Mua nhiều nhất</h2>
          <ul className="plain">
            {stats.top_items.map((t) => (
              <li key={t.name}><span className="grow">{t.name}</span><span className="num">{vnd(t.total)}</span></li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h2>Khoản chi bất thường</h2>
          {ins.anomalies.length === 0 ? (
            <p className="muted">Chưa phát hiện khoản nào cao hơn thói quen của bạn.</p>
          ) : (
            <ul className="plain">
              {ins.anomalies.map((a) => (
                <li key={a.id}>
                  <span className="grow">{a.name}<small> · {shortDate(a.date)} · {a.category}</small></span>
                  <span className="num">{vnd(a.amount)}</span>
                  <span className="pct bad">×{a.ratio}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
