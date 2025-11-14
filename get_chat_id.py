# get_chat_id.py
import requests, json, sys

TOKEN = "8246313412:AAHKMq223Ps75C1HhfhEwwHQj5Svl5Tm0Uc"   # <-- token bạn đã có

def main():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except Exception as e:
        print("Error:", e)
        sys.exit(1)

    print(json.dumps(data, indent=2, ensure_ascii=False))

    # try to extract chat ids
    ids = []
    for item in data.get("result", []):
        # try message or channel_post
        chat = (item.get("message") or item.get("channel_post") or {}).get("chat")
        if chat and "id" in chat:
            ids.append(chat["id"])
    if ids:
        print("\\nDetected chat_id(s):", ids)
    else:
        print("\\nNo chat_id found. --> Make sure you opened the bot in Telegram and sent /start to it first.")

if __name__ == "__main__":
    main()
