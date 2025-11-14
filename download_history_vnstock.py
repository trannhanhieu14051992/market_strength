# download_history_vnstock.py
# Robust downloader for vnstock (v3+)
# - retries with exponential backoff + jitter
# - logs failed symbols to vnstock_failed.txt and detailed errors to vnstock_failed.log
# - resumes (skips existing files > min_bytes_ok)
# - reads symbols from data/symbols_all.csv or fallback to data/*.csv

import os, time, glob, random, traceback
import pandas as pd
from vnstock import Vnstock

# ----- CONFIG -----
OUT_DIR = "data_hist"
os.makedirs(OUT_DIR, exist_ok=True)

SYMBOLS_FILE = "data/symbols_all.csv"   # primary source (one symbol per line or CSV)
MIN_BYTES_OK = 200                      # nếu file đã có > MIN_BYTES_OK bytes -> coi là đã tải
PAUSE = 0.25                            # pause between requests (s)
MAX_RETRIES = 5                         # số lần thử lại khi lỗi kết nối
BACKOFF_BASE = 0.8                      # base backoff seconds
FAILED_TXT = "vnstock_failed.txt"       # danh sách symbols failed (one per line)
FAILED_LOG = "vnstock_failed.log"       # chi tiết lỗi (append)
BATCH_SIZE = None                       # nếu muốn chạy theo batch: set int, or None để chạy hết
# TEST_LIMIT = 50                        # nếu test, uncomment this line to limit symbols downloaded

START_DATE = "2020-01-01"
END_DATE = "2025-11-13"

# ----- load symbols -----
symbols = []
if os.path.exists(SYMBOLS_FILE):
    with open(SYMBOLS_FILE, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            # accept CSV line "AAA,Name" or plain "AAA"
            s = s.split(",")[0].replace('"', '').strip()
            if s:
                symbols.append(s)
else:
    # fallback: take CSV filenames from data/ if exists
    data_folder_files = glob.glob("data/*.csv")
    symbols = sorted({os.path.splitext(os.path.basename(f))[0] for f in data_folder_files})

if not symbols:
    raise SystemExit("Không tìm được danh sách mã. Hãy tạo file data/symbols_all.csv hoặc đặt CSV trong thư mục data/")

# optional test limit (uncomment to use)
# symbols = symbols[:TEST_LIMIT]   # <-- bỏ comment để test nhanh

# if batch mode is set, you can control which chunk to process by environment variables or manual slicing
if BATCH_SIZE:
    # Process in batches of BATCH_SIZE: process only first batch by default.
    # You can change this logic to process different chunks.
    symbols = symbols[:BATCH_SIZE]

print(f"Symbols to process: {len(symbols)} (OUT_DIR={OUT_DIR})")

# ----- helper functions -----
def log_failed_symbol(sym, reason):
    with open(FAILED_TXT, "a", encoding="utf-8") as fh:
        fh.write(sym + "\n")
    with open(FAILED_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"----- {sym} | {time.strftime('%Y-%m-%d %H:%M:%S')} -----\n")
        fh.write(reason + "\n\n")

def should_skip(sym):
    p = os.path.join(OUT_DIR, f"{sym}.csv")
    try:
        if os.path.exists(p) and os.path.getsize(p) > MIN_BYTES_OK:
            return True
    except Exception:
        pass
    return False

def backoff_sleep(attempt):
    # exponential backoff + jitter
    wait = BACKOFF_BASE * (2 ** (attempt - 1))
    # add jitter up to 30%
    wait = wait * (1 + random.uniform(-0.3, 0.3))
    time.sleep(max(0.1, wait))

# ----- downloader loop -----
v = Vnstock()
ok = 0
fail = 0
total = len(symbols)
start_time = time.time()

for idx, sym in enumerate(symbols, 1):
    out_path = os.path.join(OUT_DIR, f"{sym}.csv")
    if should_skip(sym):
        print(f"[{idx}/{total}] {sym}: already exists, skip")
        continue

    success = False
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            s = v.stock(symbol=sym)
            df = s.quote.history(start=START_DATE, end=END_DATE, interval="1D")
            if df is None or len(df) < 3:
                last_error = f"NO DATA or too few rows ({0 if df is None else len(df)})"
                print(f"[{idx}/{total}] {sym}: {last_error}")
                # treat as fail but do not retry too aggressively
                success = False
                break
            # rename time->date if exists, keep essential columns if present
            if "time" in df.columns:
                df = df.rename(columns={"time": "date"})
            keep = [c for c in ["date","open","high","low","close","volume"] if c in df.columns]
            if keep:
                df = df[keep]
            df.to_csv(out_path, index=False, encoding="utf-8")
            print(f"[{idx}/{total}] {sym}: ✅ {len(df)} rows -> saved")
            success = True
            ok += 1
            break
        except Exception as e:
            last_error = traceback.format_exc()
            print(f"[{idx}/{total}] {sym}: attempt {attempt} failed: {e}")
            # if last attempt, log failure
            if attempt == MAX_RETRIES:
                print(f"  -> max retries reached for {sym}, logging to {FAILED_TXT}")
                log_failed_symbol(sym, last_error)
                fail += 1
            else:
                backoff_sleep(attempt)
            # continue retry loop
    # end attempts
    # small pause between symbols
    time.sleep(PAUSE)
    # early exit if lots of failures? (optional)
    # if fail > 200: break

elapsed = time.time() - start_time
print(f"\nDone. OK: {ok}, FAIL: {fail}, elapsed: {elapsed:.1f}s")
print(f"Failed symbols recorded in: {FAILED_TXT} (details in {FAILED_LOG})")
