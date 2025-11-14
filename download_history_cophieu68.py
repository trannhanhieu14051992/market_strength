# download_history_cophieu68.py (fixed)
import os, time, glob, requests
import pandas as pd
from datetime import datetime
from urllib.parse import quote
from io import StringIO

OUTDIR = "data_hist"
DATADIR = "data"   # dùng danh sách mã từ tên file trong thư mục data/
os.makedirs(OUTDIR, exist_ok=True)

# Pattern đúng: dùng {sym} và {sym_lower} (format sẽ thay giá trị)
PATTERNS = [
    "https://www.cophieu68.vn/quote/history.php?id={sym}",
    "https://www.cophieu68.vn/quote/history.php?id={sym_lower}",
    "https://www.cophieu68.vn/quote/{sym}/history",
    "https://www.cophieu68.vn/quote/{sym}",
    "https://www.cophieu68.vn/download/history.php?symbol={sym}",
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Lấy danh sách mã cổ phiếu từ thư mục data/
files = glob.glob(os.path.join(DATADIR, "*.csv"))
symbols = sorted({os.path.splitext(os.path.basename(f))[0].strip() for f in files})
print("Tổng số mã:", len(symbols))

def try_fetch_table(url, session, max_tries=2):
    # trả về (df, None) nếu ok, hoặc (None, "reason")
    for attempt in range(1, max_tries+1):
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
        except Exception as e:
            reason = f"request_err:{e}"
            # nếu là lần cuối thì trả về lỗi
            if attempt == max_tries:
                return None, reason
            time.sleep(0.5)
            continue
        if r.status_code != 200:
            reason = f"status_{r.status_code}"
            if attempt == max_tries:
                return None, reason
            time.sleep(0.3)
            continue
        # parse html into tables (use StringIO to avoid FutureWarning)
        try:
            dfs = pd.read_html(StringIO(r.text))
        except Exception as e:
            return None, f"parse_err:{e}"
        # Heuristic: chọn bảng có nhiều cột hoặc có từ khóa "date/đóng/giá"
        best, best_score = None, -1
        for df in dfs:
            cols = " ".join([str(c).lower() for c in df.columns.astype(str)])
            score = df.shape[1]
            if any(k in cols for k in ("date", "ngày", "close", "đóng", "giá")):
                score += 10
            if score > best_score:
                best, best_score = df, score
        if best is None:
            return None, "no_table"
        return best, None
    return None, "unknown_err"

failed, count = [], 0
session = requests.Session()

for i, sym in enumerate(symbols, start=1):
    out_path = os.path.join(OUTDIR, f"{sym}.csv")
    if os.path.exists(out_path):
        print(f"[{i}/{len(symbols)}] {sym}: Bỏ qua (đã có file).")
        continue
    success = False
    # prepare formatted values
    sym_lower = sym.lower()
    for p in PATTERNS:
        url = p.format(sym=quote(sym), sym_lower=quote(sym_lower))
        print(f"[{i}/{len(symbols)}] Thử {url} ...", end=" ")
        df, err = try_fetch_table(url, session, max_tries=2)
        if df is None:
            print("thất bại:", err)
            time.sleep(0.25)
            continue
        # Nếu header nằm ở hàng đầu (columns are integers) promote row 0 to header
        try:
            if all(isinstance(c, (int, float)) for c in df.columns):
                df.columns = df.iloc[0].astype(str).tolist()
                df = df.iloc[1:].reset_index(drop=True)
        except Exception:
            pass
        # Ensure date column exists (if not, insert today's date)
        if not any("date" in str(c).lower() or "ngày" in str(c).lower() for c in df.columns):
            df.insert(0, "date", datetime.today().strftime("%Y-%m-%d"))
        # Save CSV
        try:
            df.to_csv(out_path, index=False)
            print("✔️ OK, số dòng:", len(df))
            success, count = True, count + 1
            time.sleep(0.2)  # polite pause
            break
        except Exception as e:
            print("lỗi khi lưu:", e)
            time.sleep(0.2)
    if not success:
        failed.append(sym)
        time.sleep(0.35)

print("Hoàn tất. Đã lưu:", count, "mã. Thất bại:", len(failed))
if failed:
    with open("download_failed_cophieu68.txt", "w", encoding="utf8") as fh:
        fh.write("\n".join(failed))
    print("Danh sách lỗi ghi trong download_failed_cophieu68.txt")
