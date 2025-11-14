# retry_failed.py (phiên bản đọc vnstock_failed.txt)
import os, time, random, traceback
from vnstock import Vnstock

FAILED_TXT = "vnstock_failed.txt"   # <-- chú ý tên file
FAILED_LOG = "vnstock_failed.log"
OUT_DIR = "data_hist"
os.makedirs(OUT_DIR, exist_ok=True)

MAX_RETRIES = 4
PAUSE = 0.25
BACKOFF_BASE = 0.8
MIN_BYTES_OK = 200
START_DATE = "2020-01-01"
END_DATE = "2025-11-13"

def backoff_sleep(attempt):
    wait = BACKOFF_BASE * (2 ** (attempt - 1))
    wait = wait * (1 + random.uniform(-0.3, 0.3))
    time.sleep(max(0.1, wait))

def read_failed_list():
    if not os.path.exists(FAILED_TXT):
        return []
    with open(FAILED_TXT, "r", encoding="utf-8") as fh:
        syms = [line.strip() for line in fh if line.strip()]
    # unique preserve order
    seen=set(); out=[]
    for s in syms:
        if s not in seen:
            out.append(s); seen.add(s)
    return out

def write_failed_list(syms):
    with open(FAILED_TXT, "w", encoding="utf-8") as fh:
        for s in syms:
            fh.write(s + "\n")

def log_detail(sym, reason):
    with open(FAILED_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"----- {sym} | {time.strftime('%Y-%m-%d %H:%M:%S')} -----\n")
        fh.write(reason + "\n\n")

def should_skip(sym):
    p = os.path.join(OUT_DIR, f"{sym}.csv")
    try:
        if os.path.exists(p) and os.path.getsize(p) > MIN_BYTES_OK:
            return True
    except:
        pass
    return False

def try_download(v, sym):
    last_err = None
    for attempt in range(1, MAX_RETRIES+1):
        try:
            s = v.stock(symbol=sym)
            df = s.quote.history(start=START_DATE, end=END_DATE, interval="1D")
            if df is None or len(df) < 3:
                last_err = f"NO DATA or too few rows ({0 if df is None else len(df)})"
                print(f"  {sym}: {last_err}")
                break
            if "time" in df.columns:
                df = df.rename(columns={"time":"date"})
            keep = [c for c in ["date","open","high","low","close","volume"] if c in df.columns]
            if keep:
                df = df[keep]
            out_path = os.path.join(OUT_DIR, f"{sym}.csv")
            df.to_csv(out_path, index=False, encoding="utf-8")
            print(f"  {sym}: ✅ success ({len(df)} rows) -> saved")
            return True, None
        except Exception as e:
            last_err = traceback.format_exc()
            print(f"  {sym}: attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                backoff_sleep(attempt)
            else:
                print(f"  {sym}: max retries reached.")
    return False, last_err

def main():
    syms = read_failed_list()
    if not syms:
        print(f"No {FAILED_TXT} found or file is empty → nothing to retry.")
        return
    print("Symbols to retry:", len(syms))
    syms = [s for s in syms if not should_skip(s)]
    print("After skipping existing files, to retry:", len(syms))

    v = Vnstock()
    remaining = []
    for i, sym in enumerate(syms, 1):
        print(f"[{i}/{len(syms)}] Retrying {sym} ...")
        ok, err = try_download(v, sym)
        if not ok:
            remaining.append(sym)
            if err:
                log_detail(sym, err)
        time.sleep(PAUSE)

    if remaining:
        write_failed_list(remaining)
        print(f"Hoàn tất. Vẫn thất bại: {len(remaining)}. Danh sách mới ở {FAILED_TXT}")
    else:
        if os.path.exists(FAILED_TXT):
            os.remove(FAILED_TXT)
        print("Hoàn tất. Tất cả symbols retried thành công. Đã xóa", FAILED_TXT)

if __name__ == "__main__":
    main()
