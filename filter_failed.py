# filter_failed.py
# Lọc vnstock_failed.txt, giữ ONLY dòng có dạng mã chứng khoán hợp lệ.
# - Bỏ các dòng chứa "print(...)", "PY", code, dấu ^ chỉ số, text tiếng, v.v.
# - Kết quả ghi ra vnstock_failed_filtered.txt
import re, os, sys

INPUT = "vnstock_failed.txt"
OUTPUT = "vnstock_failed_filtered.txt"
REPORT = "vnstock_failed_removed.txt"

if not os.path.exists(INPUT):
    print("❌ Không tìm thấy", INPUT)
    sys.exit(1)

# pattern: chỉ chữ hoa A-Z và số 0-9, dài 1..6 (thường enough cho VN tickers)
# nếu bạn có mã dài hơn, tăng {1,6} -> {1,8}
pat = re.compile(r'^[A-Z0-9]{1,6}$')

kept = []
removed = []

with open(INPUT, "r", encoding="utf-8", errors="ignore") as f:
    for i, raw in enumerate(f, 1):
        s = raw.strip()
        if not s:
            continue
        # remove leading caret and whitespace, uppercase
        s_clean = s.lstrip("^").strip().upper()
        # remove accidental surrounding quotes
        if (s_clean.startswith('"') and s_clean.endswith('"')) or (s_clean.startswith("'") and s_clean.endswith("'")):
            s_clean = s_clean[1:-1].strip()
        # If matches stock pattern -> keep
        if pat.match(s_clean):
            if s_clean not in kept:
                kept.append(s_clean)
        else:
            removed.append((i, s))

# write outputs
with open(OUTPUT, "w", encoding="utf-8") as fo:
    for t in kept:
        fo.write(t + "\n")

with open(REPORT, "w", encoding="utf-8") as fr:
    fr.write("Removed lines (line_number : original_line):\n")
    for ln, text in removed:
        fr.write(f"{ln} : {text}\n")

print("✅ Done.")
print("Kept:", len(kept), "symbols ->", OUTPUT)
print("Removed:", len(removed), "lines ->", REPORT)
if len(kept) == 0:
    print("⚠️ CẢNH BÁO: Không mã hợp lệ nào được tìm thấy. Hãy mở vnstock_failed.txt kiểm tra thủ công.")
