# compute.py (robust version)
import glob, os, math
import pandas as pd
from datetime import datetime

DATA_GLOB = "data_hist/*.csv"
HISTORY_FILE = "history.csv"

# --- helper: detect close & volume columns ---
def detect_cols(df):
    cols = [str(c) for c in df.columns]
    lower = [c.lower() for c in cols]

    # keywords for close (price)
    close_keys = ["close", "đóng", "dong", "gia", "giá", "gia", "price", "last", "closeprice"]
    vol_keys = ["volume", "vol", "kl", "khối", "khoi", "qty", "khối lượng", "k.l."]

    # try find by keywords
    for i, c in enumerate(lower):
        for k in close_keys:
            if k in c:
                return cols[i], None
    for i, c in enumerate(lower):
        for k in vol_keys:
            if k in c:
                # find close too (maybe earlier)
                # try to find close now with broader scan
                close_candidate = None
                for j, cc in enumerate(lower):
                    for k2 in close_keys:
                        if k2 in cc:
                            close_candidate = cols[j]; break
                    if close_candidate:
                        break
                return close_candidate, cols[i]

    # fallback: choose numeric columns
    numeric_scores = {}
    for c in cols:
        try:
            s = pd.to_numeric(df[c].astype(str).str.replace(",",""), errors="coerce")
            non_na = s.notna().sum()
            mean = s.abs().mean() if non_na>0 else 0
            numeric_scores[c] = (non_na, mean)
        except Exception:
            numeric_scores[c] = (0,0)

    # pick close as numeric with most non-na values (and not too large mean like volume)
    sorted_by_nonna = sorted(numeric_scores.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True)
    close_col = None
    vol_col = None
    if sorted_by_nonna:
        # assume top numeric is price-like (smaller mean than volume often)
        close_col = sorted_by_nonna[0][0]
        # choose vol as the numeric column with largest mean (likely volume)
        sorted_by_mean = sorted(numeric_scores.items(), key=lambda kv: kv[1][1], reverse=True)
        for c, (nn, m) in sorted_by_mean:
            if c != close_col and nn > 0:
                vol_col = c
                break

    return close_col, vol_col

# --- main computation ---
def compute_market_strength(glob_pattern=DATA_GLOB, ma_days=50, vol_window=20, mom_days=20, min_rows=None):
    files = sorted(glob.glob(glob_pattern))
    total_files = len(files)
    if total_files == 0:
        print("No files found with pattern:", glob_pattern)
        return None

    # minimal rows required
    if min_rows is None:
        min_rows = max(ma_days, vol_window, mom_days) + 1

    cnt_breadth = cnt_vol = cnt_mom = 0
    used = 0
    skipped = []
    for f in files:
        sym = os.path.splitext(os.path.basename(f))[0]
        try:
            df = pd.read_csv(f)
        except Exception as e:
            skipped.append((sym, "read_error", str(e)))
            continue

        if len(df) < min_rows:
            skipped.append((sym, "too_few_rows", len(df)))
            continue

        # detect columns
        close_col, vol_col = detect_cols(df)
        if not close_col:
            skipped.append((sym, "no_close_col", ",".join(map(str, df.columns.tolist()))[:200]))
            continue

        # ensure close values numeric
        try:
            close_series = pd.to_numeric(df[close_col].astype(str).str.replace(",",""), errors="coerce")
        except Exception:
            skipped.append((sym, "close_not_numeric", close_col))
            continue

        if close_series.isna().sum() > len(close_series) * 0.5:
            skipped.append((sym, "close_mostly_nan", close_col))
            continue

        # volume may be missing but we try
        vol_series = None
        if vol_col:
            try:
                vol_series = pd.to_numeric(df[vol_col].astype(str).str.replace(",",""), errors="coerce")
            except Exception:
                vol_series = None

        # now compute metrics using last available rows
        # align to last rows (most recent last row)
        price_today = close_series.iloc[-1]
        # moving average (use last ma_days values ending at -2 to avoid look-ahead)
        try:
            ma = close_series.rolling(ma_days).mean().iloc[-2]
        except Exception:
            ma = None

        # volume average
        vol_avg = None
        if vol_series is not None:
            try:
                vol_avg = vol_series.rolling(vol_window).mean().iloc[-2]
            except Exception:
                vol_avg = None

        # momentum: compare to price mom_days ago
        price_old = None
        if len(close_series) > mom_days:
            price_old = close_series.iloc[-(mom_days+1)]
        else:
            price_old = None

        # validate numeric
        if pd.isna(price_today) or (ma is not None and pd.isna(ma)):
            skipped.append((sym, "nan_values_in_price_or_ma"))
            continue

        used += 1
        # breadth: price > MA
        if ma is not None and price_today > ma:
            cnt_breadth += 1
        # volume: today's vol > vol_avg
        if vol_series is not None and vol_avg is not None:
            try:
                if vol_series.iloc[-1] > vol_avg:
                    cnt_vol += 1
            except Exception:
                pass
        # momentum: price_today > price_old
        if price_old is not None and price_today > price_old:
            cnt_mom += 1

    if used == 0:
        print("No usable symbols found. Skipped examples (first 30):")
        for s in skipped[:30]:
            print(s)
        return {'score': 0.0, 'used': 0, 'total': total_files, 'skipped': skipped[:50]}

    # compute percentages relative to used symbols
    breadth_pct = 100.0 * cnt_breadth / used
    vol_pct = 100.0 * cnt_vol / used
    mom_pct = 100.0 * cnt_mom / used
    # final score (weights tweakable)
    score = 0.4 * breadth_pct + 0.3 * vol_pct + 0.3 * mom_pct

    result = {
        'score': round(float(score), 2),
        'breadth_pct': round(float(breadth_pct), 2),
        'vol_pct': round(float(vol_pct), 2),
        'mom_pct': round(float(mom_pct), 2),
        'counts': {'total_files': total_files, 'used': used, 'breadth': cnt_breadth, 'vol': cnt_vol, 'mom': cnt_mom},
        'skipped_sample': skipped[:50]
    }

    # append to history.csv
    try:
        row = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'score': result['score'],
            'breadth_pct': result['breadth_pct'],
            'vol_pct': result['vol_pct'],
            'mom_pct': result['mom_pct'],
            'total_files': total_files,
            'used': used
        }
        dfh = pd.DataFrame([row])
        if os.path.exists(HISTORY_FILE):
            dfh.to_csv(HISTORY_FILE, mode='a', index=False, header=False)
        else:
            dfh.to_csv(HISTORY_FILE, index=False)
    except Exception as e:
        print("Warning: failed to write history:", e)

    return result

if __name__ == "__main__":
    res = compute_market_strength(DATA_GLOB, ma_days=50, vol_window=20, mom_days=20)
    print(res)
