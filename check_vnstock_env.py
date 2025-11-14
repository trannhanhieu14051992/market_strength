import sys, subprocess, importlib, socket, time, traceback

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)

def try_pip_install(pkg):
    print(f"\n=> Thử cài đặt gói: {pkg} (pip install). Nếu venv đang active, pip sẽ cài vào venv.")
    code, out, err = run(f'"{sys.executable}" -m pip install --upgrade {pkg}')
    if code == 0:
        print("  ✅ pip cài xong.")
    else:
        print("  ❌ pip install thất bại. stdout:\n", out, "\nstderr:\n", err)

def check_vnstock_import():
    print("1) Kiểm tra import module 'vnstock' ...")
    try:
        import vnstock
        print("  ✅ vnstock import OK.")
        try:
            # Try to detect version via pkg_resources
            try:
                import pkg_resources
                ver = pkg_resources.get_distribution("vnstock").version
                print("  Phiên bản vnstock:", ver)
            except Exception:
                print("  Không lấy được version qua pkg_resources (không bắt buộc).")
            print("  Đường dẫn module:", getattr(vnstock, '__file__', 'n/a'))
            # show public attrs (small sample)
            names = [n for n in dir(vnstock) if not n.startswith('_')]
            print("  Một số thuộc tính/public names:", names[:40])
            return True, vnstock
        except Exception as e:
            print("  ❌ Lỗi khi inspect vnstock:", e)
            return True, vnstock
    except Exception as e:
        print("  ❌ Không import được vnstock:", e)
        # thử tự cài
        try:
            ans = input("Bạn có muốn tự động cài 'vnstock' bằng pip (y/n)? ").strip().lower()
        except Exception:
            ans = "y"
        if ans == "y":
            try_pip_install("git+https://github.com/thinh-vu/vnstock.git")
            time.sleep(1)
            try:
                import importlib
                vn = importlib.import_module("vnstock")
                print("  ✅ Đã cài và import được vnstock.")
                return True, vn
            except Exception as e2:
                print("  ❌ Vẫn không import được vnstock sau khi cài:", e2)
                return False, None
        else:
            print("  Bỏ qua cài vnstock. Bạn có thể cài thủ công bằng: pip install git+https://github.com/thinh-vu/vnstock.git")
            return False, None

def check_dns(host="hq.vnstocks.com"):
    print("\n2) Kiểm tra phân giải DNS cho:", host)
    try:
        ip = socket.gethostbyname(host)
        print("  ✅ DNS phân giải thành IP:", ip)
        return True, ip
    except Exception as e:
        print("  ❌ Không phân giải được DNS:", e)
        print("  Hướng dẫn kiểm tra thêm:")
        print("    - Mở CMD và chạy: ping", host)
        print("    - Mở CMD và chạy: nslookup", host)
        print("  Nếu 2 lệnh trên báo 'could not find host' -> DNS máy bạn đang có vấn đề.")
        print("  Gợi ý tạm thời: đổi DNS sang Google DNS (8.8.8.8) hoặc Cloudflare (1.1.1.1) qua Settings Network (GUI).")
        print("  Hoặc chạy CMD (Admin) để set DNS (ví dụ thay 'Wi-Fi' thành tên adapter của bạn):")
        print(r'    netsh interface ipv4 set dns name="Wi-Fi" static 8.8.8.8 primary')
        print(r'    netsh interface ipv4 add dns name="Wi-Fi" 1.1.1.1 index=2')
        return False, None

def try_vnstock_call(vnstock_module, symbol="VCB"):
    print(f"\n3) Thử gọi vnstock để lấy lịch sử một mã ({symbol}) ...")
    try:
        # prefer class name Vnstock (vnstock v3+)
        if hasattr(vnstock_module, "Vnstock"):
            V = getattr(vnstock_module, "Vnstock")
            print("  Sử dụng class Vnstock() ...")
            v = V()
            print("  Tạo instance Vnstock() thành công. In vài attrs mẫu của instance:")
            attrs = [a for a in dir(v) if not a.startswith("_")]
            print("   ", attrs[:60])
            # check if v.stock exists
            if hasattr(v, "stock"):
                try:
                    s = v.stock(symbol=symbol)
                    print("  v.stock(...) OK. In attrs của object s (tối đa 60):")
                    print("   ", [a for a in dir(s) if not a.startswith("_")][:60])
                    if hasattr(s, "quote") and hasattr(s.quote, "history"):
                        try:
                            df = s.quote.history(start="2020-01-01", end="2025-11-13", interval="1D")
                            print("  Gọi s.quote.history(...) trả về:", type(df), "số dòng:",
                                  None if df is None else (len(df) if hasattr(df,'__len__') else "n/a"))
                            if df is not None:
                                print("  3 dòng đầu của DataFrame (nếu có):")
                                try:
                                    print(df.head(3).to_string(index=False))
                                except Exception:
                                    print(df.head(3).to_dict(orient='records'))
                            return True
                        except Exception as e:
                            print("  ❌ Lỗi khi gọi s.quote.history:", e)
                            traceback.print_exc()
                            return False
                    else:
                        print("  ❌ Không thấy s.quote.history; thử các thuộc tính khác của s.")
                        return False
                except Exception as e:
                    print("  ❌ Lỗi khi tạo stock(...) hoặc truy xuất s:", e)
                    traceback.print_exc()
                    return False
            else:
                print("  ❌ Instance Vnstock không có method .stock — module vnstock có API khác. In module attrs để debug:")
                print([n for n in dir(vnstock_module) if not n.startswith("_")][:100])
                return False

        # fallback: tìm function history ở module level
        if hasattr(vnstock_module, "history"):
            try:
                hist = getattr(vnstock_module, "history")
                print("  Thử gọi vnstock.history(symbol=...) ...")
                df = hist(symbol)
                print("  Kết quả:", type(df), "rows:", None if df is None else len(df))
                return True
            except Exception as e:
                print("  ❌ Gọi vnstock.history lỗi:", e)
                return False

        print("  ❌ Không biết cách gọi API trên module vnstock hiện tại. In ra 50 public names của module để bạn gửi cho mình:")
        print([n for n in dir(vnstock_module) if not n.startswith("_")][:120])
        return False
    except Exception as e:
        print("  ❌ Lỗi không lường trước khi thử gọi vnstock:", e)
        traceback.print_exc()
        return False

def main():
    ok_import, vn_mod = check_vnstock_import()
    dns_ok, ip = check_dns("hq.vnstocks.com")
    if not ok_import:
        print("\n=> Không thể tiếp tục vì vnstock chưa import được.")
        print("   Bạn có thể cài vnstock bằng lệnh (trong venv):")
        print('     pip install git+https://github.com/thinh-vu/vnstock.git')
        return

    if not dns_ok:
        print("\n=> DNS không phân giải; script sẽ vẫn thử gọi vnstock nhưng rất có thể sẽ fail.")
        print("   Vui lòng sửa DNS (GUI hoặc lệnh netsh trên Windows với quyền Admin).")
        # still try calling vnstock to see specific error
    # thử gọi 1 mã
    print("\n--- Thử gọi API vnstock cho 1 mã mẫu (VCB) ---")
    success = try_vnstock_call(vn_mod, symbol="VCB")
    if success:
        print("\n🎉 Thử fetch thành công! Bạn có thể dùng script download_history_vnstock.py để tải hàng loạt.")
    else:
        print("\n⚠️ Thử fetch không thành công.")
        print("Gợi ý tiếp theo:")
        print(" - Nếu lỗi NameResolution (DNS) -> làm theo phần đổi DNS ở đầu script.")
        print(" - Nếu lỗi import / API khác -> gửi cho mình output của script này (public names) để mình sửa script tải phù hợp.")
        print(" - Nếu bạn muốn, mình có thể tự tạo 1 script download fallback từ cophieu68 chỉ với các mã có dữ liệu.")

if __name__ == "__main__":
    main()
