"""Thống kê và hỗ trợ ra quyết định: dự báo cuối tháng, cảnh báo ngân sách, chi tiêu bất thường."""
import calendar
import statistics
from datetime import date, timedelta


def month_bounds(month: str):
    y, m = int(month[:4]), int(month[5:7])
    last = calendar.monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last)


def prev_month(month: str) -> str:
    first, _ = month_bounds(month)
    p = first - timedelta(days=1)
    return f"{p.year:04d}-{p.month:02d}"


def fmt(n) -> str:
    return f"{n:,.0f}".replace(",", ".") + " đ"


def monthly_stats(conn, month: str, uid: int) -> dict:
    first, last = month_bounds(month)
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total, COUNT(*) AS n FROM transactions "
        "WHERE user_id = ? AND date BETWEEN ? AND ? GROUP BY category ORDER BY total DESC",
        (uid, first.isoformat(), last.isoformat()),
    ).fetchall()
    by_cat = [{"category": r["category"], "total": r["total"], "count": r["n"]} for r in rows]
    daily = conn.execute(
        "SELECT date, SUM(amount) AS total FROM transactions WHERE user_id = ? AND date BETWEEN ? AND ? "
        "GROUP BY date ORDER BY date",
        (uid, first.isoformat(), last.isoformat()),
    ).fetchall()
    top_items = conn.execute(
        "SELECT name, SUM(amount) AS total, SUM(quantity) AS qty FROM transactions "
        "WHERE user_id = ? AND date BETWEEN ? AND ? GROUP BY name ORDER BY total DESC LIMIT 5",
        (uid, first.isoformat(), last.isoformat()),
    ).fetchall()
    # 6 tháng gần nhất để vẽ xu hướng
    trend, cur = [], month
    for _ in range(6):
        f, l = month_bounds(cur)
        t = conn.execute("SELECT COALESCE(SUM(amount),0) AS t FROM transactions "
                         "WHERE user_id = ? AND date BETWEEN ? AND ?",
                         (uid, f.isoformat(), l.isoformat())).fetchone()["t"]
        trend.append({"month": cur, "total": t})
        cur = prev_month(cur)
    trend.reverse()
    return {
        "month": month,
        "total": sum(c["total"] for c in by_cat),
        "by_category": by_cat,
        "daily": [{"date": r["date"], "total": r["total"]} for r in daily],
        "top_items": [{"name": r["name"], "total": r["total"], "quantity": r["qty"]} for r in top_items],
        "trend": trend,
    }


def _forecast(spent: float, prev_total: float | None, month: str, today: date) -> dict:
    """Dự báo tổng chi cuối tháng.

    - Tháng đã qua: bằng thực tế.
    - Tháng đang chạy: spent + tốc độ chi/ngày × số ngày còn lại. Tốc độ chi/ngày là trung bình có trọng số
      giữa tốc độ tháng này (càng về cuối tháng càng tin) và tháng trước (khi mới đầu tháng, dữ liệu còn ít).
    """
    first, last = month_bounds(month)
    if today > last:
        return {"value": spent, "method": "actual", "confidence": "high"}
    if today < first:
        return {"value": 0, "method": "none", "confidence": "low"}
    elapsed = (today - first).days + 1
    days = last.day
    mtd_rate = spent / elapsed
    if prev_total:
        prev_rate = prev_total / days
        w = min(1.0, elapsed / days)  # tin tháng này nhiều hơn khi đã đi được nhiều ngày
        rate = w * mtd_rate + (1 - w) * prev_rate
        method = "blend"
    else:
        rate, method = mtd_rate, "linear"
    value = spent + rate * (days - elapsed)
    conf = "high" if elapsed >= 20 else "medium" if elapsed >= 10 else "low"
    return {"value": round(value), "method": method, "confidence": conf, "daily_rate": round(rate)}


def anomalies(conn, month: str, uid: int) -> list[dict]:
    """Khoản chi bất thường trong tháng: so với lịch sử cùng danh mục (median + MAD, bền với outlier)."""
    first, last = month_bounds(month)
    hist_from = (first - timedelta(days=120)).isoformat()
    out = []
    cats = [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM transactions WHERE user_id = ? AND date BETWEEN ? AND ?",
        (uid, first.isoformat(), last.isoformat()))]
    for cat in cats:
        hist = [r["amount"] for r in conn.execute(
            "SELECT amount FROM transactions WHERE user_id = ? AND category=? AND date >= ? AND date <= ?",
            (uid, cat, hist_from, last.isoformat()))]
        if len(hist) < 8:
            continue
        med = statistics.median(hist)
        mad = statistics.median([abs(x - med) for x in hist]) or max(1.0, med * 0.1)
        thr = med + 3.5 * 1.4826 * mad
        for r in conn.execute(
            "SELECT id, date, name, amount FROM transactions "
            "WHERE user_id = ? AND category=? AND date BETWEEN ? AND ? AND amount > ?",
            (uid, cat, first.isoformat(), last.isoformat(), thr),
        ):
            if r["amount"] >= 2 * med:
                out.append({"id": r["id"], "date": r["date"], "name": r["name"], "category": cat,
                            "amount": r["amount"], "typical": round(med),
                            "ratio": round(r["amount"] / med, 1) if med else None})
    out.sort(key=lambda x: x["amount"], reverse=True)
    return out[:8]


def build_insights(conn, month: str, uid: int, today: date | None = None) -> dict:
    today = today or date.today()
    stats = monthly_stats(conn, month, uid)
    prev = monthly_stats(conn, prev_month(month), uid)
    spent, prev_total = stats["total"], prev["total"] or None
    fc = _forecast(spent, prev_total, month, today)

    budgets = {r["category"]: r["monthly_limit"] for r in conn.execute(
        "SELECT category, monthly_limit FROM user_budgets WHERE user_id = ?", (uid,))}
    first, last = month_bounds(month)
    elapsed = max(1, min((today - first).days + 1, last.day)) if today >= first else 1
    cat_forecast = {}
    for c in stats["by_category"]:
        rate = c["total"] / elapsed
        cat_forecast[c["category"]] = c["total"] if today > last else round(c["total"] + rate * (last.day - elapsed))

    alerts = []
    for cat, limit in budgets.items():
        s = next((c["total"] for c in stats["by_category"] if c["category"] == cat), 0)
        ratio = s / limit if limit else 0
        proj = cat_forecast.get(cat, 0)
        if ratio >= 1:
            status = "over"
        elif ratio >= 0.8:
            status = "warning"
        elif proj > limit and today <= last:
            status = "at_risk"
        else:
            status = "ok"
        alerts.append({"category": cat, "limit": limit, "spent": s, "ratio": round(ratio, 3),
                       "forecast": proj, "status": status})
    order = {"over": 0, "warning": 1, "at_risk": 2, "ok": 3}
    alerts.sort(key=lambda a: (order[a["status"]], -a["ratio"]))

    anoms = anomalies(conn, month, uid)

    # lời khuyên dạng văn bản (luật nghiệp vụ, giải thích được)
    tips = []
    for a in alerts:
        if a["status"] == "over":
            tips.append(f"Danh mục {a['category']} đã vượt ngân sách {fmt(a['spent'] - a['limit'])} "
                        f"({a['ratio']:.0%}). Nên hạn chế chi thêm cho mục này.")
        elif a["status"] == "warning":
            tips.append(f"Danh mục {a['category']} đã dùng {a['ratio']:.0%} ngân sách, còn {fmt(a['limit'] - a['spent'])}.")
        elif a["status"] == "at_risk":
            tips.append(f"Với tốc độ hiện tại, {a['category']} dự kiến chi {fmt(a['forecast'])}, vượt ngân sách {fmt(a['limit'])}.")
    if prev_total and spent and fc["value"] and today <= last:
        diff = (fc["value"] - prev_total) / prev_total * 100
        if abs(diff) >= 10:
            tips.append(f"Dự báo tháng này {fmt(fc['value'])}, {'cao' if diff > 0 else 'thấp'} hơn tháng trước {abs(diff):.0f}%.")
    for an in anoms[:2]:
        tips.append(f"Khoản \"{an['name']}\" ({fmt(an['amount'])}) cao gấp {an['ratio']} lần mức thường thấy của {an['category']}.")
    if not tips and spent:
        tips.append("Chi tiêu đang trong tầm kiểm soát. Hãy đặt ngân sách theo danh mục để nhận cảnh báo sớm.")

    return {
        "month": month,
        "spent": spent,
        "previous_month_total": prev["total"],
        "forecast": fc,
        "budget_alerts": alerts,
        "anomalies": anoms,
        "tips": tips,
    }
