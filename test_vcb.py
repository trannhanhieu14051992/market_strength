# test_vcb.py - kiểm tra vnstock với mã VCB
from vnstock import Vnstock
v = Vnstock()
s = v.stock(symbol="VCB")
df = s.quote.history(start="2020-01-01", end="2025-11-13", interval="1D")
print("VCB rows:", None if df is None else len(df))
if df is not None:
    print(df.head(5).to_string(index=False))
