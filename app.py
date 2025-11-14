# app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from compute import load_all_csv, compute_market_strength

app = FastAPI()
# cho phép frontend ở file:// hoặc server khác gọi API (cho giai đoạn dev)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

symbols_data = {}
current_result = {}

def refresh():
    global symbols_data, current_result
    print("Cập nhật dữ liệu...")
    symbols_data = load_all_csv('data/*.csv')
    res = compute_market_strength(symbols_data)
    current_result = res if res else {}
    print("✅ Cập nhật:", current_result)

sched = BackgroundScheduler()
# refresh mỗi 10 phút; khi test bạn có thể chỉnh nhỏ lại
sched.add_job(refresh, 'interval', minutes=10)
sched.start()

@app.on_event("startup")
def startup_event():
    refresh()

@app.get("/api/market-strength")
def get_strength():
    if not current_result:
        return {"error": "No data yet"}
    return current_result

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
