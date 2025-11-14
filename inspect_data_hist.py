# inspect_data_hist.py
# Dò toàn bộ file CSV, đếm số dòng, xem thử có dữ liệu hay không
import glob, os, pandas as pd
from pathlib import Path

IN_DIR = "data_hist"
files = sorted(glob.glob(os.path.join(IN_DIR, "*.csv")))
print("Tổng số file tìm thấy:", len(files))

summary = []
nonempty = []
for f in files:
    name = Path(f).name
    size = os.path.getsize(f)
    # đọc thô 8 dòng đầu tiên để xem có HTML hay bảng thật
    raw_head = []
    try:
        with open(f, "r", encoding="utf-8", errors="replace") as fh:
            for _ in range(8):
                line = fh.readline()
                if not line:
                    break
                raw_head.append(line.rstrip("\n"))
    except Exception as e:
        raw_head = [f"LỖI ĐỌC FILE: {e}"]

    # thử đọc bằng pandas
    df = None
    for enc in ("utf-8","latin1","cp1258"):
        try:
            df = pd.read_csv(f, encoding=enc)
            break
        except Exception:
            df = None
    rows = len(df) if df is not None else 0
    cols = list(df.columns) if df is not None else []
    summary.append((name, size, rows, cols[:8], raw_head[:6]))
    if rows > 0:
        nonempty.append((name, rows, cols[:8]))

# ghi file tổng hợp
sdf = pd.DataFrame([
    {"file": s[0], "kích_thước": s[1], "số_dòng": s[2], "các_cột": "|".join(map(str, s[3]))}
    for s in summary
])
sdf.to_csv("data_hist_summary.csv", index=False)

print("\n✅ Đã lưu danh sách vào: data_hist_summary.csv")
print("\nCác file có dữ liệu (rows > 0, tối đa 30 file):")
for n in nonempty[:30]:
    print(" ", n)

print("\n--- Xem trước nội dung 6 file đầu tiên ---")
for s in summary[:6]:
    print(f"\n== {s[0]}  kích_thước={s[1]} bytes, số_dòng={s[2]}, cột={s[3]}")
    for L in s[4]:
        print("   ", L)
