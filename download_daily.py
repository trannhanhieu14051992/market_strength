# download_daily.py (cải tiến)
import requests
import pandas as pd
import os
from datetime import datetime
from io import StringIO

OUTDIR = "data"

def fetch_daily_table():
    url = "https://www.cophieu68.vn/download/historydaily.php"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    html = r.text
    # Nếu pandas cảnh báo về literal html, ta dùng StringIO để an toàn
    dfs = pd.read_html(StringIO(html))
    # Chọn bảng có nhiều cột nhất (thường là bảng chính)
    df = max(dfs, key=lambda d: d.shape[1])
    return df

def normalize_header_if_needed(df):
    # Nếu cột là số (0,1,2...), rất có thể header nằm ở dòng đầu -> promote row 0 to header
    if all(isinstance(c, (int, float)) for c in df.columns):
        first_row = df.iloc[0].astype(str).tolist()
        df = df[1:].copy()
        df.columns = first_row
        df = df.reset_index(drop=True)
    # Chuyển tên cột sang str (an toàn)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def find_best_column(cols, keywords):
    """
    cols: list of column names (strings)
    keywords: list of substrings to match (lowercased)
    return first column name that contains any keyword (case-insensitive)
    """
    lower = [c.lower() for c in cols]
    for k in keywords:
        for i,c in enumerate(lower):
            if k in c:
                return cols[i]
    return None

def pick_close_and_volume(df):
    cols = list(df.columns)
    # Try find close price column
    close_col = find_best_column(cols, ["đóng", "dong", "close", "gia", "giá", "price", "last"])
    # Try find volume column
    vol_col = find_best_column(cols, ["kl", "khối", "k.l", "khoi", "volume", "vol"])

    # If not found, guess: choose numeric columns and heuristics
    numeric_cols = []
    for c in cols:
        # try convert a sample to numeric to detect numeric column
        try:
            s = pd.to_numeric(df[c].astype(str).str.replace(',', '').str.replace('.', ''), errors='coerce')
            if s.notna().sum() > 0:
                numeric_cols.append(c)
        except Exception:
            pass

    # If close_col still None, pick the first numeric column after symbol column (handled later)
    # If vol_col still None, pick the numeric column with largest average (likely volume)
    return close_col, vol_col, numeric_cols

def split_and_save(df):
    os.makedirs(OUTDIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    print("Columns found:", df.columns.tolist())

    # Normalize header if needed
    df = normalize_header_if_needed(df)

    # Identify symbol column: look for keywords
    cols = list(df.columns)
    symbol_col = find_best_column(cols, ["mã", "ma", "symbol", "ticker", "code"])
    if symbol_col is None:
        # fallback: first column
        symbol_col = cols[0]
        print("Không tìm cột mã rõ ràng, dùng cột đầu tiên:", symbol_col)
    else:
        print("Cột mã tìm thấy:", symbol_col)

    # Clean symbol column
    df[symbol_col] = df[symbol_col].astype(str).str.strip()

    # Try detect close and volume columns
    close_col, vol_col, numeric_cols = pick_close_and_volume(df)

    if close_col:
        print("Cột giá đóng/nghiên đoán:", close_col)
    else:
        print("Không xác định được cột giá đóng (close) tự động.")

    if vol_col:
        print("Cột khối lượng/nghiên đoán:", vol_col)
    else:
        print("Không xác định được cột khối lượng (volume) tự động.")

    # For each symbol, save a CSV. We'll try to produce at least: date,close,volume if possible.
    saved = 0
    for sym, group in df.groupby(symbol_col):
        # make a copy and reset index
        g = group.copy().reset_index(drop=True)
        # Ensure there's a date column; if not, add today's date
        # If DataFrame already has a column meaning 'date', try to use it
        date_col = find_best_column(list(g.columns), ["ngày", "date", "day"])
        if date_col:
            g = g.rename(columns={date_col: "date"})
        if "date" not in [c.lower() for c in g.columns]:
            g.insert(0, "date", today)

        # choose close & volume if available and rename to standard names
        if close_col and close_col in g.columns:
            g = g.rename(columns={close_col: "close"})
        else:
            # try to pick a numeric column that looks like price:
            # prefer numeric_cols[0] if exists
            for c in numeric_cols:
                if c in g.columns and c != symbol_col:
                    g = g.rename(columns={c: "close"})
                    print(f"Fallback: dùng cột {c} làm 'close' cho {sym}")
                    break

        if vol_col and vol_col in g.columns:
            g = g.rename(columns={vol_col: "volume"})
        else:
            # guess volume as numeric column with largest mean
            cand = [c for c in numeric_cols if c in g.columns and c != "close" and c != symbol_col]
            if cand:
                means = {c: pd.to_numeric(g[c].astype(str).str.replace(',', ''), errors='coerce').abs().mean() for c in cand}
                best = max(means, key=lambda k: means[k]) if means else None
                if best:
                    g = g.rename(columns={best: "volume"})
                    print(f"Fallback: dùng cột {best} làm 'volume' cho {sym}")

        # Prepare path and save (if file exists, append rows without header)
        path = os.path.join(OUTDIR, f"{sym}.csv")
        # Select common columns for output if they exist
        out_cols = []
        for want in ["date", "close", "volume"]:
            for c in g.columns:
                if c.lower() == want:
                    out_cols.append(c)
                    break
        # If we have at least date + close, write a compact CSV; otherwise write full group
        if "date" in [c.lower() for c in out_cols] and any(c.lower() == "close" for c in out_cols):
            to_save = g[[c for c in out_cols]]
        else:
            to_save = g

        if os.path.exists(path):
            to_save.to_csv(path, mode="a", index=False, header=False)
        else:
            to_save.to_csv(path, index=False)
        saved += 1

    print(f"Saved {saved} symbol files to {OUTDIR}")

if __name__ == "__main__":
    print("Fetching daily table from cophieu68...")
    df = fetch_daily_table()
    split_and_save(df)
    print("Done.")
