@echo off
echo Starting Researcher Metrics API on http://127.0.0.1:8000
echo Press CTRL+C to stop.
echo.
uvicorn main:app --host 0.0.0.0 --port 8000
pause
