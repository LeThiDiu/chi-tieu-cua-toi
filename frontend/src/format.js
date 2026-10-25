export const vnd = (n) => `${Math.round(n || 0).toLocaleString("vi-VN")} ₫`;
export const today = () => new Date().toISOString().slice(0, 10);
export const thisMonth = () => today().slice(0, 7);
export const monthLabel = (m) => `Tháng ${Number(m.slice(5, 7))}/${m.slice(0, 4)}`;
export const shiftMonth = (m, delta) => {
  const d = new Date(Number(m.slice(0, 4)), Number(m.slice(5, 7)) - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};
export const shortDate = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

// Màu cố định cho từng danh mục (dùng chung cho biểu đồ và nhãn)
export const CAT_COLORS = {
  "Ăn uống": "#C2410C", "Đồ uống": "#0E7490", "Thực phẩm": "#4D7C0F", "Gia dụng": "#7C5CBF",
  "Chăm sóc cá nhân": "#BE185D", "Y tế": "#B3261E", "Di chuyển": "#1F3FBF", "Học tập": "#A16207",
  "Giải trí": "#0F766E", "Khác": "#6B7280",
};
export const catColor = (c) => CAT_COLORS[c] || "#6B7280";
