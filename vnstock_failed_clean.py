# vnstock_failed_clean.py
# Đọc vnstock_failed.txt, loại bỏ các chỉ số/ký tự '^', viết ra vnstock_failed_clean.txt

import os

SRC = "vnstock_failed.txt"
OUT = "vnstock_failed_clean.txt"

if not os.path.exists(SRC):
    print("❌ Không tìm thấy", SRC)
    raise SystemExit(1)

skip_indices = {
    "VNINDEX","HNXINDEX","UPCOMINDEX",
    "VN30","HNX30","UPCOM",
    "HASTC","HASTCINDEX"
}

clean = []
with open(SRC, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        s = line.strip()
        if not s:
            continue
        # loại ^ + uppercase + trim
        s = s.lstrip("^").strip().upper()
        if s in skip_indices:
            continue
        if s and s not in clean:
            clean.append(s)

with open(OUT, "w", encoding="utf-8") as f:
    for s in clean:
        f.write(s + "\n")

print("✅ ĐÃ TẠO FILE:", OUT)
print("👉 Số mã còn lại:", len(clean))
