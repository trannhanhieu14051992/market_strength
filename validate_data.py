# validate_data.py
import glob, os, pandas as pd

folder = "data"
files = glob.glob(os.path.join(folder, "*.csv"))
print("Found", len(files), "csv files in", folder)
bad = []
ok = []
for f in files:
    try:
        df = pd.read_csv(f)
    except Exception as e:
        bad.append((f, "read error:"+str(e)))
        continue
    cols = [str(c).lower() for c in df.columns]
    has_close = any("close" in c or "đóng" in c or "gia" in c or "giá" in c or "last" in c for c in cols)
    has_volume = any("volume" in c or "vol" in c or "kl" in c or "khối" in c or "khoi" in c for c in cols)
    rows = len(df)
    # minimal rows threshold
    enough_rows = rows >= 5
    if has_close and has_volume and enough_rows:
        ok.append((os.path.basename(f), rows))
    else:
        reasons = []
        if not has_close: reasons.append("no-close")
        if not has_volume: reasons.append("no-volume")
        if not enough_rows: reasons.append(f"rows={rows}")
        bad.append((os.path.basename(f), ",".join(reasons)))
print("OK files:", len(ok))
print("BAD files:", len(bad))
if len(bad)>0:
    print("\nFirst 30 bad examples:")
    for i,ent in enumerate(bad[:30],1):
        print(i, ent)
else:
    print("All good.")
