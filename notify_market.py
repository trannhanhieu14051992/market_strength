# notify_market.py
# Gửi cảnh báo Telegram dựa trên file score.json
import json, os, time, requests

# === CẤU HÌNH ===
# Option A: đặt trực tiếp token & chat id (tạm thời)
TOKEN = os.environ.get("TELEGRAM_TOKEN") or "8246313412:AAHKMq223Ps75C1HhfhEwwHQj5Svl5Tm0Uc"
# Thay None bằng chat id của bạn (số nguyên) hoặc để None để auto detect nếu muốn
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or 849935038

# File do compute.py xuất ra (nếu compute.py chưa xuất, ta dùng test file)
SCORE_FILE = "score.json"
STATE_FILE = "notify_state.json"

# Ngưỡng cảnh báo (bạn có thể tinh chỉnh)
THRESHOLDS = {
    "very_strong": 70,
    "strong": 50,
    "weak": 30
}
# ==================

def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

def load_score():
    if not os.path.exists(SCORE_FILE):
        return None
    try:
        with open(SCORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Error loading score.json:", e)
        return None

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
        except:
            pass
    return {"last_level": None, "last_score": None, "last_sent": 0}

def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def level_from_score(score):
    if score is None:
        return None
    if score >= THRESHOLDS["very_strong"]:
        return "very_strong"
    if score >= THRESHOLDS["strong"]:
        return "strong"
    if score >= THRESHOLDS["weak"]:
        return "weak"
    return "very_weak"

def pretty_msg(result):
    score = result.get("score")
    b = result.get("breadth_pct")
    v = result.get("vol_pct")
    m = result.get("mom_pct")
    lines = []
    lines.append("🔥 <b>MARKET STRENGTH UPDATE</b>")
    lines.append(f"Score: <b>{score}</b>")
    lines.append(f"Breadth: {b}% | Volume: {v}% | Momentum: {m}%")
    if score is None:
        lines.append("No data.")
    elif score >= THRESHOLDS["very_strong"]:
        lines.append("🚀 <b>Thị trường RẤT MẠNH — Có thể cân nhắc giải ngân</b>")
    elif score >= THRESHOLDS["strong"]:
        lines.append("📈 <b>Thị trường MẠNH — Theo dõi nhóm dẫn dắt</b>")
    elif score >= THRESHOLDS["weak"]:
        lines.append("⚠️ <b>Thị trường YẾU — Cẩn trọng</b>")
    else:
        lines.append("🔻 <b>Thị trường RẤT YẾU — Hạn chế giao dịch</b>")
    lines.append(f"⏱ {time.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)

def autodetect_chat_id(token):
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10).json()
        if not r.get("ok"):
            return None
        for item in r.get("result", []):
            chat = (item.get("message") or item.get("channel_post") or {}).get("chat")
            if chat and "id" in chat:
                return chat.get("id")
    except:
        return None
    return None

def main():
    global CHAT_ID, TOKEN
    if not TOKEN or TOKEN == "<PASTE_YOUR_TOKEN_HERE>":
        print("No TOKEN set. Set env TELEGRAM_TOKEN or edit TOKEN in the file.")
        return

    # try autodetect chat id if not set
    if not CHAT_ID:
        CHAT_ID = autodetect_chat_id(TOKEN)
        if CHAT_ID:
            print("Autodetected CHAT_ID:", CHAT_ID)
        else:
            print("CHAT_ID not provided and couldn't autodetect. Please set TELEGRAM_CHAT_ID env or set CHAT_ID variable.")
            return

    score = load_score()
    if not score:
        print("No score.json found or invalid.")
        return

    state = load_state()
    current_level = level_from_score(score.get("score"))
    last_level = state.get("last_level")

    # send when level changed OR score changed significantly (e.g., +/-5)
    send_flag = False
    if current_level != last_level:
        send_flag = True
    else:
        last_score = state.get("last_score") or 0
        if abs((score.get("score") or 0) - last_score) >= 5:
            send_flag = True

    if send_flag:
        msg = pretty_msg(score)
        ok, resp = send_message(TOKEN, CHAT_ID, msg)
        print("Sent:", ok, resp)
        if ok:
            state["last_level"] = current_level
            state["last_score"] = score.get("score")
            state["last_sent"] = int(time.time())
            save_state(state)
    else:
        print("No alert needed. Level unchanged and delta < threshold.")

if __name__ == "__main__":
    main()
