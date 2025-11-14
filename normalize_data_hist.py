# normalize_data_hist.py
# Chuẩn hóa tất cả file trong data_hist (chuyển mã UTF-8, rename cột, numeric hóa)
import os, glob, shutil, pandas as pd
from datetime import datetime

IN_DIR = "data_hist"
BACKUP_DIR = "data_hist_backup"
os.makedirs(BACKUP_DIR, exist_ok=True)

# từ khóa phát hiện cột
close_keys = ["close", "đóng", "dong", "gia", "giá", "price", "last", "closeprice"]
vol_keys = ["volume", "vol", "kl", "khối", "khoi", "qty", "khối lượng"]

def normalize_encoding(file_path):
    """Thử đọc UTF-8, fallback latin1."""
    for enc in ["utf-8", "latin1", "cp1258"]:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            return df
        except Exception:
            continue
    raise Exception("Không đọc được file:", file_path)

def to_number(s):
    s = s.astype(str).str.replace(",", "").str.replace(" ", "").str.replace(".", ".")
    return pd.to_numeric(s, errors="coerce")

def normalize_one(f):
    name = os.path.basename(f)
    try:
        df = normalize_encoding(f)
    except Exception as e:
        print(f"❌ Lỗi đọc {name}:", e)
        return False

    # backup
    bk = os.path.join(BACKUP_DIR, name)
    if not os.path.exists(bk):
        shutil.copy2(f, bk)

    # tìm cột "date"
    date_col = None
    for c in df.columns:
        if any(x in str(c).lower() for x in ["date", "ngày", "day"]):
            date_col = c
            break
    if date_col is None:
        df.insert(0, "date", datetime.today().strftime("%Y-%m-%d"))
        date_col = "date"

    # tìm close và volume
    close_col = None
    for c in df.columns:
        for k in close_keys:
            if k in str(c).lower():
                close_col = c; break
        if close_col: break

    vol_col = None
    for c in df.columns:
        for k in vol_keys:
            if k in str(c).lower():
                vol_col = c; break
        if vol_col: break

    # tạo cột chuẩn
    df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    if close_col:
        df["close"] = to_number(df[close_col])
    else:
        df["close"] = pd.NA
    if vol_col:
        df["volume"] = to_number(df[vol_col])
    else:
        df["volume"] = pd.NA

    # drop NaN
    before = len(df)
    df = df.dropna(subset=["close"])
    after = len(df)

    # sắp xếp theo ngày
    df = df.sort_values("date").reset_index(drop=True)

    # ghi đè lại
    df.to_csv(f, index=False, encoding="utf-8")
    print(f"✅ {name}: OK ({after}/{before} hàng)")
    return True

# main loop
files = sorted(glob.glob(os.path.join(IN_DIR, "*.csv")))
print("Tổng số file:", len(files))
ok, fail = 0, 0
for f in files:
    if normalize_one(f):
        ok += 1
    else:
        fail += 1
print(f"\nHoàn tất! Chuẩn hóa thành công {ok} file, lỗi {fail} file.")
