@echo off
REM run_retry_failed.bat
REM Kích hoạt venv, chạy retry_failed.py, ghi log kèm timestamp

cd /d "C:\Users\Gau lang thang\Desktop\market_strength"

REM Kích hoạt virtualenv
call venv\Scripts\activate.bat

REM Tạo thư mục log nếu chưa có
if not exist logs mkdir logs

REM Chạy script và append log với timestamp
echo ---------------------------- >> logs/retry_run.log
echo Run at %DATE% %TIME% >> logs/retry_run.log
python retry_failed.py >> logs/retry_run.log 2>&1
echo Exit code: %ERRORLEVEL% >> logs/retry_run.log
echo. >> logs/retry_run.log

REM (Tùy chọn) deactivate venv (không cần bắt buộc)
call venv\Scripts\deactivate.bat
