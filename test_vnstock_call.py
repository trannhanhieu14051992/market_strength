# test_vnstock_call.py - thử gọi vnstock v3+ để lấy lịch sử VCB
import traceback, json
try:
    from vnstock import Vnstock
except Exception as e:
    print("Import vnstock failed:", e)
    raise SystemExit(1)

sym = "VCB"   # đổi mã nếu muốn
try:
    v = Vnstock()
    # một số phiên bản gọi khác — ta in available attrs
    print("Vnstock object methods/attrs sample:", [a for a in dir(v) if not a.startswith('_')][:80])
    # try common call pattern
    if hasattr(v, 'stock'):
        s = v.stock(symbol=sym)   # trả về object
        print("v.stock OK; attrs of s:", [a for a in dir(s) if not a.startswith('_')][:80])
        if hasattr(s, 'quote') and hasattr(s.quote, 'history'):
            df = s.quote.history(start="2020-01-01", end="2025-11-13", interval="1D")
            print("history type:", type(df), "rows:", None if df is None else len(df))
            if df is not None:
                print(df.head(3).to_dict(orient='records'))
        else:
            print("Không thấy s.quote.history, in s.quote attrs:", [a for a in dir(s.quote) if not a.startswith('_')])
    else:
        print("Không có method .stock trên Vnstock; hãy in module vnstock attrs")
except Exception as e:
    print("Call error:", e)
    traceback.print_exc()
